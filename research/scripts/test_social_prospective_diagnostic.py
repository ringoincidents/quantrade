import unittest
from social_prospective_diagnostic import prospective_features

BARS = [{'session_date':'2026-10-19',
         'open_utc':'2026-10-19T13:30:00Z','close_utc':'2026-10-19T20:00:00Z',
         'soxl_open':'90','soxl_close':'95','qqq_open':'700','qqq_close':'703'}]

class Tests(unittest.TestCase):
    def test_weekend_post_valid(self):
        p=[{'ticker':'SOXL','direction':'1','platform':'stocktwits', 'source_kind':'community',
            'published_utc':'2026-10-16T21:00:00Z','first_seen_utc':'2026-10-16T21:15:00Z'}]
        a=prospective_features(p,BARS)
        self.assertEqual(a[0]['n_messages'],1)
        self.assertAlmostEqual(a[0]['soxl_intraday_return_pct'],5.55556)
    def test_late_observation_not_backfilled(self):
        p=[{'ticker':'SOXL','direction':'1','platform':'reddit', 'source_kind':'community',
            'published_utc':'2026-10-16T21:00:00Z','first_seen_utc':'2026-10-19T15:00:00Z'}]
        self.assertEqual(prospective_features(p,BARS)[0]['n_messages'],0)
    def test_timestamp_naive_rejected(self):
        p=[{'ticker':'SOXL','direction':'1','platform':'stocktwits','published_utc':'2026-10-16T12:00:00','first_seen_utc':'2026-10-17T00:00:00Z'}]
        with self.assertRaises(ValueError): prospective_features(p,BARS)
    def test_no_future_posts(self):
        p=[{'ticker':'SOXL','direction':'-1','platform':'reddit','published_utc':'2026-10-19T13:20:00Z','first_seen_utc':'2026-10-19T13:20:00Z'}]
        self.assertEqual(prospective_features(p,BARS)[0]['n_messages'],0)
    def test_first_seen_must_follow_published(self):
        p=[{'ticker':'SOXL','direction':'0','platform':'stocktwits','published_utc':'2026-10-19T13:20:00Z','first_seen_utc':'2026-10-19T12:20:00Z'}]
        with self.assertRaises(ValueError): prospective_features(p,BARS)

if __name__ == '__main__': unittest.main()
