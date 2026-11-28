import unittest
from experiment import evaluate, score

class TestExperiment(unittest.TestCase):
    def test_constant(self):
        rows=evaluate([2]*8,[2]*8,[2]*8)
        self.assertEqual(len(rows),4)
        self.assertTrue(all(v["mae"]==0 for v in score(rows).values()))
    def test_no_future_target(self):
        a=[1,2,3,4,5,6]
        b=[1,2,3,4,99,100]
        self.assertEqual(evaluate(a,a,a)[0]["predictions"],evaluate(b,a,a)[0]["predictions"])
    def test_invalid(self):
        with self.assertRaises(ValueError): evaluate([1]*5,[1]*4,[1]*5)
        with self.assertRaises(ValueError): evaluate([1]*4+[float("nan")],[1]*5,[1]*5)
    def test_score(self):
        s=score([{"actual":2,"predictions":{"m":1}},{"actual":4,"predictions":{"m":5}}])
        self.assertEqual(s["m"],{"mae":1,"rmse":1,"bias":0})
if __name__=="__main__": unittest.main()
