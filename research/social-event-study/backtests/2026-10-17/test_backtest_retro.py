import unittest
from backtest_retro import run,read_price,load_claims
from pathlib import Path
import os

BASE=Path(__file__).parent
DATA=Path(os.environ.get('QT_SOCIAL_DATA_DIR', BASE.parents[1] / '2026-10-17'))
PRICE=DATA/'soxl_daily_2026_selected.csv'
REDDIT=DATA/'manual_samples_v0.csv'

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prices=read_price(PRICE)
        cls.claims=load_claims(REDDIT,BASE/'handcoded_claims.csv')
        cls.summary,cls.raw,cls.groups=run(cls.prices,cls.claims)
    def test_no_future_first_seen_eligible(self):
        self.assertEqual(self.summary['all_historical_first_seen_verified_count'],0)
        self.assertTrue(all(x['eligible_for_live_replay'] is False for x in self.raw))
    def test_dated_post_not_at_same_day_close(self):
        a=next(x for x in self.raw if x['id']=='META-006')
        self.assertEqual(a['date'],'2026-10-02')
        self.assertEqual(a['anchor_date'],'2026-10-05')
        self.assertAlmostEqual(a['return_5d_pct'],-21.836,places=2)
    def test_weekend_post_waits_until_monday_close(self):
        a=next(x for x in self.raw if x['id']=='DC-012')
        self.assertEqual(a['anchor_date'],'2026-09-28')
    def test_missing_data_cannot_bridge_calendar_gap(self):
        a=next(x for x in self.raw if x['id']=='META-005')
        self.assertAlmostEqual(a['return_5d_pct'],22.2542,places=3)
        # Insert an imaginary August 7 claim; five-session result cannot jump to Sept 8.
        fake=[dict(id='gap',platform='reddit',date='2026-08-06',thread='https://example.org/test',layer='meta',direction=1,category='test')]
        _, rows, _ = run(self.prices,fake)
        self.assertIsNone(rows[0]['return_5d_pct'])
    def test_unavailable_future_not_zero(self):
        a=next(x for x in self.raw if x['id']=='O04')
        self.assertIsNone(a['return_1d_pct'])
    def test_duplicate_comments_one_thread_group(self):
        a=[x for x in self.groups if '1wghryt' in x['thread']]
        self.assertEqual(len(a),1)
        self.assertEqual(a[0]['n_claims'],4)
    def test_meta_horizon_sensitivity(self):
        m=self.summary['group_summary']['meta']
        self.assertEqual(m['1']['n_directionally_correct'],4)
        self.assertEqual(m['5']['n_directionally_correct'],2)
        self.assertEqual(m['5']['n_evaluable_directional_units'],3)
    def test_neutral_discourse_not_market_signal(self):
        a=next(x for x in self.groups if '1wg493q' in x['thread'])
        self.assertEqual(a['net_direction'],0)
        self.assertIsNone(a['correct_1d'])
    def test_source_size(self):
        self.assertEqual(self.summary['claims_total'],37)
        self.assertEqual(self.summary['price_sessions_available'],44)

if __name__=='__main__':unittest.main()