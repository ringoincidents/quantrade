import unittest
from indicators import macd,bollinger,volume_ratio,cmf
class ExtendedIndicators(unittest.TestCase):
    def test_macd_linear(self):
        v=macd(list(range(1,41)))
        self.assertIsNone(v["line"][24]);self.assertAlmostEqual(v["line"][25],7)
        self.assertIsNone(v["signal"][32]);self.assertAlmostEqual(v["signal"][33],7)
        self.assertAlmostEqual(v["histogram"][-1],0)
    def test_macd_flat_and_invalid(self):
        self.assertEqual(macd([100]*40)["histogram"][-1],0)
        with self.assertRaises(ValueError):macd([100]*40,26,12)
    def test_bollinger_population(self):
        b=bollinger([1,2,3],3)
        self.assertAlmostEqual(b["upper"][-1],2+2*(2/3)**.5)
        self.assertAlmostEqual(b["lower"][-1],2-2*(2/3)**.5)
        self.assertIsNone(b["mid"][1])
    def test_volume_ratio_prior_excludes_current(self):
        self.assertEqual(volume_ratio([10,10,30],2),[None,None,3.0])
        self.assertEqual(volume_ratio([0,0,30],2),[None,None,None])
    def test_cmf_extremes_and_flat(self):
        self.assertEqual(cmf([11,11],[9,9],[11,11],[10,10],2)[-1],1)
        self.assertEqual(cmf([11,11],[9,9],[9,9],[10,10],2)[-1],-1)
        self.assertEqual(cmf([10,10],[10,10],[10,10],[10,10],2)[-1],0)
        self.assertIsNone(cmf([11,11],[9,9],[10,10],[0,0],2)[-1])
    def test_invalid_volume(self):
        for values in ([True,1],[-1,1],[float("nan"),1]):
            with self.assertRaises(ValueError):volume_ratio(values,1)
        with self.assertRaises(ValueError):cmf([11],[9],[12],[1],1)
    def test_prefix_invariance(self):
        p=list(range(1,51))
        for fn in (macd,bollinger):
            a=fn(p[:40]);b=fn(p)
            self.assertEqual(a,{k:v[:40] for k,v in b.items()})
