import unittest
from datetime import datetime,timezone
import duty as core
import public_duty as pub
import handoff as h
from test_public_duty import at
def fixture(sop,now):
    stamp=datetime.fromtimestamp(now,timezone.utc).isoformat()
    if sop=="UST_PAR":
        source="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=2026"
        rows=[{"observation_date":"2026-11-27","ust_par_2y_pct":4.69,"ust_par_10y_pct":4.94,"spread_10y_2y_bp":25}]
    else:
        source="https://api.bls.gov/publicAPI/v1/timeseries/data/"
        rows=[{"source_series_id":k,"observation_date":"2026-10-01","value":v} for k,v in
              [("CUSR0000SA0","337.476"),("CUSR0000SA0L1E","339.9"),("CES0000000001","159293"),("LNS14000000","4.1")]]
    return {"mode":"OFFICIAL_PUBLIC_REFERENCE","source":source,"observed_at":stamp,"source_sha256":"0"*64,"rows":rows,
            "latest_session_verified":False,"original_publication_time_verified":False,"decision_authorized":False,"trade_authorized":False}
class Handoff(unittest.TestCase):
    def setUp(self):
        self.db=core.open_db(":memory:");pub.init(self.db);h.init(self.db)
    def tearDown(self):self.db.close()
    def run_cycle(self,now,loader=fixture):
        pub.tick(self.db,now,loader);h.tick(self.db,now)
    def test_follow_on_no_dup(self):
        self.run_cycle(at(7,10));h.tick(self.db,at(7,11))
        self.assertEqual(h.summary(self.db)["stage_states"],{"COMPLETED":6})
    def test_revision_only_escalates(self):
        self.run_cycle(at(7,10))
        def revised(s,n):
            p=fixture(s,n)
            if s=="UST_PAR":p["rows"][0].update(ust_par_10y_pct=4.95,spread_10y_2y_bp=26)
            return p
        self.run_cycle(at(19,10),revised)
        self.assertEqual(h.summary(self.db)["pending_review_count"],1)
        self.assertEqual(self.db.execute("SELECT reason FROM duty_reviews").fetchone()[0],"REVISED")
    def test_input_tamper_blocks(self):
        pub.plan(self.db,at(7,10));pub.run_ready(self.db,at(7,10),fixture)
        with self.db:self.db.execute("UPDATE public_jobs SET digest='bad' WHERE sop='UST_PAR'")
        h.tick(self.db,at(7,10))
        self.assertEqual(h.summary(self.db)["stage_states"],{"BLOCKED":3,"COMPLETED":3})
    def test_bad_spread_blocks(self):
        def bad(s,n):
            p=fixture(s,n)
            if s=="UST_PAR":p["rows"][0]["spread_10y_2y_bp"]=999
            return p
        self.run_cycle(at(7,10),bad)
        self.assertEqual(h.summary(self.db)["pending_review_count"],1)
    def test_closed_period_coverage(self):
        self.run_cycle(at(7,10));self.run_cycle(at(19,10))
        self.run_cycle(at(0,0,29))
        p=h.decode(self.db.execute("SELECT * FROM duty_period_reports WHERE kind='DAILY' ORDER BY period_end DESC LIMIT 1").fetchone())
        self.assertTrue(p["all_completed"]);self.assertEqual(p["expected_source_jobs"],4)
        old=h.decode(self.db.execute("SELECT * FROM duty_period_reports WHERE kind='MONTHLY'").fetchone())
        self.assertFalse(old["coverage_complete"])
    def test_source_failure_goes_to_review(self):
        def bad(s,n):raise TimeoutError()
        self.run_cycle(at(7,10),bad)
        self.assertEqual(h.summary(self.db)["pending_review_count"],2)
        self.assertEqual(h.summary(self.db)["stage_states"],{"BLOCKED":6})
if __name__=="__main__":unittest.main()
