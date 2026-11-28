import unittest
import sqlite3
from forecast_ledger import connect,forecast,realization,evaluate,read

class TestLedger(unittest.TestCase):
    def setUp(self):
        self.db=connect(":memory:")
        self.f=forecast(self.db,"2020Q1","2020-02-01T00:00:00Z","mean","1",2,"a"*64)
    def tearDown(self): self.db.close()
    def test_revision(self):
        r=realization(self.db,"2020Q1","2020-04-30T00:00:00Z","FIRST_RELEASE",3)
        e=evaluate(self.db,self.f,r,"2020-05-01T00:00:00Z")
        r2=realization(self.db,"2020Q1","2020-06-01T00:00:00Z","REVISED",1)
        e2=evaluate(self.db,self.f,r2,"2020-06-02T00:00:00Z")
        self.assertEqual(read(self.db,e,"evaluation")["error"],-1)
        self.assertEqual(read(self.db,e2,"evaluation")["error"],1)
        self.assertNotEqual(e,e2)
        self.assertEqual(e,evaluate(self.db,self.f,r,"2020-05-01T00:00:00Z"))
    def test_immutable(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM events")
    def test_future(self):
        r=realization(self.db,"2020Q1","2020-04-30T00:00:00Z","FIRST_RELEASE",3)
        with self.assertRaises(ValueError):
            evaluate(self.db,self.f,r,"2020-04-01T00:00:00Z")
