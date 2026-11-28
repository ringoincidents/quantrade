"""Research-only extension of Market Data Vault; no network or trade authority."""
import hashlib
import json
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from vault import connect as vault_connect, parse_utc
from private_backup import private_dir, private_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS reference_captures(
 provider TEXT NOT NULL, series TEXT NOT NULL, captured_at TEXT NOT NULL,
 digest TEXT NOT NULL, rights_ref TEXT NOT NULL, raw BLOB NOT NULL,
 PRIMARY KEY(provider,series,captured_at,digest)
);
CREATE TABLE IF NOT EXISTS reference_rows(
 provider TEXT NOT NULL, series TEXT NOT NULL, captured_at TEXT NOT NULL,
 digest TEXT NOT NULL, identity TEXT NOT NULL, period TEXT NOT NULL,
 value TEXT NOT NULL, unit TEXT NOT NULL, filing_ref TEXT,
 PRIMARY KEY(provider,series,captured_at,digest,identity,period),
 FOREIGN KEY(provider,series,captured_at,digest)
 REFERENCES reference_captures(provider,series,captured_at,digest)
);
"""
MAX_BODY=4*1024*1024

def open_private(path):
    p=private_path(path)
    private_dir(p.parent)
    if p.exists() and (not p.is_file() or p.stat().st_mode & 0o077):
        raise ValueError("PRIVATE_DB_REQUIRED")
    import os
    fd=os.open(p,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    os.close(fd)
    db=vault_connect(p)
    db.executescript(SCHEMA)
    return db

def number(x):
    if not isinstance(x,str) or len(x)>128:
        raise ValueError("INVALID_NUMBER")
    import re
    if not re.fullmatch(r"-?\d+(?:\.\d+)?|-?\d{1,3}(?:,\d{3})+(?:\.\d+)?",x):
        raise ValueError("INVALID_NUMBER")
    n=Decimal(x.replace(",",""))
    if not n.is_finite():
        raise ValueError("INVALID_NUMBER")
    return str(n)

def normalize(provider,series,data):
    rows=[]
    if provider=="FRED":
        # Only this known units contract; no guessed unit or series metadata.
        if series!="DGS10":
            raise ValueError("UNSUPPORTED_SERIES")
        for r in data["observations"]:
            d=r["date"]
            if date.fromisoformat(d).isoformat()!=d:
                raise ValueError("INVALID_DATE")
            # Missing observations are not silently converted to zero.
            if r["value"]==".":
                continue
            rows.append((series,d,number(r["value"]),"PERCENT",None))
    elif provider=="DART":
        corp,year,report,scope=series.split(":")
        if scope!="CFS" or data["status"]!="000":
            raise ValueError("UNSUPPORTED_REPORT")
        for r in data["list"]:
            if (r["corp_code"],r["bsns_year"],r["reprt_code"])!=(corp,year,report):
                raise ValueError("IDENTITY_MISMATCH")
            if r.get("fs_div",scope)!=scope or r.get("currency")!="KRW":
                raise ValueError("UNIT_OR_SCOPE_MISMATCH")
            if r.get("thstrm_amount") in ("","-",None):
                continue
            filing=r["rcept_no"]
            if not isinstance(filing,str) or len(filing)!=14 or not filing.isascii() or not filing.isdigit():
                raise ValueError("INVALID_FILING")
            # Preserve statement and source labels; not standardized accounting taxonomy.
            key=json.dumps([r["sj_div"],r["account_id"],r["account_nm"],r.get("account_detail"),r.get("ord")],ensure_ascii=False,separators=(",",":"))
            rows.append((key,year+":"+report,number(r["thstrm_amount"]),"KRW",filing))
    else:
        raise ValueError("UNSUPPORTED_PROVIDER")
    if not rows or len(rows)>10000 or len({(r[0],r[1]) for r in rows})!=len(rows):
        raise ValueError("EMPTY_OR_DUPLICATE_ROWS")
    return rows

def ingest(db,provider,series,raw,*,captured_at,rights_ref=None,rights_confirmed=False):
    if rights_confirmed is not True or not isinstance(rights_ref,str) or not rights_ref.strip() or len(rights_ref)>200:
        raise ValueError("RIGHTS_UNCONFIRMED")
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BODY:
        raise ValueError("INVALID_RAW")
    captured=parse_utc(captured_at)
    if captured>datetime.now(timezone.utc).isoformat():
        raise ValueError("FUTURE_CAPTURE")
    data=json.loads(raw)
    rows=normalize(provider,series,data)
    digest=hashlib.sha256(raw).hexdigest()
    key=(provider,series,captured,digest)
    with db:
        existing=db.execute("SELECT raw,rights_ref FROM reference_captures WHERE provider=? AND series=? AND captured_at=? AND digest=?",key).fetchone()
        if existing is not None:
            if existing!=(raw,rights_ref):
                raise ValueError("CAPTURE_CONFLICT")
            stored=db.execute("SELECT identity,period,value,unit,filing_ref FROM reference_rows WHERE provider=? AND series=? AND captured_at=? AND digest=?",key).fetchall()
            if set(stored)!=set(rows):
                raise ValueError("INDEX_MISMATCH")
            return digest
        db.execute("INSERT INTO reference_captures VALUES(?,?,?,?,?,?)",(*key,rights_ref,raw))
        db.executemany("INSERT INTO reference_rows VALUES(?,?,?,?,?,?,?,?,?)",[(*key,*r) for r in rows])
    return digest

def observed_snapshot(db,provider,series,asof):
    # Observed/captured time only. Never implies original release or PIT market availability.
    cutoff=parse_utc(asof)
    captures=db.execute("SELECT captured_at,digest,raw FROM reference_captures WHERE provider=? AND series=? AND captured_at<=? ORDER BY captured_at DESC,digest LIMIT 2",(provider,series,cutoff)).fetchall()
    if not captures:
        return {"state":"NOT_CAPTURED","pit_verified":False,"rows":[]}
    if len(captures)>1 and captures[0][0]==captures[1][0]:
        raise ValueError("AMBIGUOUS_CAPTURE")
    captured,digest,raw=captures[0]
    if hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError("RAW_HASH_MISMATCH")
    rows=db.execute("SELECT identity,period,value,unit,filing_ref FROM reference_rows WHERE provider=? AND series=? AND captured_at=? AND digest=? ORDER BY identity,period",(provider,series,captured,digest)).fetchall()
    if set(rows)!=set(normalize(provider,series,json.loads(raw))):
        raise ValueError("INDEX_MISMATCH")
    return {"state":"OBSERVED_ONLY","pit_verified":False,"captured_at":captured,"digest":digest,"rows":rows}
