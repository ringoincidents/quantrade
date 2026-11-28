import tempfile,unittest,sqlite3
from pathlib import Path
from datetime import datetime
import duty as core
import public_duty as pub
import operations_audit as a
from test_handoff import fixture
from test_public_duty import at
class Audit(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/"source.sqlite"
        self.db=core.open_db(self.path);pub.init(self.db)
        pub.tick(self.db,at(7,10),fixture)
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def audit(self,now):
        r=a.open_readonly(self.path)
        try:
            r.execute("BEGIN");return a.audit(r,now)
        finally:r.close()
    def test_healthy_and_read_only(self):
        self.assertEqual(self.audit(at(7,11))["state"],"PASS")
        r=a.open_readonly(self.path)
        try:
            with self.assertRaises(sqlite3.OperationalError):r.execute("DELETE FROM public_jobs")
        finally:r.close()
    def test_missing_and_stale(self):
        p=self.audit(at(19,30))
        self.assertEqual(p["findings"]["SCHEDULE_MISSING"],2)
        self.assertIn("SCHEDULER_STALE",p["findings"])
        self.assertIn("HOURLY_REPORT_MISSING",p["findings"])
    def test_corrupt_source(self):
        with self.db:self.db.execute("UPDATE public_jobs SET digest='x' WHERE sop='UST_PAR'")
        p=self.audit(at(7,11))
        self.assertIn("SOURCE_ARTIFACT_INVALID",p["findings"])
        self.assertIn("SOURCE_STAGE_LINK_INVALID",p["findings"])
    def test_incomplete_handoff(self):
        with self.db:self.db.execute("DELETE FROM duty_handoffs WHERE sop='UST_PAR' AND stage='COMPARE'")
        p=self.audit(at(7,14))
        self.assertIn("HANDOFF_INCOMPLETE",p["findings"])
        self.assertIn("HANDOFF_LINK_INVALID",p["findings"])
    def test_forged_completion_without_source(self):
        with self.db:self.db.execute("UPDATE public_jobs SET state='BLOCKED' WHERE sop='BLS_V1'")
        self.assertIn("COMPLETION_WITHOUT_SOURCE",self.audit(at(7,11))["findings"])
    def test_report_and_review(self):
        with self.db:
            self.db.execute("UPDATE public_reports SET digest='bad'")
            self.db.execute("INSERT INTO duty_reviews VALUES('UST_PAR',?,'REVISED',?,'PENDING_GOVERNANCE')",(at(7,5),at(7,10)))
        p=self.audit(at(7,11))
        self.assertIn("REVIEW_PENDING",p["findings"])
        # Current report belongs to the initial partial hour; audit it after next hour.
        pub.tick(self.db,at(8),fixture)
        with self.db:self.db.execute("UPDATE public_reports SET digest='bad' WHERE hour=?",(at(8),))
        self.assertIn("HOURLY_REPORT_INVALID",self.audit(at(8,1))["findings"])
    def test_separate_ledger(self):
        p=self.audit(at(7,11));dst=Path(self.tmp.name)/"audit.sqlite"
        a.save(dst,p);a.save(dst,p)
        d=sqlite3.connect(dst)
        try:self.assertEqual(d.execute("SELECT count(*) FROM audits").fetchone()[0],1)
        finally:d.close()
    def test_no_activation_claim(self):
        with self.db:self.db.execute("DELETE FROM public_meta WHERE k='coverage_start'")
        self.assertIn("COVERAGE_UNVERIFIED",self.audit(at(7,11))["findings"])
if __name__=="__main__":unittest.main()
