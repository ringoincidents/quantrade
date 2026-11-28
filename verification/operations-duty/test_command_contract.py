import tempfile,unittest
from pathlib import Path
import duty as d
import command_contract as c
class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=d.open_db(Path(self.tmp.name)/"pilot.sqlite")
        d.tick(self.db,3600)
        self.key=b"x"*32
        self.report=self.db.execute("SELECT digest FROM reports").fetchone()[0]
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def envelope(self,**kwargs):
        p={"id":"a1","action":"ACK_REPORT","issued_at":3600,"expires_at":3900,"report_digest":self.report,"sop":None}
        p.update(kwargs)
        return dict(p,signature=c.sign(p,self.key))
    def accept(self,e):return c.accept(self.db,e,self.key,3660,d.PLAN)
    def test_ack_replay_conflict(self):
        self.assertEqual(self.accept(self.envelope()),"ACKNOWLEDGED")
        self.assertEqual(self.accept(self.envelope()),"ALREADY_RECORDED")
        with self.assertRaisesRegex(ValueError,"ID_CONFLICT"):
            self.accept(self.envelope(action="REQUEST_REVIEW",sop="collect"))
    def test_reject_expired_bad_action_unknown_report(self):
        for e in [self.envelope(expires_at=3659),self.envelope(action="EXECUTE"),self.envelope(report_digest="0"*64)]:
            with self.assertRaises(ValueError):self.accept(e)
    def test_reject_tamper(self):
        e=self.envelope();e["signature"]="0"*64
        with self.assertRaisesRegex(ValueError,"SIGNATURE"):self.accept(e)
    def test_request_review_reported(self):
        self.assertEqual(self.accept(self.envelope(action="REQUEST_REVIEW",sop="assure")),"REVIEW_REQUESTED")
        d.tick(self.db,7200)
        self.assertEqual(d.latest_report(self.db)["review_requests"][0]["sop"],"assure")
    def test_no_private_key_in_repo(self):
        p=Path(self.tmp.name)/"key";p.write_bytes(self.key);p.chmod(0o644)
        with self.assertRaises(ValueError):c.read_key(p)
        p.chmod(0o600);self.assertEqual(c.read_key(p),self.key)
if __name__=="__main__":unittest.main()
