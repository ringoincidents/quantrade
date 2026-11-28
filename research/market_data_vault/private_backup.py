"""Local offline backup/restore of the existing P0 vault plus original CSVs.
No network, no permanent hosting, no encryption or independent rights attestation.
Trusted local filesystem and exclusive ownership of archive directories required.
"""
import hashlib
import json
import os
import sqlite3
import stat
import tempfile
from pathlib import Path
from vault import read_rows_bytes,parse_utc

SCHEMA="qt-vault-backup-v1"
MAX_FILE=32*1024*1024
MAX_DB=128*1024*1024
MAX_TOTAL=256*1024*1024
MAX_FILES=1000
MAX_MANIFEST=256*1024

def require(ok,reason):
    if not ok:raise ValueError(reason)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def is_sha(s):return isinstance(s,str) and len(s)==64 and all(x in "0123456789abcdef" for x in s)
def private_path(path):
    p=Path(path).absolute()
    require(p==p.resolve(),"SYMLINK_PATH")
    require(not any((a/".git").exists() for a in (p,*p.parents)),"REPOSITORY_PATH_FORBIDDEN")
    return p
def private_dir(p):
    p=private_path(p)
    require(p.is_dir() and stat.S_IMODE(p.stat().st_mode)&0o077==0,"PRIVATE_DIRECTORY_REQUIRED")
    return p
def read(p,limit):
    require(p.is_file() and not p.is_symlink(),"FILE_UNAVAILABLE")
    require(p.stat().st_size<=limit,"FILE_TOO_LARGE")
    with p.open("rb") as f:b=f.read(limit+1)
    require(len(b)<=limit,"FILE_TOO_LARGE")
    return b
def write_new(p,b):
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(b);f.flush();os.fsync(f.fileno())
def sync_dir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
def ro(p):
    db=sqlite3.connect(p.as_uri()+"?mode=ro",uri=True)
    db.execute("PRAGMA query_only=ON")
    return db
def batch_set(db):
    require(db.execute("PRAGMA integrity_check").fetchall()==[("ok",)],"INDEX_INTEGRITY_FAILED")
    require(not db.execute("PRAGMA foreign_key_check").fetchall(),"INDEX_FOREIGN_KEY_FAILED")
    batches=db.execute("SELECT dataset_id,sha256,captured_at,rows FROM batches ORDER BY dataset_id,sha256").fetchall()
    require(0<len(batches)<=MAX_FILES and all(is_sha(b[1]) for b in batches),"INVALID_BATCH_SET")
    return batches
def validate_index(db,raw_dir):
    """Check each indexed bar against its original bytes and batch membership.
    Also reject missing indexed observations and conflicting published values.
    """
    batches=batch_set(db);expected={};owners={}
    total=0
    for dataset,digest,captured,count in batches:
        raw=read(raw_dir/(digest+".csv"),MAX_FILE);total+=len(raw)
        require(total<=MAX_TOTAL,"ARCHIVE_SIZE_LIMIT")
        require(sha(raw)==digest,"RAW_HASH_MISMATCH")
        parsed=read_rows_bytes(raw)
        require(len(parsed)==count,"BATCH_COUNT_MISMATCH")
        capture=parse_utc(captured)
        for session,available,*values in parsed:
            require(available<=capture,"CAPTURE_BEFORE_PUBLICATION")
            key=(dataset,session,available)
            require(key not in expected or expected[key]==tuple(values),"CONFLICTING_RAW_REVISION")
            expected[key]=tuple(values)
            owners.setdefault(key,set()).add(digest)
    seen=set()
    for dataset,session,available,o,h,l,c,v,verified,digest in db.execute("SELECT dataset_id,session,available_at,open,high,low,close,volume,availability_verified,batch_sha FROM bars"):
        key=(dataset,session,available)
        require(key in expected and tuple((o,h,l,c,v))==expected[key] and digest in owners[key] and verified in (0,1),"INDEX_RAW_MISMATCH")
        seen.add(key)
    require(seen==set(expected),"INDEX_ROWS_MISSING")
    return {"datasets":db.execute("SELECT count(*) FROM datasets").fetchone()[0],"batches":len(batches),"bars":len(seen)}

def pack(index_path,raw_dir,destination,*,rights_confirmed=False):
    """Publish new package; manifest is completion marker, never overwrite.
    Original CSV directory must contain SHA256.csv for every indexed batch.
    """
    require(rights_confirmed is True,"BACKUP_RIGHTS_UNCONFIRMED")
    source=private_path(index_path);raw_dir=private_dir(raw_dir)
    dest=private_path(destination);private_dir(dest.parent)
    require(source.is_file() and source.stat().st_size<=MAX_DB,"INDEX_UNAVAILABLE")
    dest.mkdir(mode=0o700)
    sync_dir(dest.parent)
    blobs=dest/"raw";blobs.mkdir(mode=0o700)
    # Back up to a new index, not the live source. SQLite backup is a consistent
    # snapshot including committed WAL data, not a blind file copy.
    index=dest/"vault.sqlite"
    fd=os.open(index,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    src=ro(source);out=sqlite3.connect(index)
    try:src.backup(out)
    finally:out.close();src.close()
    db=ro(index)
    try:
        batches=batch_set(db)
        total=0
        for digest in sorted({x[1] for x in batches}):
            b=read(raw_dir/(digest+".csv"),MAX_FILE)
            total+=len(b);require(total<=MAX_TOTAL,"ARCHIVE_SIZE_LIMIT")
            require(sha(b)==digest,"RAW_HASH_MISMATCH")
            write_new(blobs/(digest+".csv"),b)
        counts=validate_index(db,blobs)
    finally:db.close()
    data=read(index,MAX_DB)
    with index.open("rb") as f:os.fsync(f.fileno())
    manifest={"schema":SCHEMA,"index_sha256":sha(data),"index_bytes":len(data),
              "raw_sha256":sorted({x[1] for x in batches}),"counts":counts,
              "rights_attested":True,"independent_rights_verified":False}
    encoded=json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()
    sync_dir(blobs)
    write_new(dest/"manifest.json",encoded);sync_dir(dest);sync_dir(dest.parent)
    return {"state":"PACKED","manifest_sha256":sha(encoded),"counts":counts}

def verify(package,expected_manifest_sha256):
    root=private_dir(package);raw_dir=private_dir(root/"raw")
    require(is_sha(expected_manifest_sha256),"MANIFEST_HASH_REQUIRED")
    encoded=read(root/"manifest.json",MAX_MANIFEST)
    require(sha(encoded)==expected_manifest_sha256,"MANIFEST_HASH_MISMATCH")
    m=json.loads(encoded)
    require(isinstance(m,dict) and m.get("schema")==SCHEMA and m.get("rights_attested") is True and m.get("independent_rights_verified") is False,"INVALID_MANIFEST")
    digests=m.get("raw_sha256")
    require(isinstance(digests,list) and 0<len(digests)<=MAX_FILES and all(is_sha(x) for x in digests) and digests==sorted(set(digests)),"INVALID_RAW_LIST")
    require({p.name for p in raw_dir.iterdir()}=={x+".csv" for x in digests},"RAW_SET_MISMATCH")
    idx=root/"vault.sqlite";data=read(idx,MAX_DB)
    require(sha(data)==m.get("index_sha256") and len(data)==m.get("index_bytes"),"INDEX_HASH_MISMATCH")
    # Reject WAL/journal sidecars that could change the meaning of checked bytes.
    require({p.name for p in root.iterdir()}=={"raw","vault.sqlite","manifest.json"},"PACKAGE_FILE_SET_MISMATCH")
    db=ro(idx)
    try:
        require(sorted({x[1] for x in batch_set(db)})==digests,"BATCH_SET_MISMATCH")
        counts=validate_index(db,raw_dir)
    finally:db.close()
    require(counts==m.get("counts"),"MANIFEST_COUNT_MISMATCH")
    return {"state":"VERIFIED","manifest_sha256":expected_manifest_sha256,"counts":counts}

def restore(package,destination,expected_manifest_sha256,*,rights_confirmed=False):
    require(rights_confirmed is True,"RESTORE_RIGHTS_UNCONFIRMED")
    root=private_dir(package);dest=private_path(destination);private_dir(dest.parent)
    verified=verify(root,expected_manifest_sha256)
    # Destination must be entirely new. Incomplete failed copies lack a valid
    # completion manifest or fail verification; never overwrite an existing index.
    dest.mkdir(mode=0o700);sync_dir(dest.parent)
    (dest/"raw").mkdir(mode=0o700)
    for p in sorted((root/"raw").iterdir()):write_new(dest/"raw"/p.name,read(p,MAX_FILE))
    write_new(dest/"vault.sqlite",read(root/"vault.sqlite",MAX_DB))
    sync_dir(dest/"raw")
    write_new(dest/"manifest.json",read(root/"manifest.json",MAX_MANIFEST))
    sync_dir(dest);sync_dir(dest.parent)
    result=verify(dest,expected_manifest_sha256)
    return {**result,"state":"RESTORED"}
