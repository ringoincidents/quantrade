"""Official US Treasury par-yield series research adapter and private raw archive.

No cron, broker, market signals, or third-party quote feeds. Uses only the
official Treasury annual Atom/OData XML endpoint. One explicit year at a time.
The archive stores when OUR collector saw a version, NOT the first historical
release date. Unknown historical first publication => ineligible for PIT test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

OFFICIAL_HOST = "home.treasury.gov"
PATH = "/resource-center/data-chart-center/interest-rates/pages/xml"
KIND = "daily_treasury_yield_curve"
MATURITIES = {"2Y": "BC_2YEAR", "10Y": "BC_10YEAR"}
MAX_XML_BYTES = 4_000_000


def official_url(year: int) -> str:
    if not isinstance(year, int) or not 1990 <= year <= datetime.now(timezone.utc).year:
        raise ValueError("Treasury XML year out of supported historical range")
    qs = urllib.parse.urlencode({"data": KIND, "field_tdr_date_value": str(year)})
    return f"https://{OFFICIAL_HOST}{PATH}?{qs}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_annual_xml(raw: bytes, year: int) -> dict[str, list[tuple[str, float]]]:
    """Parse official Atom entries. Missing maturity is MISSING, not 0."""
    if not raw or len(raw) > MAX_XML_BYTES:
        raise ValueError("Empty or unexpectedly large Treasury feed")
    root = ET.fromstring(raw)
    rows = {k: [] for k in MATURITIES}
    seen_dates = set()
    entries = [el for el in root.iter() if _local(el.tag) == "entry"]
    if not entries:
        raise ValueError("No official Atom entries; feed/host may have changed")
    for entry in entries:
        props = next((el for el in entry.iter() if _local(el.tag) == "properties"), None)
        if props is None:
            raise ValueError("No OData properties in Treasury entry")
        fields = {_local(el.tag): el.text for el in props}
        observation = (fields.get("NEW_DATE") or "")[:10]
        if not observation or date.fromisoformat(observation).year != year:
            raise ValueError(f"Unexpected Treasury observation date {observation}")
        if observation in seen_dates:
            raise ValueError("Duplicate Treasury observation date")
        seen_dates.add(observation)
        for maturity, key in MATURITIES.items():
            v = fields.get(key)
            if v is None or not v.strip():
                continue
            rate = float(v)
            if not 0 < rate < 100:
                raise ValueError("Implausible percent yield")
            rows[maturity].append((observation, rate))
    return rows


def fetch_official(year: int, opener=None) -> tuple[bytes, str]:
    """Perform one explicit official-host HTTP request; no untrusted redirects."""
    url = official_url(year)
    request = urllib.request.Request(url, headers={
        "User-Agent": "QuanTradeResearch/0.1 (official-data research; rate limited)",
        "Accept": "application/atom+xml,application/xml,text/xml",
    })
    response = (opener or urllib.request.urlopen)(request, timeout=25)
    with response:
        final_url = response.geturl()
        parsed = urllib.parse.urlparse(final_url)
        if parsed.scheme != "https" or parsed.hostname != OFFICIAL_HOST:
            raise ValueError("Treasury source redirected to an untrusted host")
        data = response.read(MAX_XML_BYTES + 1)
        if len(data) > MAX_XML_BYTES:
            raise ValueError("Treasury XML response exceeded safety limit")
    return data, final_url


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS archive_batches (
      sha256 TEXT PRIMARY KEY,
      source_url TEXT NOT NULL,
      collector_seen_utc TEXT NOT NULL,
      source_year INTEGER NOT NULL,
      byte_size INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS yield_versions (
      source_series TEXT NOT NULL,
      observation_date TEXT NOT NULL,
      collector_seen_utc TEXT NOT NULL,
      value_percent REAL NOT NULL,
      batch_sha256 TEXT NOT NULL REFERENCES archive_batches(sha256),
      originally_public_at_utc TEXT,
      PRIMARY KEY(source_series,observation_date,collector_seen_utc)
    );
    CREATE INDEX IF NOT EXISTS yield_asof
       ON yield_versions(source_series,observation_date,collector_seen_utc);
    """)
    return db


def archive_and_index(private_dir: str | Path, raw: bytes, year: int,
                      final_url: str, collector_seen_utc: str) -> dict:
    """Save immutable raw XML privately, then add collector-time snapshots.

    No claims that collector_seen_utc equals original release time. Recovered
    history requires separately verified original vintages before backtesting.
    """
    if urllib.parse.urlparse(final_url).hostname != OFFICIAL_HOST:
        raise ValueError("Source URL is not official Treasury")
    seen = datetime.fromisoformat(collector_seen_utc.replace("Z", "+00:00"))
    if seen.tzinfo is None or seen.utcoffset() is None:
        raise ValueError("Collector timestamp must be timezone-aware")
    seen_utc = seen.astimezone(timezone.utc).isoformat()
    rows = parse_annual_xml(raw, year)
    folder = Path(private_dir).resolve()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw_dir = folder / "sha256"
    raw_dir.mkdir(exist_ok=True, mode=0o700)
    digest = hashlib.sha256(raw).hexdigest()
    target = raw_dir / f"{digest}.xml"
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("Existing archived source has corrupted hash")
    else:
        # Make immutable-by-convention; originals never overwritten.
        try:
            with target.open("xb") as f:
                f.write(raw)
        except FileExistsError:
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("Archive collision or corruption")
    db = connect(folder / "treasury_yields.sqlite")
    try:
        with db:
            previous = db.execute("SELECT 1 FROM archive_batches WHERE sha256=?",
                                  (digest,)).fetchone()
            if previous:
                return {"status": "unchanged", "sha256": digest,
                        "rows_by_series": {k: len(v) for k, v in rows.items()}}
            db.execute("INSERT INTO archive_batches VALUES(?,?,?,?,?)",
                       (digest, final_url, seen_utc, year, len(raw)))
            for maturity, values in rows.items():
                series_id = f"UST_PAR_{maturity}"
                for observed_date, value in values:
                    db.execute(
                        "INSERT INTO yield_versions VALUES(?,?,?,?,?,NULL)",
                        (series_id, observed_date, seen_utc, value, digest))
        return {"status": "archived", "sha256": digest,
                "rows_by_series": {k: len(v) for k, v in rows.items()}}
    finally:
        db.close()


def latest_captured(db: sqlite3.Connection, series_id: str,
                    observed_date: str, at_utc: str) -> float | None:
    """What our collector had captured by time t. NOT historic first-public PIT."""
    t = datetime.fromisoformat(at_utc.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("UTC-aware timestamp required")
    r = db.execute(
        "SELECT value_percent FROM yield_versions "
        "WHERE source_series=? AND observation_date=? "
        "AND collector_seen_utc<=? ORDER BY collector_seen_utc DESC LIMIT 1",
        (series_id, observed_date, t.astimezone(timezone.utc).isoformat()),
    ).fetchone()
    return r[0] if r else None


def verified_historic_pit(db: sqlite3.Connection, series_id: str,
                          observed_date: str, at_utc: str) -> float | None:
    """Strict: WITHOUT independent original release evidence, return UNKNOWN."""
    t = datetime.fromisoformat(at_utc.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("UTC-aware timestamp required")
    r = db.execute(
        "SELECT value_percent FROM yield_versions "
        "WHERE source_series=? AND observation_date=? "
        "AND originally_public_at_utc IS NOT NULL AND originally_public_at_utc<=? "
        "ORDER BY originally_public_at_utc DESC LIMIT 1",
        (series_id, observed_date, t.astimezone(timezone.utc).isoformat()),
    ).fetchone()
    return r[0] if r else None


def pilot(year: int, private_dir: str | Path | None = None) -> dict:
    raw, url = fetch_official(year)
    rows = parse_annual_xml(raw, year)
    if len(rows["10Y"]) < 100 or len(rows["2Y"]) < 100:
        raise ValueError("Too few official observations; halt pilot")
    summary = {
        "source": "US Treasury annual par-yield XML", "year": year,
        "record_count": {k: len(v) for k, v in rows.items()},
        "date_range": {k: [v[0][0], v[-1][0]] for k, v in rows.items()},
        "sha256": hashlib.sha256(raw).hexdigest(),
        "original_pit_releases_verified": False,
    }
    if private_dir:
        result = archive_and_index(private_dir, raw, year, url,
                                   datetime.now(timezone.utc).isoformat())
        summary["private_archive_status"] = result["status"]
    else:
        summary["private_archive_status"] = "not_saved_ephemeral_pilot"
    return summary


def main():
    ap = argparse.ArgumentParser(description="Official Treasury annual XML pilot, no trading")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--private-dir", help="Optional private persistent storage, outside Git")
    args = ap.parse_args()
    print(json.dumps(pilot(args.year, args.private_dir), indent=2))


if __name__ == "__main__":
    main()
