import unittest, tempfile, json, sys, sqlite3
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"market_data_vault"))
from reference_store import open_private, ingest, observed_snapshot
from research.decision_review.budget_ledger import init, configure_day, reserve, settle
from research.decision_review.decision_review import Case

class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"vault.db"
        self.db=open_private(self.path)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda:self.db.close())
    def put(self,raw=None,**kwargs):
        return ingest(self.db,"FRED","DGS10",raw or b'{"observations":[{"date":"2026-01-05","value":"4.20"}]}',captured_at="2026-01-06T00:00:00Z",**kwargs)
    def test_no_rights(self):
        with self.assertRaisesRegex(ValueError,"RIGHTS"):
            self.put()
    def test_reopen_snapshot_and_idempotency(self):
        args=dict(rights_ref="fixture",rights_confirmed=True)
        h=self.put(**args);self.assertEqual(h,self.put(**args))
        self.db.close();self.db=open_private(self.path)
        before=observed_snapshot(self.db,"FRED","DGS10","2026-01-05T00:00:00Z")
        self.assertEqual(before["state"],"NOT_CAPTURED")
        after=observed_snapshot(self.db,"FRED","DGS10","2026-01-06T00:00:00Z")
        self.assertEqual(after["rows"][0][2],"4.20")
        self.assertFalse(after["pit_verified"])
    def test_tamper(self):
        self.put(rights_ref="fixture",rights_confirmed=True)
        with self.db:self.db.execute("UPDATE reference_rows SET value='99'")
        with self.assertRaisesRegex(ValueError,"INDEX_MISMATCH"):
            observed_snapshot(self.db,"FRED","DGS10","2026-01-07T00:00:00Z")
    def test_duplicate(self):
        raw=b'{"observations":[{"date":"2026-01-05","value":"4.20"},{"date":"2026-01-05","value":"4.21"}]}'
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            self.put(raw,rights_ref="fixture",rights_confirmed=True)
        self.assertEqual(self.db.execute("SELECT count(*) FROM reference_captures").fetchone()[0],0)
    def test_dart(self):
        data={"status":"000","list":[{"corp_code":"00126380","bsns_year":"2025","reprt_code":"11011","currency":"KRW","rcept_no":"20260301000001","sj_div":"BS","account_id":"ifrs-full_Assets","account_nm":"자산","thstrm_amount":"1,000"}]}
        ingest(self.db,"DART","00126380:2025:11011:CFS",json.dumps(data).encode(),captured_at="2026-04-01T00:00:00Z",rights_confirmed=True,rights_ref="fixture")
        result=observed_snapshot(self.db,"DART","00126380:2025:11011:CFS","2026-04-02T00:00:00Z")
        self.assertEqual(result["rows"][0][2:4],("1000","KRW"))

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        init(self.db)
        self.day=datetime.now(timezone.utc).date().isoformat()
        self.case=Case("NEW_HYPOTHESIS")
    def cfg(self,**kwargs):
        configure_day(self.db,self.day,**dict({"max_calls":4,"max_micro_usd":1000,"policy_ref":"fixture"},**kwargs))
    def req(self,**kwargs):
        args=dict(case_id="case1",request_id="req1",provider="OPENAI",model="test",prompt_sha="a"*64,author_provider="ANTHROPIC",scope="SYNTHETIC_APPROVED",provider_approved=True,tariff_ref="fixture",max_input=100,max_output=20,input_micro_per_million=1000000,output_micro_per_million=1000000)
        args.update(kwargs)
        return reserve(self.db,self.case,**args)
    def test_default_closed(self):
        with self.assertRaisesRegex(ValueError,"BUDGET_NOT_CONFIGURED"):self.req()
    def test_budget_ceiling(self):
        self.cfg(max_micro_usd=119)
        with self.assertRaises(ValueError):self.req()
    def test_scope(self):
        self.cfg()
        with self.assertRaises(ValueError):self.req(scope="UNKNOWN")
    def test_independence(self):
        self.cfg()
        with self.assertRaisesRegex(ValueError,"INDEPENDENCE"):self.req(author_provider="OPENAI")
    def test_reserve_and_report(self):
        self.cfg()
        r=self.req()
        self.assertEqual(r["reserved_micro_usd"],120)
        self.assertFalse(r["external_call_authorized"])
        self.assertEqual(settle(self.db,"req1",actual_input=30,actual_output=2,reported_micro_usd=32,receipt_sha="b"*64),"REPORTED")
        with self.assertRaises(ValueError):self.req(request_id="req2")
    def test_unknown_freeze(self):
        self.cfg();self.req()
        self.assertEqual(settle(self.db,"req1"),"UNKNOWN")
        with self.assertRaisesRegex(ValueError,"UNRECONCILED"):self.req(case_id="case2",request_id="req2")
    def test_routine_no_call(self):
        self.cfg();self.case=Case("REGRESSION_TEST")
        with self.assertRaises(ValueError):self.req()
    def test_daily_count(self):
        self.cfg(max_calls=1);self.req()
        with self.assertRaises(ValueError):self.req(case_id="case2",request_id="req2")
    def test_overrun(self):
        self.cfg();self.req()
        self.assertEqual(settle(self.db,"req1",actual_input=101,actual_output=2,reported_micro_usd=103,receipt_sha="b"*64),"UNKNOWN")

if __name__=="__main__":unittest.main()
