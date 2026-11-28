import unittest
import tempfile
import csv
from pathlib import Path
from datetime import date,timedelta
from vault import connect,register_dataset,ingest_csv
from multiframe import build_multiframe,Blocked

class MultiframeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=connect(self.root/"v.db");self.addCleanup(self.db.close)
        self.dataset="DEMO"
        register_dataset(self.db,self.dataset,"DEMO","SyntheticTestProvider","USD","fixture")
    def plan(self,start,end,skip=()):
        lo,hi=date.fromisoformat(start),date.fromisoformat(end)
        sessions=[];rows=[]
        for i in range((hi-lo).days+1):
            d=lo+timedelta(days=i);s=d.isoformat()
            if d.weekday()>=5 or s in skip:continue
            sessions.append({"session":s,"close_at":s+"T21:00:00Z"})
            p=100+len(rows);rows.append([s,p,p+2,p-1,p+1,10,s+"T21:01:00Z"])
        self.ingest("initial",rows)
        return {"dataset_id":self.dataset,"timezone":"America/New_York","coverage_start":start,"coverage_end":end,
            "calendar_ref":"fixture:calendar","corporate_action_ref":"fixture:actions",
            "corporate_action_state":"NO_ACTIONS_IN_WINDOW","sessions":sessions}
    def ingest(self,name,rows,verified=True):
        p=self.root/(name+".csv")
        with p.open("w",newline="") as f:
            w=csv.writer(f);w.writerow(["session","open","high","low","close","volume","first_available_at_utc"]);w.writerows(rows)
        ingest_csv(self.db,p,dataset_id=self.dataset,source_uri="fixture:test",usage_rights_confirmed=True,availability_verified=verified)
    def test_week_ohlcv_and_partial_current(self):
        p=self.plan("2026-01-05","2026-01-18",skip=("2026-01-09",))
        v=build_multiframe(self.db,self.dataset,"2026-01-15T00:00:00Z",p,"W")
        b=v["bars"][0]
        self.assertEqual((b["open"],b["high"],b["low"],b["close"],b["volume"]),(100,105,99,104,40))
        self.assertEqual(b["session_count"],4);self.assertEqual(b["last_session"],"2026-01-08")
        self.assertEqual(v["excluded_periods"][0]["state"],"PERIOD_NOT_CLOSED")
        self.assertFalse(v["g0_approved"]);self.assertIsNone(v["features"]["SMA:5"]["value"])
    def test_month_local_boundary(self):
        p=self.plan("2026-01-01","2026-02-28")
        with self.assertRaisesRegex(Blocked,"NO_COMPLETED_PERIOD"):
            build_multiframe(self.db,self.dataset,"2026-02-01T04:59:59Z",p,"M")
        v=build_multiframe(self.db,self.dataset,"2026-02-01T05:00:00Z",p,"M")
        self.assertEqual(v["period_count"],1);self.assertEqual(v["bars"][0]["period_end"],"2026-01-31")
    def test_year_partial_edges(self):
        p=self.plan("2024-12-01","2026-01-31")
        v=build_multiframe(self.db,self.dataset,"2026-02-01T06:00:00Z",p,"Y")
        self.assertEqual(v["period_count"],1);self.assertEqual(v["bars"][0]["period_start"],"2025-01-01")
        self.assertEqual([x["state"] for x in v["excluded_periods"]],["PARTIAL_COVERAGE","PARTIAL_COVERAGE"])
    def test_missing_constituent(self):
        p=self.plan("2026-01-05","2026-01-11")
        self.db.execute("DELETE FROM bars WHERE session='2026-01-07'")
        with self.assertRaisesRegex(Blocked,"MISSING_SESSION"):build_multiframe(self.db,self.dataset,"2026-01-12T06:00:00Z",p,"W")
    def test_latest_revision_blocks(self):
        p=self.plan("2026-01-05","2026-01-11")
        self.ingest("revision",[["2026-01-09",104,108,103,107,10,"2026-01-13T00:00:00Z"]],False)
        v=build_multiframe(self.db,self.dataset,"2026-01-12T06:00:00Z",p,"W")
        self.assertEqual(v["bars"][0]["close"],105)
        with self.assertRaisesRegex(Blocked,"LATEST_REVISION_UNVERIFIED"):build_multiframe(self.db,self.dataset,"2026-01-14T00:00:00Z",p,"W")
    def test_completed_period_features(self):
        p=self.plan("2026-01-05","2026-02-15")
        v=build_multiframe(self.db,self.dataset,"2026-02-16T06:00:00Z",p,"W")
        self.assertEqual(v["period_count"],6)
        self.assertEqual(v["features"]["SMA:5"]["value"],120)
        self.assertEqual(v["period_unit"],"COMPLETED_W")
    def test_empty_interior_period(self):
        p=self.plan("2026-01-05","2026-01-25",skip=tuple("2026-01-"+str(i) for i in range(12,17)))
        with self.assertRaisesRegex(Blocked,"EMPTY_DECLARED_PERIOD"):build_multiframe(self.db,self.dataset,"2026-01-26T06:00:00Z",p,"W")
    def test_corporate_actions_block(self):
        p=self.plan("2026-01-05","2026-01-11")
        p["corporate_action_state"]="UNKNOWN"
        with self.assertRaisesRegex(Blocked,"RAW_ACTIONS_UNRESOLVED"):build_multiframe(self.db,self.dataset,"2026-01-12T06:00:00Z",p,"W")
