import unittest
from datetime import timedelta
from forward_maturity import paper_horizon,session_list

DECISION='2026-10-17T08:00:00Z'
SIG={'state':'FEATURES_ONLY_NO_TRADE','decision_cutoff_utc':DECISION,
     'features_locked_at_utc':'2026-10-17T07:40:00Z'}
EVAL='2026-10-26T10:00:00Z'
def bars():
 out=[]
 for k,(date,op,cl) in enumerate(session_list(DECISION,EVAL,5)):
  out.append({'session_date':date,'open':100+k,'close':101+k,'source_verified':True,
       'corporate_actions_verified':True,'session_open_utc':op.isoformat(),
       'session_close_utc':cl.isoformat(),
       'price_first_observed_utc':(cl+timedelta(minutes=2)).isoformat()})
 return out
class Tests(unittest.TestCase):
 def test_matured_all(self):
  r=paper_horizon(SIG,bars(),EVAL)
  self.assertTrue(all(r['horizons'][str(h)]['state']=='PAPER_OUTCOME_ONLY' for h in (1,3,5)))
  self.assertEqual(r['horizons']['1']['start_session'],'2026-10-19')
 def test_no_future(self):
  r=paper_horizon(SIG,bars(),'2026-10-20T10:00:00Z')
  self.assertEqual(r['horizons']['3']['state'],'AWAITING_FUTURE_CLOSE')
 def test_gap_rejected(self):
  b=bars();b.pop(2)
  self.assertEqual(paper_horizon(SIG,b,EVAL)['horizons']['5']['state'],'MISSING_SESSION_PRICE')
 def test_unverified(self):
  b=bars();b[0]['source_verified']=False
  self.assertEqual(paper_horizon(SIG,b,EVAL)['horizons']['1']['state'],'UNVERIFIED_PRICE_SOURCE')
 def test_wrong_clock(self):
  b=bars();b[0]['session_open_utc']='2026-10-19T15:00:00Z'
  self.assertEqual(paper_horizon(SIG,b,EVAL)['horizons']['1']['state'],'CLOCK_DISAGREEMENT')
 def test_duplicate(self):
  b=bars();b.append(b[0])
  with self.assertRaises(ValueError):paper_horizon(SIG,b,EVAL)
 def test_no_signal(self):self.assertEqual(paper_horizon({'state':'NO_SIGNAL'},bars(),EVAL)['status'],'NO_SIGNAL')
 def test_late_label(self):
  s=SIG|{'features_locked_at_utc':'2026-10-17T07:50:00Z'}
  self.assertEqual(paper_horizon(s,bars(),EVAL)['status'],'INVALID_FEATURE_LOCK')
 def test_price_from_future(self):
  b=bars();b[0]['price_first_observed_utc']='2026-10-28T00:00:00Z'
  self.assertEqual(paper_horizon(SIG,b,EVAL)['horizons']['1']['state'],'INVALID_PRICE_OBSERVATION_TIME')
 def test_15min_buffer(self):
  s={'state':'FEATURES_ONLY_NO_TRADE','decision_cutoff_utc':'2026-10-19T13:20:00Z',
     'features_locked_at_utc':'2026-10-19T13:00:00Z'}
  self.assertEqual(paper_horizon(s,bars(),EVAL)['horizons']['1']['start_session'],'2026-10-20')
if __name__=='__main__':unittest.main()
