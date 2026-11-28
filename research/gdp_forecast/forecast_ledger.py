"""Local research ledger; no production or trading integration."""
import sqlite3
import json
import hashlib
import math
from observation_validator import instant, quarter

def connect(path):
    db=sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS events(
      id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL
    );
    CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON events
      BEGIN SELECT RAISE(ABORT,'immutable event'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON events
      BEGIN SELECT RAISE(ABORT,'immutable event'); END;
    """)
    return db

def append(db,kind,payload):
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False)
    key=hashlib.sha256((kind+":"+raw).encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?)",(key,kind,raw))
    return key

def read(db,key,kind):
    row=db.execute("SELECT payload FROM events WHERE id=? AND kind=?",(key,kind)).fetchone()
    if row is None: raise ValueError("Unknown event")
    return json.loads(row[0])

def forecast(db,period,issued_at,model,version,value,evidence_sha):
    quarter(period); instant(issued_at)
    if not model or not version or not math.isfinite(value): raise ValueError("Invalid forecast")
    if len(evidence_sha)!=64 or any(c not in "0123456789abcdef" for c in evidence_sha): raise ValueError("Invalid evidence hash")
    return append(db,"forecast",dict(period=period,issued_at=issued_at,model=model,version=version,value=value,evidence_sha=evidence_sha))

def realization(db,period,public_at,vintage,value):
    quarter(period); instant(public_at)
    if vintage not in ("FIRST_RELEASE","REVISED") or not math.isfinite(value): raise ValueError("Invalid realization")
    return append(db,"realization",dict(period=period,public_at=public_at,vintage=vintage,value=value))

def evaluate(db,forecast_id,realization_id,asof):
    f=read(db,forecast_id,"forecast"); r=read(db,realization_id,"realization")
    if f["period"]!=r["period"] or not instant(f["issued_at"])<instant(r["public_at"])<=instant(asof):
        raise ValueError("Period or chronology mismatch")
    error=f["value"]-r["value"]
    return append(db,"evaluation",dict(forecast_id=forecast_id,realization_id=realization_id,asof=asof,error=error,absolute_error=abs(error),squared_error=error**2))
