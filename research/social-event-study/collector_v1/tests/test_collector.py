import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from collector import collect,gdelt_url,gdelt_articles,naver_series,iso
UTC=dt.timezone.utc
NOW=dt.datetime(2026,10,17,8,30,tzinfo=UTC)
ART={'articles':[{'url':'https://example.com/chip-a','seendate':'20261017T080000Z'},
                 {'url':'https://example.com/chip-b','seendate':'20261017T080500Z'}]}
class Tests(unittest.TestCase):
 def test_window_bounded(self):
  with self.assertRaises(ValueError):gdelt_url('SOXL',NOW-dt.timedelta(days=3),NOW)
 def test_seen_not_publish(self):
  a=gdelt_articles('SOXL',ART,iso(NOW),{})
  self.assertEqual(a[0]['gdelt_seendate_utc'],'2026-10-17T08:00:00Z')
  self.assertIsNone(a[0]['published_utc'])
  self.assertFalse(a[0]['predictive_eligible'])
 def test_bad_url_discarded(self):
  self.assertEqual(gdelt_articles('x',{'articles':[{'url':'/not-public'}]},iso(NOW),{}),[])
 def test_retained_first_seen(self):
  with tempfile.TemporaryDirectory() as t:
   collect(NOW,t,http=lambda u,**kw:ART)
   collect(NOW+dt.timedelta(hours=1),t,http=lambda u,**kw:ART)
   x=[json.loads(p.read_text()) for p in sorted(Path(t).rglob('news_metadata.json'))]
   self.assertEqual(len(x),2)
   self.assertEqual(x[0][0]['first_seen_utc'],x[1][0]['first_seen_utc'])
 def test_failure_recorded(self):
  with tempfile.TemporaryDirectory() as t:
   def fail(u,**kw):raise ValueError('mock failure')
   r=collect(NOW,t,http=fail)
   self.assertEqual(r['queries']['leveraged_semis']['status'],'FAILED')
   self.assertEqual(r['usable_price_predictions'],0)
 def test_no_naver_secret_missing(self):
  with tempfile.TemporaryDirectory() as t:
   with patch.dict(os.environ,{'NAVER_CLIENT_ID':'','NAVER_CLIENT_SECRET':''}):
    r=collect(NOW,t,http=lambda u,**kw:ART,use_naver=True)
   self.assertEqual(r['naver']['status'],'NO_CREDENTIALS_NOT_FETCHED')
 def test_no_secrets_in_public_data(self):
  with tempfile.TemporaryDirectory() as t:
   with patch.dict(os.environ,{'NAVER_CLIENT_ID':'secret-id','NAVER_CLIENT_SECRET':'secret-password'}):
    def mock(url,**kw):return {'results':[]} if 'naver' in url else ART
    collect(NOW,t,http=mock,use_naver=True)
   content=' '.join(p.read_text() for p in Path(t).rglob('*.json'))
   self.assertNotIn('secret-password',content)
   self.assertNotIn('secret-id',content)
 def test_naver_is_not_forum(self):
  d=naver_series({'results':[{'title':'SOXL/속슬','data':[{'period':'2026-10-10','ratio':89}]}]},iso(NOW),'year')
  self.assertEqual(d[0]['ratio'],89)
  self.assertFalse(d[0]['predictive_eligible'])
 def test_dry_run_no_external_calls(self):
  with tempfile.TemporaryDirectory() as t:
   def explode(*a,**kw):raise AssertionError('unexpected network')
   r=collect(NOW,t,http=explode,dry_run=True)
   self.assertEqual(r['queries']['leveraged_semis']['status'],'DRY_RUN_NOT_FETCHED')
 def test_zero_hits_not_zero_posts(self):
  with tempfile.TemporaryDirectory() as t:
   r=collect(NOW,t,http=lambda u,**kw:{'articles':[]})
   self.assertEqual(r['social_forum_api_access'],'NOT_AUTHORIZED')
   self.assertEqual(r['live_forum_posts_ingested'],0)
if __name__=='__main__':unittest.main()
