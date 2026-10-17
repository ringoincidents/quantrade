import unittest
from dc_snapshot import analyze

NOW='2026-10-17T06:17:00+00:00'

def attempts():
    return [{'gallery':g,'alias':a,'queried_at_utc':'2026-10-17T06:12:00Z','method':'web_search_engine','status':'NO_SAME_DAY_VERIFIED','exhaustive':'false'} for g in ('stockus','krstock','tenbagger') for a in ('SOXL','속슬','속쓸')]

def post():
    return {'gallery':'stockus','post_url':'https://gall.dcinside.com/mgallery/board/view/?id=stockus&no=1','direction':'bullish','published_at_kst':'2026-10-02T18:59:50+09:00','first_seen_at_utc':'2026-10-17T06:13:00Z','collection_method':'retrospective_search','eligible_for_forward_test':'false','time_precision':'second'}

class Tests(unittest.TestCase):
    def test_no_false_zero_or_poll(self):
        r=analyze(attempts(),[],NOW)
        self.assertEqual(r['forward_eligible_records'],0)
        self.assertEqual(r['gallery_coverage']['stockus']['population_sentiment'],'UNKNOWN')
        self.assertEqual(r['status'],'DISCOVERY_SNAPSHOT_NOT_POLL')
    def test_historical_cannot_become_predictive(self):
        p=post();p['eligible_for_forward_test']='true'
        with self.assertRaises(ValueError):analyze(attempts(),[p],NOW)
    def test_future_firstseen_rejected(self):
        p=post();p['first_seen_at_utc']='2026-10-20T06:13:00Z'
        with self.assertRaises(ValueError):analyze(attempts(),[p],NOW)
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):analyze(attempts(),[post(),post()],NOW)
    def test_missing_alias_rejected(self):
        with self.assertRaises(ValueError):analyze(attempts()[:-1],[],NOW)
    def test_bad_engine_coverage(self):
        aa=attempts();aa[0]['exhaustive']='true'
        with self.assertRaises(ValueError):analyze(aa,[],NOW)
    def test_weekend_not_equated_to_exchange_tick(self):
        r=analyze(attempts(),[post()],NOW)
        self.assertEqual(r['soxl_market_session_status'],'WEEKEND_CLOSED')
    def test_naive_post_timestamp_rejected(self):
        p=post();p['published_at_kst']='2026-10-02T18:59:50'
        with self.assertRaises(ValueError):analyze(attempts(),[p],NOW)

if __name__=='__main__':unittest.main()
