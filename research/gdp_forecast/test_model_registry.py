import unittest
from contextlib import closing
from forecast_ledger import connect
from model_registry import register,lookup

class TestRegistry(unittest.TestCase):
    def test_identity(self):
        with closing(connect(":memory:")) as db, db:
            a=register(db,"SPF","1","a"*40,"benchmark")
            self.assertEqual(a,register(db,"SPF","1","a"*40,"benchmark"))
            self.assertNotEqual(a,register(db,"SPF","2","b"*40,"benchmark"))
            self.assertEqual(lookup(db,a)["status"],"RESEARCH_ONLY")
    def test_invalid(self):
        with closing(connect(":memory:")) as db:
            with self.assertRaises(ValueError): register(db,"unknown","1","a"*40,"test")
            with self.assertRaises(ValueError): register(db,"SPF","1","bad","test")
