"""Trusted local filesystem only; expected digest must be kept separately."""
import hashlib
import sqlite3
from pathlib import Path
from contextlib import closing
import os

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(65536),b""): h.update(chunk)
    return h.hexdigest()

def verify(db):
    if db.execute("PRAGMA integrity_check").fetchall()!=[("ok",)]:
        raise ValueError("SQLite integrity failure")
    for key,kind,payload in db.execute("SELECT id,kind,payload FROM events"):
        if hashlib.sha256((kind+":"+payload).encode()).hexdigest()!=key:
            raise ValueError("Event digest mismatch")

def snapshot(db,destination):
    if db.in_transaction: raise ValueError("Commit pending writes first")
    p=Path(destination)
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.close(fd)
    try:
        with closing(sqlite3.connect(p)) as out:
            db.backup(out)
            verify(out)
        return digest(p)
    except BaseException:
        p.unlink(missing_ok=True)
        raise

def restore(source,destination,expected_sha):
    p=Path(source)
    if digest(p)!=expected_sha: raise ValueError("Snapshot digest mismatch")
    with closing(sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True)) as db:
        verify(db)
        return snapshot(db,destination)
