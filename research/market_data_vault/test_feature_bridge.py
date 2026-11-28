import csv
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from vault import connect,register_dataset,ingest_csv
from feature_bridge import build_bundle,Blocked

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=connect(self.root/"vault.db");self.addCleanup(self.db.close)
        self.dataset="SYNTHETIC:RAW"
        register_dataset(self.db,self.dataset,"DEMO","SyntheticTestProvider","USD","fixture rights")
        self.sessions=[]
        rows=[]
        d=date(2026,1,1)
        for i in range(26):
            day=(d+timedelta(days=i)).isoformat()
            self.sessions.append({"session":day,"close_at":day+"T21:00:00Z"})
            rows.append([day,100+i,101+i,99+i,100+i,1000,day+"T21:01:00Z"])
        self.load("initial",rows)
        self.plan={"dataset_id":self.dataset,"timezone":"America/New_York","calendar_ref":"fixture:calendar",
            "corporate_action_ref":"fixture:actions","corporate_action_state":"NO_ACTIONS_IN_WINDOW","sessions":self.sessions}
    def load(self,name,rows,verified=True):
        p=self.root/(name+".csv")
        with p.open("w",newline="") as f:
            w=csv.writer(f);w.writerow(["session","open","high","low","close","volume","first_available_at_utc"]);w.writerows(rows)
        ingest_csv(self.db,p,dataset_id=self.dataset,source_uri="synthetic://fixture",usage_rights_confirmed=True,availability_verified=verified)
    def run_bundle(self,asof="2026-02-01T00:00:00Z"):
        return build_bundle(self.db,self.dataset,asof,self.plan)
    def test_reuse_indicators_and_warmup(self):
        v=self.run_bundle();f=v["features"]
        self.assertEqual(v["input_count"],26)
        self.assertEqual(f["SMA:25"]["value"],113.0)
        self.assertAlmostEqual(f["DISPARITY:25"]["value"],100*125/113)
        self.assertEqual(f["RSI:WILDER:14"]["value"],100)
        self.assertEqual(f["ATR:WILDER:14"]["value"],2)
        self.assertEqual(f["SMA:200"]["state"],"WARMUP")
        self.assertEqual(f["VOLUME_RATIO:20"]["value"],1)
        self.assertEqual(f["CMF:20"]["value"],0)
        self.assertEqual(f["MACD:12:26:9:signal"]["state"],"WARMUP")
        self.assertIsNotNone(f["BOLLINGER:20:2:width"]["value"])
        self.assertIsNone(f["PRICE_RETURN:60"]["value"])
        self.assertFalse(v["g0_approved"]);self.assertFalse(v["decision_authorized"])
        self.assertEqual(v["snapshot_sha256"],self.run_bundle()["snapshot_sha256"])
    def test_revision_changes_hash_only_after_known(self):
        original=self.run_bundle()
        self.load("revision", [["2026-01-26",125,127,124,126,1000,"2026-02-02T00:00:00Z"]])
        self.assertEqual(self.run_bundle()["snapshot_sha256"],original["snapshot_sha256"])
        newer=self.run_bundle("2026-02-03T00:00:00Z")
        self.assertNotEqual(newer["snapshot_sha256"],original["snapshot_sha256"])
        self.assertAlmostEqual(newer["features"]["SMA:25"]["value"],113.04)
    def test_unverified_latest_blocks_no_fallback(self):
        self.load("unverified",[["2026-01-26",125,127,124,126,1000,"2026-02-02T00:00:00Z"]],False)
        with self.assertRaisesRegex(Blocked,"LATEST_REVISION_UNVERIFIED"):self.run_bundle("2026-02-03T00:00:00Z")
    def test_session_gap(self):
        self.db.execute("DELETE FROM bars WHERE session='2026-01-13'")
        with self.assertRaisesRegex(Blocked,"MISSING_SESSION"):self.run_bundle()
    def test_unexpected_session(self):
        self.plan["sessions"]=self.sessions[:5]+self.sessions[6:]
        with self.assertRaisesRegex(Blocked,"UNEXPECTED_SESSION"):self.run_bundle()
    def test_raw_action_unresolved(self):
        self.plan["corporate_action_state"]="UNKNOWN"
        with self.assertRaisesRegex(Blocked,"RAW_ACTIONS_UNRESOLVED"):self.run_bundle()
    def test_future_close_rejected(self):
        with self.assertRaisesRegex(Blocked,"SESSION_CLOSE_INVALID"):self.run_bundle("2026-01-25T00:00:00Z")
    def test_no_missing_batch_provenance(self):
        self.db.execute("DELETE FROM batches")
        with self.assertRaisesRegex(Blocked,"BATCH_PROVENANCE_MISSING"):self.run_bundle()
    def test_no_fixture_as_real(self):
        with self.assertRaisesRegex(Blocked,"FIXTURE_IN_RESEARCH_MODE"):
            build_bundle(self.db,self.dataset,"2026-02-01T00:00:00Z",self.plan,mode="RESEARCH_CANDIDATE")
    def test_before_close_rejected(self):
        self.load("early",[["2026-01-26",125,126,124,125,1000,"2026-01-26T20:59:00Z"]])
        with self.assertRaisesRegex(Blocked,"PRICE_BEFORE_CLOSE"):self.run_bundle()
