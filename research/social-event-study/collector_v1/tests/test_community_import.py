import unittest
from community_import import record

def example(**kw):
 d={'source_url':'https://example.com/public-forum/post-1','platform':'dc_stockus',
    'level':'L2','direction':'bearish','category':'herd_warning',
    'collection_mode':'retrospective_manual','rights_status':'public_link_only',
    'published_utc':'2026-10-16T09:00:00Z','first_observed_utc':'2026-10-17T08:00:00Z',
    'label_locked_utc':'2026-10-17T08:01:00Z'}
 d.update(kw);return d
class Tests(unittest.TestCase):
 def test_retrospective_not_predictive(self):
  r=record(example(),set());self.assertFalse(r['predictive_eligible'])
 def test_duplicate(self):
  s=set();record(example(),s)
  with self.assertRaises(ValueError):record(example(),s)
 def test_source_time(self):
  with self.assertRaises(ValueError):record(example(first_observed_utc='2026-10-15T08:00:00Z'),set())
 def test_rights(self):
  with self.assertRaises(ValueError):record(example(rights_status='unknown'),set())
 def test_even_live_manual_has_no_complete_population(self):
  r=record(example(collection_mode='authorized_manual_live',rights_status='authorized_metadata'),set())
  self.assertFalse(r['representative_population']);self.assertFalse(r['predictive_eligible'])
 def test_privacy(self):
  r=record(example(),set());self.assertNotIn('username',r);self.assertNotIn('raw_body',r)
if __name__=='__main__':unittest.main()
