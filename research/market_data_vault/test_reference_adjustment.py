import unittest,csv,tempfile
from pathlib import Path
from vault import connect,register_dataset,ingest_csv
from reference_adjustment import reference_plan,build_reference_bundle,Blocked

class ReferenceAdjustmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=connect(self.root/"vault.db");self.addCleanup(self.db.close)
        register_dataset(self.db,"DEMO","XNYS:DEMO","SyntheticTestProvider","USD","fixture")
        self.at="2026-11-28T06:00:00Z"
        self.plan=reference_plan("DEMO","XNYS","2026-11-23","2026-11-27",self.at,"fixture:actions",split=True)
        self.manifest={"schema":"qt-split-manifest-v1","dataset_id":"DEMO","asset_id":"XNYS:DEMO","market":"XNYS",
            "coverage_start":"2026-11-23","coverage_end":"2026-11-27","coverage_known_at":"2026-11-28T05:00:00Z",
            "coverage_state":"ALL_ACTIONS_DECLARED","source_ref":"fixture:actions","events":[
            {"kind":"SPLIT","effective_session":"2026-11-25","first_known_at":"2026-11-24T12:00:00Z",
            "effective_basis":"BEFORE_SESSION_OPEN","new_shares":2,"old_shares":1,"event_ref":"fixture:split"}]}
        self.load()
    def load(self):
        p=self.root/"bars.csv"
        with p.open("w",newline="") as f:
            w=csv.writer(f);w.writerow(["session","open","high","low","close","volume","first_available_at_utc"])
            for s in self.plan["sessions"]:
                d=s["session"];v=100 if d<"2026-11-25" else 50
                w.writerow([d,v,v,v,v,10 if v==100 else 20,d+("T18:01:00Z" if d=="2026-11-27" else "T21:01:00Z")])
        ingest_csv(self.db,p,dataset_id="DEMO",source_uri="fixture:test",usage_rights_confirmed=True,availability_verified=True)
        # Set captured_at to a valid deterministic synthetic timestamp; real capture
        # is not fabricated or modified by the adjustment implementation.
        with self.db:self.db.execute("UPDATE batches SET captured_at=?",("2026-11-28T06:00:00+00:00",))
    def run_bundle(self):
        return build_reference_bundle(self.db,"DEMO","XNYS","2026-11-23","2026-11-27",self.at,self.manifest)
    def test_reference_thanksgiving(self):
        self.assertEqual(self.plan["closed_dates"],["2026-11-26"])
        self.assertEqual(self.plan["sessions"][-1]["close_at"],"2026-11-27T13:00:00-05:00")
        self.assertEqual(len(self.plan["sessions"]),4)
    def test_no_unfinished_early_close(self):
        with self.assertRaisesRegex(Blocked,"SESSION_NOT_COMPLETED"):
            reference_plan("DEMO","XNYS","2026-11-23","2026-11-27","2026-11-27T17:59:00Z","fixture")
    def test_no_extrapolation(self):
        for market,start in (("XKRX","2026-11-23"),("XNYS","2026-11-22")):
            with self.assertRaises(Blocked):reference_plan("DEMO",market,start,"2026-11-27",self.at,"fixture")
    def test_split_ohlcv_and_raw_unchanged(self):
        v=self.run_bundle();self.assertEqual([b["close"] for b in v["bars"]],[50]*4)
        self.assertEqual([b["volume"] for b in v["bars"]],[20]*4)
        self.assertEqual(v["features"]["PRICE_RETURN:1"]["value"],0)
        self.assertEqual(self.db.execute("SELECT close FROM bars ORDER BY session").fetchall(),[(100.0,),(100.0,),(50.0,),(50.0,)])
        self.assertFalse(v["total_return"]);self.assertFalse(v["g0_approved"])
        self.assertEqual(v["snapshot_sha256"],self.run_bundle()["snapshot_sha256"])
    def test_unknown_action_coverage(self):
        self.manifest["coverage_state"]="UNKNOWN"
        with self.assertRaisesRegex(Blocked,"ACTION_COVERAGE_UNVERIFIED"):self.run_bundle()
    def test_dividend_blocks(self):
        self.manifest["events"][0]["kind"]="DIVIDEND"
        with self.assertRaisesRegex(Blocked,"UNSUPPORTED_CORPORATE_ACTION"):self.run_bundle()
    def test_future_action_knowledge_blocks(self):
        self.manifest["events"][0]["first_known_at"]="2026-11-29T00:00:00Z"
        with self.assertRaisesRegex(Blocked,"ACTION_NOT_KNOWN_AS_OF"):self.run_bundle()
    def test_invalid_split_ratio(self):
        self.manifest["events"][0]["new_shares"]=0
        with self.assertRaisesRegex(Blocked,"INVALID_SPLIT_RATIO"):self.run_bundle()
    def test_duplicate_action_blocks(self):
        self.manifest["events"]*=2
        with self.assertRaisesRegex(Blocked,"ACTION_SESSION_INVALID_OR_DUPLICATE"):self.run_bundle()
    def test_wrong_asset(self):
        self.manifest["asset_id"]="OTHER"
        with self.assertRaisesRegex(Blocked,"ACTION_IDENTITY_MISMATCH"):self.run_bundle()
    def test_missing_bar(self):
        self.db.execute("DELETE FROM bars WHERE session='2026-11-24'")
        with self.assertRaisesRegex(Blocked,"MISSING_SESSION"):self.run_bundle()
