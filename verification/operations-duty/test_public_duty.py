import unittest
from datetime import datetime,timezone
import duty as core
import public_duty as d

def at(h,m=0,day=28):
    return int(datetime(2026,11,day,h,m,tzinfo=d.KST).timestamp())
def fixture(sop,now):
    return {"mode":"OFFICIAL_PUBLIC_REFERENCE","source":"fixture","observed_at":datetime.fromtimestamp(now,timezone.utc).isoformat(),"rows":[{"fixture":sop}],"decision_authorized":False,"trade_authorized":False}
class PublicDuty(unittest.TestCase):
    def setUp(self):
        self.db=core.open_db(":memory:");d.init(self.db)
    def tearDown(self):self.db.close()
    def rows(self):return self.db.execute("SELECT sop,state,due FROM public_jobs ORDER BY due").fetchall()
    def test_kst_and_dedupe(self):
        d.tick(self.db,at(7,0),fixture)
        d.tick(self.db,at(7,5),fixture)
        d.tick(self.db,at(7,10),fixture)
        d.tick(self.db,at(7,15),fixture)
        self.assertEqual([(x[0],x[1]) for x in self.rows()],[("UST_PAR","COLLECTED"),("BLS_V1","COLLECTED")])
        r=d.tick(self.db,at(8),fixture)
        self.assertTrue(all(x["last_success"] for x in r["jobs"]))
    def test_no_historical_network_replay(self):
        d.tick(self.db,at(7),fixture)
        called=[]
        d.tick(self.db,at(19,10),lambda s,n:(called.append(s),fixture(s,n))[1])
        self.assertEqual([r[1] for r in self.rows()],["MISSED","MISSED","COLLECTED","COLLECTED"])
        self.assertEqual(called,["UST_PAR","BLS_V1"])
    def test_failure_never_retries(self):
        def bad(s,n):raise TimeoutError()
        d.tick(self.db,at(7,10),bad);d.tick(self.db,at(7,15),fixture)
        self.assertEqual([r[1] for r in self.rows()],["BLOCKED","BLOCKED"])
    def test_recovery(self):
        d.plan(self.db,at(7,5))
        with self.db:self.db.execute("UPDATE public_jobs SET state='RUNNING'")
        d.tick(self.db,at(7,6),fixture)
        self.assertEqual(self.rows()[0][1],"BLOCKED")
    def test_clock_regression(self):
        d.tick(self.db,at(7,10),fixture)
        with self.assertRaisesRegex(ValueError,"CLOCK_REGRESSION"):d.tick(self.db,at(7),fixture)
    def test_report_integrity(self):
        d.tick(self.db,at(7,10),fixture)
        with self.db:self.db.execute("UPDATE public_reports SET digest='bad'")
        with self.assertRaisesRegex(ValueError,"REPORT_CORRUPT"):d.report(self.db,at(7,20))
    def test_last_success_labeled_historical(self):
        d.tick(self.db,at(7,10),fixture)
        def bad(s,n):raise TimeoutError()
        d.tick(self.db,at(19,10),bad)
        r=d.tick(self.db,at(20),fixture)
        self.assertTrue(all(x["last_success"]["historical_only"] and x["latest_state"]=="BLOCKED" for x in r["jobs"]))
if __name__=="__main__":unittest.main()
