"""Offline, append-only *research prototype* for licensed price bars.

No network access, provider API, automatic ingest, market signal, or trading.
Production integration requires separate authority and validation.
"""
from __future__ import annotations

import csv
import io
import hashlib
import math
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS datasets(
    id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, provider TEXT NOT NULL,
    currency TEXT NOT NULL, basis TEXT NOT NULL CHECK (basis='RAW_OHLCV'),
    rights_note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS batches(
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    sha256 TEXT NOT NULL, source_uri TEXT NOT NULL,
    captured_at TEXT NOT NULL, rows INTEGER NOT NULL,
    PRIMARY KEY(dataset_id,sha256)
);
CREATE TABLE IF NOT EXISTS bars(
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    session TEXT NOT NULL, available_at TEXT NOT NULL,
    open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL,
    close REAL NOT NULL, volume REAL NOT NULL,
    availability_verified INTEGER NOT NULL CHECK (availability_verified IN (0,1)),
    batch_sha TEXT NOT NULL, PRIMARY KEY(dataset_id,session,available_at)
);
CREATE INDEX IF NOT EXISTS idx_bar_point_in_time
    ON bars(dataset_id,available_at,session);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    return db


def parse_utc(value: str) -> str:
    if not value or value in ("UNKNOWN", ".", "null"):
        raise ValueError("An explicit first-availability timestamp is mandatory")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("Timestamp must contain UTC offset")
    return d.astimezone(timezone.utc).isoformat()


def register_dataset(db: sqlite3.Connection, dataset_id: str, asset_id: str,
                     provider: str, currency: str, rights_note: str) -> None:
    if not all((dataset_id, asset_id, provider, currency, rights_note)):
        raise ValueError("Dataset identity, source, currency and rights are required")
    # RAW only until corporate-actions/vintage reconstruction is validated.
    with db:
        db.execute("INSERT INTO datasets VALUES (?,?,?,?,?,?)",
                   (dataset_id, asset_id, provider, currency, "RAW_OHLCV", rights_note))


def _read_rows(path: Path):
    return read_rows_bytes(path.read_bytes())


def read_rows_bytes(raw: bytes):
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"session", "open", "high", "low", "close", "volume",
                    "first_available_at_utc"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("Missing required OHLCV or first-publication fields")
        rows = []
        seen = set()
        for row in reader:
            session = row["session"]
            if date.fromisoformat(session).isoformat() != session:
                raise ValueError("Noncanonical ISO session date")
            available = parse_utc(row["first_available_at_utc"])
            if session in seen:
                raise ValueError("Multiple versions inside one input CSV; use separate source batches")
            seen.add(session)
            o, h, l, c, v = [float(row[x]) for x in
                             ("open", "high", "low", "close", "volume")]
            if (not all(map(math.isfinite, (o, h, l, c, v))) or
                min(o, h, l, c) <= 0 or v < 0 or
                l > min(o, c, h) or h < max(o, c, l)):
                raise ValueError(f"Invalid OHLCV at {session}")
            rows.append((session, available, o, h, l, c, v))
    if not rows:
        raise ValueError("Empty market data input")
    return rows


def ingest_csv(db: sqlite3.Connection, path: str | Path, *, dataset_id: str,
               source_uri: str, usage_rights_confirmed: bool = False,
               availability_verified: bool = False) -> dict:
    """Fail closed if rights aren't confirmed. Claims about availability are auditable.

    Revisions must arrive as distinct later first-availability timestamps.
    availability_verified=True MUST mean first availability was independently checked.
    """
    if not usage_rights_confirmed:
        raise PermissionError("Source rights must be confirmed before local data retention")
    if not source_uri:
        raise ValueError("Source URI is required")
    path = Path(path)
    raw = path.read_bytes()
    raw_hash = hashlib.sha256(raw).hexdigest()
    rows = read_rows_bytes(raw)
    now = datetime.now(timezone.utc).isoformat()
    with db:
        if db.execute("SELECT 1 FROM batches WHERE dataset_id=? AND sha256=?",
                      (dataset_id, raw_hash)).fetchone():
            return {"status": "unchanged", "sha256": raw_hash, "new_rows": 0}
        if not db.execute("SELECT 1 FROM datasets WHERE id=?", (dataset_id,)).fetchone():
            raise ValueError("Dataset must be registered with provider and rights")
        # No retroactive rewriting: a different value for the same availability
        # timestamp indicates unresolved vendor/revision conflict.
        new_count = 0
        for session, available, o, h, l, c, v in rows:
            previous = db.execute(
                "SELECT open,high,low,close,volume,availability_verified FROM bars "
                "WHERE dataset_id=? AND session=? AND available_at=?",
                (dataset_id, session, available)
            ).fetchone()
            values = (o, h, l, c, v)
            if previous:
                if tuple(previous[:5]) != values or bool(previous[5]) != availability_verified:
                    raise ValueError(f"Conflicting published revision: {session} at {available}")
                continue
            db.execute("INSERT INTO bars VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (dataset_id, session, available, *values,
                        int(availability_verified), raw_hash))
            new_count += 1
        db.execute("INSERT INTO batches VALUES (?,?,?,?,?)",
                   (dataset_id, raw_hash, source_uri, now, len(rows)))
    return {"status": "ingested", "sha256": raw_hash, "new_rows": new_count}


def snapshot(db: sqlite3.Connection, dataset_id: str, asof_utc: str,
             *, verified_only: bool = True) -> list[dict]:
    """Research-as-of query: latest *then known* revision for each session.

    Does not automatically adjust splits or dividends; RAW_OHLCV ONLY.
    """
    when = parse_utc(asof_utc)
    rows = db.execute(
        """SELECT session,available_at,open,high,low,close,volume
           FROM (
             SELECT session,available_at,open,high,low,close,volume,
                    ROW_NUMBER() OVER (
                      PARTITION BY session ORDER BY available_at DESC
                    ) AS rank
             FROM bars
             WHERE dataset_id=? AND available_at<=?
               AND (availability_verified=1 OR ?=0)
           )
           WHERE rank=1 ORDER BY session""",
        (dataset_id, when, int(verified_only))
    ).fetchall()
    return [dict(zip(("session","available_at","open","high","low",
                      "close","volume"), row)) for row in rows]
