import json,unittest
from datetime import datetime,timezone
import duty as core
import public_duty as public
import hq_bridge as h
from test_public_duty import fixture,at
class API:
    def __init__(self):self.rows=[];self.calls=0;self.fail=False
    def actor(self):return 77
    def comments(self):return self.rows
    def post(self,b):
        self.calls+=1
        r={"id":123,"user":{"id":77},"body":b};self.rows.append(r)
        if self.fail:raise TimeoutError()
        return r
class Bridge(unittest.TestCase):
    def setUp(self):
        self.db=core.open_db(":memory:");public.init(self.db);h.init(self.db)
        self.now=at(8);public.tick(self.db,at(7,10),fixture);public.tick(self.db,self.now,fixture)
        self.api=API()
    def tearDown(self):self.db.close()
    def command(self,**kwargs):
        d={"action":"REQUEST_REVIEW","report_digest":h.prepare(self.db)["digest"],"sop":"UST_PAR"}
        stamp=datetime.fromtimestamp(self.now,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        c={"id":9,"user":{"id":88},"created_at":stamp,"updated_at":stamp,"body":h.COMMAND_PREFIX+core.canonical(d)}
        c.update(kwargs);return c
    def test_sanitized_projection(self):
        p=json.loads(self.db.execute("SELECT payload FROM public_reports ORDER BY hour DESC").fetchone()[0])
        p["private"]="secret";p["jobs"][0]["reason"]="private raw error"
        p["jobs"][0]["last_success"]["rows"]=[{"position":"private"}]
        result=core.canonical(h.project(p))
        for term in ("secret","private","fixture","rows","reason"):self.assertNotIn(term,result)
    def test_dedupe_and_recover_unknown(self):
        self.api.fail=True
        with self.assertRaises(TimeoutError):h.publish(self.db,self.api,self.now,77)
        self.assertEqual(h.publish(self.db,self.api,self.now,77),"SENT")
        self.assertEqual(h.publish(self.db,self.api,self.now,77),"SENT")
        self.assertEqual(self.api.calls,1)
    def test_unknown_no_blind_retry(self):
        self.api.fail=True
        with self.assertRaises(TimeoutError):h.publish(self.db,self.api,self.now,77)
        self.api.rows=[]
        self.assertEqual(h.publish(self.db,self.api,self.now,77),"DELIVERY_UNKNOWN")
        self.assertEqual(self.api.calls,1)
    def test_wrong_identity(self):
        with self.assertRaisesRegex(ValueError,"PUBLISHER_IDENTITY"):h.publish(self.db,self.api,self.now,88)
    def test_valid_proposal_never_executes(self):
        h.publish(self.db,self.api,self.now,77)
        c=self.command()
        self.assertEqual(h.ingest(self.db,[c],self.now,88)["accepted"],1)
        self.assertEqual(h.ingest(self.db,[c],self.now,88)["duplicate"],1)
        self.assertEqual(self.db.execute("SELECT state FROM hq_proposals").fetchone()[0],"PENDING_GOVERNANCE")
    def test_reject_untrusted_edited_expired_unbound(self):
        c=self.command()
        self.assertEqual(h.ingest(self.db,[c],self.now,88)["rejected"],1)
        h.publish(self.db,self.api,self.now,77)
        for q,now in [(dict(c,user={"id":1}),self.now),(dict(c,updated_at="changed"),self.now),(c,self.now+3600)]:
            self.assertEqual(h.ingest(self.db,[q],now,88)["rejected"],1)
    def test_no_arbitrary_command(self):
        h.publish(self.db,self.api,self.now,77)
        c=self.command();p=json.loads(c["body"][len(h.COMMAND_PREFIX):]);p["action"]="EXECUTE"
        c["body"]=h.COMMAND_PREFIX+core.canonical(p)
        self.assertEqual(h.ingest(self.db,[c],self.now,88)["rejected"],1)
if __name__=="__main__":unittest.main()
