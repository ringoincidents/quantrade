import unittest
import tempfile
import csv
from pathlib import Path
from event_phases import run

class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parent

    def test_pilot_runs_and_unknown_after(self):
        d=run(self.root/'soxl_daily_2026_selected.csv', self.root/'events_curated_v0.csv',self.root/'manual_samples_v0.csv')
        self.assertEqual(d['data']['predictive_eligible'],0)
        self.assertFalse(d['events'][2]['complete_after_window'])
        self.assertEqual(d['events'][2]['phases']['after']['observations'],0)
        self.assertNotIn('p_value',repr(d))

    def test_duplicate_id_fails(self):
        # Use existing pilot as a baseline and ensure repeated samples can't silently count twice.
        text=(self.root/'manual_samples_v0.csv').read_text()
        dup=text+'\n'+text.splitlines()[1]+'\n'
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'dup.csv';p.write_text(dup)
            with self.assertRaises(ValueError):run(self.root/'soxl_daily_2026_selected.csv',self.root/'events_curated_v0.csv',p)

    def test_date_only_cannot_be_forward_signal(self):
        text=(self.root/'manual_samples_v0.csv').read_text().replace('date,false','date,true',1)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'leak.csv';p.write_text(text)
            with self.assertRaises(ValueError):run(self.root/'soxl_daily_2026_selected.csv',self.root/'events_curated_v0.csv',p)

    def test_no_daily_price_duplicate(self):
        txt=(self.root/'soxl_daily_2026_selected.csv').read_text()
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'prices.csv';p.write_text(txt+'\n'+txt.splitlines()[1]+'\n')
            with self.assertRaises(ValueError):run(p,self.root/'events_curated_v0.csv',self.root/'manual_samples_v0.csv')

if __name__=='__main__':unittest.main()