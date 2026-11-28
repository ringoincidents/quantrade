import unittest
from contextlib import closing
from forecast_ledger import connect, forecast, realization, evaluate
from scorecard import compare

class TestScorecard(unittest.TestCase):
    def test_comparison(self):
        with closing(connect(":memory:")) as db, db:
            ids=[]
            for q in ("2020Q1","2020Q2"):
                r=realization(db,q,"2020-08-01T00:00:00Z","FIRST_RELEASE",3)
                for name,value in (("base",1),("candidate",2)):
                    f=forecast(db,q,"2020-01-01T00:00:00Z",name,"1",value,"a"*64)
                    ids.append(evaluate(db,f,r,"2020-09-01T00:00:00Z"))
            result=compare(db,ids,("base","1"))
            self.assertEqual(result["models"][1]["skill"],0.5)
            with self.assertRaises(ValueError): compare(db,ids[:-1],("base","1"))
            with self.assertRaises(ValueError): compare(db,ids+[ids[0]],("base","1"))
    def test_zero_baseline(self):
        with closing(connect(":memory:")) as db, db:
            r=realization(db,"2020Q1","2020-04-01T00:00:00Z","FIRST_RELEASE",3)
            f=forecast(db,"2020Q1","2020-02-01T00:00:00Z","base","1",3,"a"*64)
            e=evaluate(db,f,r,"2020-05-01T00:00:00Z")
            self.assertIsNone(compare(db,[e],("base","1"))["models"][0]["skill"])
