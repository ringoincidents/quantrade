import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import duty as d
class DutyTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"pilot.sqlite"
        self.db=d.open_db(self.path)
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def count(self,state):
        return self.db.execute("SELECT count(*) FROM jobs WHERE state=?",(state,)).fetchone()[0]
    def test_idempotency_and_dependency(self):
        d.tick(self.db,3600);d.tick(self.db,3660)
        self.assertEqual(self.count("COMPLETED"),3)
        self.assertEqual(self.db.execute("SELECT count(*) FROM events WHERE kind='STARTED'").fetchone()[0],3)
    def test_catchup_and_hourly_report(self):
        d.tick(self.db,3600);d.tick(self.db,7200)
        self.assertEqual(self.count("COMPLETED"),39)
        self.assertTrue(d.latest_report(self.db)["coverage_complete"])
        self.assertEqual(d.latest_report(self.db)["states"],{"COMPLETED":36})
    def test_restart(self):
        d.plan_due(self.db,3600)
        with self.db:self.db.execute("UPDATE jobs SET state='RUNNING' WHERE sop='collect'")
        self.db.close();self.db=d.open_db(self.path);d.recover(self.db,3660);d.tick(self.db,3660)
        self.assertEqual(self.count("BLOCKED"),3)
    def test_failure_blocks_descendants(self):
        with patch.object(d,"handler",side_effect=RuntimeError("fixture")):
            d.tick(self.db,3600)
        self.assertEqual(self.count("BLOCKED"),3)
    def test_tamper(self):
        d.plan_due(self.db,3600)
        with self.db:self.db.execute("UPDATE jobs SET state='COMPLETED',result='{}',digest='wrong' WHERE sop='collect'")
        d.run_ready(self.db,3600)
        self.assertEqual(self.count("BLOCKED"),2)
    def test_bounded_backfill_and_clock(self):
        d.tick(self.db,3600);d.tick(self.db,36000)
        self.assertEqual(self.count("COMPLETED"),39)
        d.tick(self.db,1800)
        self.assertEqual(self.count("COMPLETED"),39)
        self.assertEqual(self.db.execute("SELECT count(*) FROM events WHERE kind='CLOCK_REGRESSION'").fetchone()[0],1)
    def test_report_immutable(self):
        d.tick(self.db,3600);first=d.latest_report(self.db)
        d.tick(self.db,3900)
        self.assertEqual(first,d.latest_report(self.db))
        self.assertFalse(first["llm_enabled"])
    def test_reopen(self):
        d.tick(self.db,3600)
        self.db.close();self.db=d.open_db(self.path);d.tick(self.db,3600)
        self.assertEqual(self.count("COMPLETED"),3)
if __name__=="__main__":unittest.main()
