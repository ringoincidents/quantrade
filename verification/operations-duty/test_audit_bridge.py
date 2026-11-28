import sqlite3,unittest
import audit_bridge as b
from test_hq_bridge import API
class AuditBridge(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:");self.db.row_factory=sqlite3.Row;b.init(self.db);self.api=API()
    def tearDown(self):self.db.close()
    def audit(self,at,findings):
        return {"schema":"QT_OPERATIONS_AUDIT_V1","mode":"PUBLIC_REFERENCE_PILOT","checked_at":at,
        "state":"EXCEPTION" if findings else "PASS","findings":findings,"finding_count":sum(findings.values()),
        "source_independently_verified":False,"execution_authorized":False,"trade_authorized":False,"llm_calls":0,
        "samples":[{"secret":"not projected"}]}
    def test_exception_then_recovery(self):
        self.assertIsNone(b.prepare(self.db,self.audit(100,{}),100))
        r=b.prepare(self.db,self.audit(200,{"SCHEDULER_STALE":1}),200)
        self.assertNotIn("secret",r["body"]);self.assertEqual(b.publish(self.db,self.api,77,200),"SENT")
        self.assertIsNone(b.prepare(self.db,self.audit(300,{"SCHEDULER_STALE":1}),300))
        self.assertIsNotNone(b.prepare(self.db,self.audit(400,{}),400))
        self.assertEqual(b.publish(self.db,self.api,77,400),"SENT")
        self.assertEqual(self.api.calls,2)
    def test_uncertain_delivery_reconciles(self):
        b.prepare(self.db,self.audit(200,{"SCHEDULER_STALE":1}),200)
        self.api.fail=True
        with self.assertRaises(TimeoutError):b.publish(self.db,self.api,77,200)
        self.assertEqual(b.publish(self.db,self.api,77,201),"SENT")
        self.assertEqual(self.api.calls,1)
    def test_no_blind_retry(self):
        b.prepare(self.db,self.audit(200,{"SCHEDULER_STALE":1}),200);self.api.fail=True
        with self.assertRaises(TimeoutError):b.publish(self.db,self.api,77,200)
        self.api.rows=[]
        self.assertEqual(b.publish(self.db,self.api,77,201),"DELIVERY_UNKNOWN")
        self.assertEqual(self.api.calls,1)
    def test_invalid_or_stale(self):
        with self.assertRaises(ValueError):b.prepare(self.db,self.audit(100,{"private text":1}),100)
        with self.assertRaises(ValueError):b.prepare(self.db,self.audit(100,{}),2000)
    def test_stale_unsent_no_post(self):
        b.prepare(self.db,self.audit(200,{"SCHEDULER_STALE":1}),200)
        self.assertEqual(b.publish(self.db,self.api,77,2100),"STALE_PENDING")
        self.assertEqual(self.api.calls,0)
if __name__=="__main__":unittest.main()
