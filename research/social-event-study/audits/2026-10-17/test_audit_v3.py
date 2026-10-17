import unittest
from pathlib import Path
from audit_v3 import read_csv,report,values

CSV=Path(__file__).resolve().parents[2]/'backtests/2026-10-17/extended_thread_day_results.csv'
class AuditTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows=read_csv(CSV);cls.s=report(cls.rows)
 def test_four_evaluable_meta(self):self.assertEqual(self.s['horizons']['1']['meta_all_descriptive']['n'],4)
 def test_two_overlapping_event_clusters(self):self.assertEqual(self.s['horizons']['1']['meta_overlapping_cluster_count'],2)
 def test_naive_four_of_four(self):self.assertEqual(self.s['horizons']['1']['meta_all_descriptive']['direction_matches'],4)
 def test_one_percent_filters_two(self):self.assertEqual(self.s['horizons']['1']['meta_all_descriptive']['threshold_matches'],2)
 def test_two_forward_meta_hypotheses(self):
  self.assertEqual(self.s['horizons']['1']['meta_strict_only']['n'],2)
  self.assertEqual(self.s['horizons']['1']['meta_strict_only']['threshold_matches'],1)
 def test_thread_duplicates_collapsed(self):
  self.assertEqual(self.s['horizons']['1']['direct_thread_day_descriptive']['n'],15)
  self.assertEqual(self.s['horizons']['1']['direct_publication_day_collapsed']['n'],13)
 def test_paired_dates(self):
  self.assertEqual(self.s['horizons']['1']['paired_meta_and_direct_publication_dates'],['2026-07-30','2026-10-02'])
 def test_2022_not_backfilled(self):
  self.assertEqual(len([r for r in self.rows if r['year']=='2022' and values(r,1) is not None]),0)
 def test_audit_not_trading(self):self.assertIn('NOT_A_TRADING_BACKTEST',self.s['status'])
 def test_firstseen_unverified(self):self.assertTrue(all(r['historical_first_seen']=='NOT_VERIFIED' for r in self.rows))
if __name__=='__main__':unittest.main()
