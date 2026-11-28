import tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta
import duty as core
import public_duty as pub
import operations_audit as a
import audit_bridge as b
import spool_backup as backup
from test_handoff import fixture
from test_public_duty import at

class Integrated(unittest.TestCase):
    def test_seven_day_file_backed_restart_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/"spool.sqlite";aud=folder/"audit.sqlite"
            start=at(0);end=start+7*86400
            # 5-min ticks, close/reopen each invocation (oneshot lifecycle).
            # Fixed observation fixture is explicitly not live data.
            for t in range(start,end+1,300):
                db=core.open_db(path)
                try:pub.init(db);pub.tick(db,t,fixture)
                finally:db.close()
                if (t-start)%900==0:
                    r=a.open_readonly(path)
                    try:
                        r.execute("BEGIN");result=a.audit(r,t)
                        self.assertEqual(result["state"],"PASS",result)
                    finally:r.close()
                    a.save(aud,result)
            db=a.open_readonly(path)
            try:
                self.assertEqual(db.execute("SELECT count(*) FROM public_jobs WHERE state='COLLECTED'").fetchone()[0],28)
                self.assertEqual(db.execute("SELECT count(*) FROM duty_handoffs WHERE state='COMPLETED'").fetchone()[0],84)
                self.assertEqual(db.execute("SELECT count(*) FROM public_reports").fetchone()[0],169)
            finally:db.close()
            manifest=backup.snapshot(path,folder/"bundle")
            self.assertEqual(manifest["counts"]["public_jobs"],28)
            backup.restore(folder/"bundle",folder/"restored.sqlite")
            r=a.open_readonly(folder/"restored.sqlite")
            try:self.assertEqual(a.audit(r,end)["state"],"PASS")
            finally:r.close()
            with self.assertRaises(FileExistsError):backup.restore(folder/"bundle",folder/"restored.sqlite")
    def test_backup_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/"spool.sqlite"
            db=core.open_db(path)
            try:pub.init(db);pub.tick(db,at(7,10),fixture)
            finally:db.close()
            backup.snapshot(path,folder/"bundle")
            with (folder/"bundle"/"spool.sqlite").open("ab") as f:f.write(b"corrupt")
            with self.assertRaises(ValueError):backup.verify(folder/"bundle")
if __name__=="__main__":unittest.main()
