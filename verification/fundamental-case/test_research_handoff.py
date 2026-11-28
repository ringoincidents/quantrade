import unittest,threading,http.client,time
from datetime import datetime,timezone
from worker import Work,Server
from research_link import fetch,validate,PATH,Verifier,request_message,mac

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
        self.work=Work();self.work.result=fixture()
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
    def test_wrong_key(self):
        self.assertEqual(fetch("b"*64,connection_factory=self.conn)["state"],"WORKER_PENDING_OR_REJECTED")
    def test_unsigned(self):
        c=self.conn();c.request("GET",PATH);self.assertEqual(c.getresponse().status,403);c.close()
    def test_pending(self):
        self.work.result={"state":"PENDING"}
        self.assertEqual(fetch(KEY,connection_factory=self.conn)["state"],"WORKER_PENDING_OR_REJECTED")
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
