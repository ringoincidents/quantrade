"""Synthetic-only Market Data Vault regression tests. No network or trading."""
from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from vault import connect, ingest_csv, parse_utc, register_dataset, snapshot
from indicators import sma, ema, rsi_wilder, atr_wilder, LIBRARY_VERSION

HEADERS = ["session", "open", "high", "low", "close", "volume", "first_available_at_utc"]


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = connect(self.folder / "vault.db")
        self.addCleanup(self.db.close)
        register_dataset(self.db, "US:ETF:XYZ:RAW", "US:ETF:XYZ",
                         "SyntheticTestProvider", "USD", "synthetic test fixture")

    def file(self, name="data.csv", **updates):
        row = {"session": "2026-10-01", "open": "100", "high": "110",
               "low": "90", "close": "105", "volume": "1000",
               "first_available_at_utc": "2026-10-01T21:00:00Z"}
        row.update(updates)
        p = self.folder / name
        with p.open("w", newline="", encoding="utf8") as stream:
            writer = csv.DictWriter(stream, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerow(row)
        return p

    def load(self, p, verified=True, approved=True):
        return ingest_csv(self.db, p, dataset_id="US:ETF:XYZ:RAW",
                          source_uri="synthetic://test", availability_verified=verified,
                          usage_rights_confirmed=approved)

    def test_01_rights_fail_closed(self):
        with self.assertRaises(PermissionError):
            self.load(self.file(), approved=False)
        self.assertEqual(snapshot(self.db, "US:ETF:XYZ:RAW",
                                  "2026-10-03T00:00:00Z"), [])

    def test_02_first_availability_must_be_timezone_aware(self):
        for bad in ("UNKNOWN", "2026-10-01T15:00:00", ""):
            with self.assertRaises(ValueError):
                self.load(self.file(first_available_at_utc=bad))

    def test_03_no_lookahead_and_snapshot(self):
        self.load(self.file())
        self.assertEqual(snapshot(self.db, "US:ETF:XYZ:RAW",
                                  "2026-10-01T20:59:59Z"), [])
        values = snapshot(self.db, "US:ETF:XYZ:RAW", "2026-10-01T21:00:00Z")
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["close"], 105)

    def test_04_repeat_ingest_is_idempotent(self):
        p = self.file()
        self.assertEqual(self.load(p)["new_rows"], 1)
        self.assertEqual(self.load(p)["status"], "unchanged")
        self.assertEqual(self.db.execute("SELECT count(*) FROM bars").fetchone()[0], 1)

    def test_05_revisions_preserve_historical_view(self):
        self.load(self.file())
        self.load(self.file("revision.csv", close="106",
                            first_available_at_utc="2026-10-05T22:00:00Z"))
        before = snapshot(self.db, "US:ETF:XYZ:RAW", "2026-10-04T00:00:00Z")
        after = snapshot(self.db, "US:ETF:XYZ:RAW", "2026-10-06T00:00:00Z")
        self.assertEqual(before[0]["close"], 105)
        self.assertEqual(after[0]["close"], 106)

    def test_06_conflicting_same_publication_rejected(self):
        self.load(self.file())
        with self.assertRaises(ValueError):
            self.load(self.file("conflict.csv", close="106"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM bars").fetchone()[0], 1)

    def test_07_unverified_data_excluded_from_research(self):
        self.load(self.file(), verified=False)
        self.assertEqual(snapshot(self.db, "US:ETF:XYZ:RAW",
                                  "2026-10-03T00:00:00Z"), [])
        self.assertEqual(len(snapshot(self.db, "US:ETF:XYZ:RAW",
                                      "2026-10-03T00:00:00Z",
                                      verified_only=False)), 1)

    def test_08_ohlc_validation(self):
        with self.assertRaises(ValueError):
            self.load(self.file(low="112"))
        with self.assertRaises(ValueError):
            self.load(self.file(volume="-1"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM bars").fetchone()[0], 0)

    def test_09_dataset_identity_separated(self):
        self.load(self.file())
        register_dataset(self.db, "US:ETF:ABC:RAW", "US:ETF:ABC",
                         "SyntheticTestProvider", "USD", "synthetic test fixture")
        self.assertEqual(snapshot(self.db, "US:ETF:ABC:RAW",
                                  "2026-10-03T00:00:00Z"), [])

    def test_10_indicator_warmup_and_ema(self):
        self.assertEqual(sma([1,2,3,4], 3), [None,None,2.0,3.0])
        self.assertEqual(ema([1,2,3,4], 3), [None,None,2.0,3.0])
        self.assertIsInstance(LIBRARY_VERSION, str)

    def test_11_wilder_rsi_semantics(self):
        self.assertEqual(rsi_wilder([100]*16, 14)[14], 50.0)
        self.assertEqual(rsi_wilder(list(range(1,17)), 14)[14], 100.0)
        self.assertEqual(rsi_wilder(list(range(17,1,-1)), 14)[14], 0.0)

    def test_12_wilder_atr_and_bad_values(self):
        vals = [100.0]*17
        self.assertEqual(atr_wilder([101]*17, [99]*17, vals, 14)[13], 2)
        with self.assertRaises(ValueError): sma([1.0, float("nan")], 2)
        with self.assertRaises(ValueError): atr_wilder([101], [99], [150], 1)

    def test_13_bad_date_keeps_database_empty(self):
        with self.assertRaises(ValueError):
            self.load(self.file(session="not-a-date"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM batches").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM bars").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
