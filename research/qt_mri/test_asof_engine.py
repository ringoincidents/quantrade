"""Synthetic tests only. Passing these does not show real-world predictive value."""
import tempfile
import csv
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from asof_engine import (Release, Close, utc, asof_panel, vix_crosses,
                         hy_turns, combine_events, evaluate_forward,
                         read_releases)


def stamp(day, hour=21):
    return datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=day, hours=hour)


class TestPITGuard(unittest.TestCase):
    def test_refuse_missing_or_naive_publication(self):
        for value in ["", "UNKNOWN", "2020-01-01T12:00:00"]:
            with self.assertRaises(ValueError): utc(value)

    def test_known_only_after_release(self):
        prices = [Close("D1", 100, stamp(1)), Close("D2", 101, stamp(2)),
                  Close("D3", 99, stamp(3))]
        releases = [Release("VIXCLS", "day1", 20, stamp(2, 22))]
        observed = asof_panel(prices, releases, "VIXCLS")
        self.assertIsNone(observed[0])
        self.assertIsNone(observed[1])
        self.assertEqual(observed[2].value, 20)

    def test_no_prohibited_credit_proxy_splice(self):
        prices = [Close("D1", 100, stamp(1))]
        with self.assertRaises(ValueError):
            asof_panel(prices, [Release("BAA10Y", "D1", 2, stamp(0))], "BAMLH0A0HYM2")
        with self.assertRaises(ValueError): hy_turns([], "DBAA")

    def test_input_requires_reliable_release_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("series_id,observation_date,value,first_public_at_utc\nVIXCLS,2020-01-01,35,UNKNOWN\n")
            with self.assertRaises(ValueError): read_releases(str(path), "VIXCLS")

    def test_vix_cross_once_not_forward_filled(self):
        vals = [20, 20, 32, 32, 29, 31]
        times = [stamp(0),stamp(0),stamp(2),stamp(2),stamp(4),stamp(5)]
        r = [Release("VIXCLS", "X", v, t) for v, t in zip(vals, times)]
        self.assertEqual(vix_crosses(r), [2])
        recover = r[:3] + [Release("VIXCLS", "X", 19, stamp(i)) for i in range(3, 13)] + [Release("VIXCLS", "X", 31, stamp(13))]
        self.assertEqual(vix_crosses(recover), [2, 13])

    def test_credit_turn_uses_past_and_bp_units(self):
        aligned = [Release("BAA10Y", str(i), 1.0 + 0.001*i, stamp(i)) for i in range(260)]
        for i in range(260, 269):
            aligned.append(Release("BAA10Y", str(i), 2.6 - (i-260)*0.06, stamp(i)))
        ev = hy_turns(aligned, "BAA10Y", lookback=252)
        self.assertTrue(ev)
        self.assertTrue(all(i >= 252 for i in ev))

    def test_combination_only_when_credit_later(self):
        self.assertEqual(combine_events([2, 40], [1, 3, 35, 41, 80]), [3, 41])

    def test_no_future_price_at_signal(self):
        prices = [Close(f"D{i}", 100+i, stamp(i)) for i in range(70)]
        a = evaluate_forward(prices, [0, 68], [5, 60])
        self.assertEqual(a["5"]["n"], 1)
        self.assertEqual(a["60"]["n"], 1)
        self.assertAlmostEqual(a["5"]["events"][0]["future_return"], .05)
        self.assertLessEqual(a["5"]["events"][0]["max_adverse_excursion"], 0)


if __name__ == "__main__": unittest.main()
