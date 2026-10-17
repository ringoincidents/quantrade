"""Offline, deterministic regressions for Darvas research-only event study."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
from darvas_box_pilot import Bar, describe, make_events, matched_controls


class DarvasPilotTests(unittest.TestCase):
    def test_empty_statistics_are_unknown(self):
        self.assertIsNone(describe([])["mean"])
        self.assertEqual(describe([{"ret": .2}, {"ret": -.1}])["n"], 2)

    def test_future_price_changes_do_not_alter_earlier_signals(self):
        bars = [Bar(f"2023-{i//28+1:02}-{i%28+1:02}",
                    100+i*.06, 101+i*.06, 99+i*.06, 100+i*.06, 100000)
                for i in range(360)]
        base, _ = make_events("TEST", bars)
        changed = bars[:-25] + [
            Bar(b.date, b.open*5, b.high*5, b.low*5, b.close*5, b.volume)
            for b in bars[-25:]]
        updated, _ = make_events("TEST", changed)
        self.assertEqual([(e["t"], e["type"]) for e in base if e["t"] < 335],
                         [(e["t"], e["type"]) for e in updated if e["t"] < 335])

    def test_always_rising_has_no_confirmed_box(self):
        bars = [Bar(f"{i:08}", 50+i*.2, 51+i*.2, 49+i*.2, 50+i*.2, 10000)
                for i in range(400)]
        events, _ = make_events("TEST", bars)
        self.assertFalse([e for e in events if e["type"] == "darvas"])

    def test_matches_respect_nonoverlap(self):
        def event(t, typ):
            return {"ticker": "TEST", "year": 2025, "date": f"2025-{t:03}",
                    "t": t, "type": typ, "ret": t/1000, "momentum60": .12,
                    "near252": .97, "volratio": 1.2}
        matched = matched_controls(
            [event(100, "darvas"), event(99, "eligible"),
             event(110, "eligible"), event(121, "eligible")], 2025)
        self.assertEqual(matched["matched_pairs"], 1)
        self.assertEqual(matched["pairs"][0]["control_date"], "2025-121")


if __name__ == "__main__":
    unittest.main()
