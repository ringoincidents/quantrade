import unittest
import duty as d
class SevenDaySimulation(unittest.TestCase):
    def test_virtual_seven_days(self):
        db=d.open_db(":memory:")
        try:
            start=3600; end=start+7*86400
            for now in range(start,end+1,d.PERIOD): d.tick(db,now)
            self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE state='COMPLETED'").fetchone()[0],6051)
            self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE state!='COMPLETED'").fetchone()[0],0)
            reports=[__import__("json").loads(r[0]) for r in db.execute("SELECT body FROM reports ORDER BY slot")]
            self.assertEqual(len(reports),169)
            self.assertFalse(reports[0]["coverage_complete"])
            self.assertTrue(all(x["all_completed"] and x["llm_calls"]==0 and not x["decision_requested"] for x in reports[1:]))
        finally: db.close()
if __name__=="__main__":unittest.main()
