"""Offline SQLite snapshot/restore of the public duty spool only.

Uses SQLite backup API, not a raw copy of a live WAL database. Backup bundles
are private. No deletion, overwrite, upload, automatic restore or network.
"""
import argparse,hashlib,json,os,sqlite3,tempfile
from pathlib import Path
from datetime import datetime,timezone
import operations_audit as audit

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def check(db):
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("SQLITE_INTEGRITY")
    required={"public_jobs","public_reports","public_meta","duty_handoffs","duty_reviews","duty_period_reports"}
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required<=tables:raise ValueError("SCHEMA_INCOMPLETE")
    # Full history, not just the audit's bounded window.
    for table,body in (("public_jobs","payload"),("public_reports","payload"),("duty_handoffs","body"),("duty_period_reports","body")):
        for p,d in db.execute(f"SELECT {body},digest FROM {table} WHERE {body} IS NOT NULL OR digest IS NOT NULL"):
            audit.verified(p,d)
    return {t:db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in sorted(required)}
def snapshot(source,bundle):
    source=Path(source).resolve(strict=True);bundle=Path(bundle)
    bundle.mkdir(mode=0o700,parents=False,exist_ok=False)
    target=bundle/"spool.sqlite"
    src=audit.open_readonly(source)
    dst=sqlite3.connect(target)
    try:
        src.backup(dst);dst.execute("PRAGMA journal_mode=DELETE")
        counts=check(dst)
    finally:dst.close();src.close()
    os.chmod(target,0o600)
    manifest={"schema":"QT_PUBLIC_SPOOL_BACKUP_V1","created_at":datetime.now(timezone.utc).isoformat(),
              "sha256":sha(target),"bytes":target.stat().st_size,"counts":counts,
              "scope":"PUBLIC_REFERENCE_PILOT_ONLY"}
    with (bundle/"manifest.json").open("x") as f:json.dump(manifest,f,sort_keys=True)
    os.chmod(bundle/"manifest.json",0o600)
    return manifest
def verify(bundle):
    bundle=Path(bundle);target=bundle/"spool.sqlite"
    m=json.loads((bundle/"manifest.json").read_text())
    if m.get("schema")!="QT_PUBLIC_SPOOL_BACKUP_V1" or m.get("scope")!="PUBLIC_REFERENCE_PILOT_ONLY" or sha(target)!=m["sha256"] or target.stat().st_size!=m["bytes"]:
        raise ValueError("BACKUP_MANIFEST")
    db=audit.open_readonly(target)
    try:
        if check(db)!=m["counts"]:raise ValueError("BACKUP_COUNTS")
    finally:db.close()
    return m
def restore(bundle,target):
    m=verify(bundle);target=Path(target)
    if any(Path(str(target)+s).exists() for s in ("","-wal","-shm","-journal")):raise FileExistsError("DESTINATION_EXISTS")
    # Copy into a unique temporary file, verify exact bytes, link with no overwrite.
    import shutil
    with tempfile.NamedTemporaryFile(dir=target.parent,prefix=".qt-restore-",delete=False) as tmp:
        staged=Path(tmp.name)
    try:
        shutil.copyfile(Path(bundle)/"spool.sqlite",staged)
        if sha(staged)!=m["sha256"]:raise ValueError("RESTORE_HASH")
        os.chmod(staged,0o600);os.link(staged,target)
    finally:staged.unlink()
    return m
def main():
    p=argparse.ArgumentParser();p.add_argument("action",choices=("snapshot","verify","restore"));p.add_argument("--bundle",required=True);p.add_argument("--db")
    a=p.parse_args();os.umask(0o077)
    if a.action!="verify" and not a.db:p.error("--db required")
    result=snapshot(a.db,a.bundle) if a.action=="snapshot" else restore(a.bundle,a.db) if a.action=="restore" else verify(a.bundle)
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
