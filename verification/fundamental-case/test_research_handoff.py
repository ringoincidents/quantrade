import unittest,threading,http.client,time
from datetime import datetime,timezone
from worker import Work,Server
from research_link import fetch,validate,validate_work,PATH,Verifier,request_message,mac
from work_lifecycle import Lifecycle

KEY="fixture_"+("a"*56)
def fixture():
    return {"state":"REPORT_READY","asset_id":"KRX:005930","period":"2025-12-31","metric_unit":"KRW_TRILLION",
        "independent_review":"PENDING","accounting_identity_check":"PASS_WITHIN_1000_KRW",
        "valuation_authority":False,"portfolio_authority":False,"trade_authority":False,
        "filing_ref":"20260310002820","publication_date_eod":"2026-03-10T23:59:59+09:00",
        "observed_at":datetime.now(timezone.utc).isoformat(),
        "metrics":{"assets":"300.000","liabilities":"100.000","equity":"200.000","revenue":"150.000","operating_income":"30.000","net_income":"15.000"},
        "ratios":{"operating_margin_pct":"20.00","net_margin_pct":"10.00","liabilities_to_equity_pct":"50.00"}}
class Tests(unittest.TestCase):
    def setUp(self):
        self.work=Work();self.work.lifecycle=Lifecycle(launch=lambda target:target())
        self.work.lifecycle.dispatch(fixture)
        self.s=Server(("127.0.0.1",0),KEY,self.work)
        self.t=threading.Thread(target=self.s.serve_forever,daemon=True);self.t.start()
    def tearDown(self):
        self.s.shutdown();self.s.server_close();self.t.join(2)
    def conn(self,*a,**kw):
        return http.client.HTTPConnection("127.0.0.1",self.s.server_port,timeout=3)
    def test_signed_report(self):
        r=fetch(KEY,connection_factory=self.conn)
        self.assertEqual(r["handoff"],"AUTHENTICATED_INTERNAL_REPORT")
        self.assertFalse(r["trade_authority"])
        self.assertEqual(r["workflow"]["state"],"REVIEW_BLOCKED")
        self.assertFalse(r["workflow"]["approved"])
    def test_wrong_key(self):
        self.assertEqual(fetch("b"*64,connection_factory=self.conn)["state"],"WORKER_PENDING_OR_REJECTED")
    def test_unsigned(self):
        c=self.conn();c.request("GET",PATH);self.assertEqual(c.getresponse().status,403);c.close()
    def test_pending(self):
        self.work.lifecycle=Lifecycle(launch=lambda target:None)
        self.assertEqual(fetch(KEY,connection_factory=self.conn)["state"],"RUNNING")
    def test_replay(self):
        v=Verifier(KEY);stamp=str(int(time.time()));nonce="1"*32;sig=mac(v.key,request_message(stamp,nonce))
        self.assertTrue(v.verify(stamp,nonce,sig));self.assertFalse(v.verify(stamp,nonce,sig))
    def test_stale(self):
        r=fixture();r["observed_at"]="2025-12-31T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"STALE"):validate(r)
    def test_ratios_and_authority(self):
        r=fixture();r["ratios"]["net_margin_pct"]="99.00"
        with self.assertRaisesRegex(ValueError,"RATIO"):validate(r)
        r=fixture();r["trade_authority"]=True
        with self.assertRaisesRegex(ValueError,"AUTHORITY"):validate(r)

class LifecycleTests(unittest.TestCase):
    def test_refresh_cooldown_and_cap(self):
        now=[time.time()]
        work=Lifecycle(clock=lambda:now[0],launch=lambda target:target())
        self.assertTrue(work.dispatch(fixture))
        self.assertFalse(work.dispatch(fixture))
        now[0]+=3600
        self.assertTrue(work.dispatch(fixture))
        now[0]+=3600
        self.assertFalse(work.dispatch(fixture))
        self.assertEqual(work.snapshot()["runs"],2)
    def test_inflight_guard(self):
        pending=[]
        work=Lifecycle(launch=pending.append)
        self.assertTrue(work.dispatch(fixture))
        self.assertFalse(work.dispatch(fixture))
        pending[0]()
        self.assertEqual(work.snapshot()["state"],"REVIEW_BLOCKED")
    def test_failed_job(self):
        work=Lifecycle(launch=lambda target:target())
        work.dispatch(lambda:{"state":"BLOCKED"})
        self.assertEqual(work.snapshot()["state"],"FAILED")
        self.assertIsNone(work.snapshot()["report"])
    def test_tampered_digest(self):
        work=Lifecycle(launch=lambda target:target())
        work.dispatch(fixture)
        w=work.snapshot()
        w["report"]["metrics"]["assets"]="999.000"
        with self.assertRaisesRegex(ValueError,"WORK_HASH"):validate_work(w)
    def test_no_approval(self):
        work=Lifecycle(launch=lambda target:target())
        work.dispatch(fixture)
        w=work.snapshot();w["approved"]=True
        with self.assertRaisesRegex(ValueError,"WORK_AUTHORITY"):validate_work(w)
    def test_invalid_sequence(self):
        work=Lifecycle(launch=lambda target:target())
        work.dispatch(fixture)
        w=work.snapshot();w["events"][1]["state"]="ACCEPTED"
        with self.assertRaisesRegex(ValueError,"WORK_SEQUENCE"):validate_work(w)
