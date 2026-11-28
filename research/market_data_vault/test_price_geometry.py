import unittest
from indicators import price_geometry
from feature_bridge import measure_bars

class PriceGeometryTests(unittest.TestCase):
    def test_candle(self):
        g=price_geometry([100],[110],[95],[105])
        self.assertAlmostEqual(g["body_signed_fraction"][0],1/3)
        self.assertAlmostEqual(g["upper_wick_fraction"][0],1/3)
        self.assertAlmostEqual(g["lower_wick_fraction"][0],1/3)
        self.assertAlmostEqual(g["range_fraction"][0],.15)
    def test_prior_window_excludes_current(self):
        g=price_geometry([10,11,12],[12,13,20],[9,10,11],[11,12,19],2)
        self.assertEqual(g["prior_high"],[None,None,13])
        self.assertEqual(g["prior_low"][-1],9)
        self.assertAlmostEqual(g["distance_to_prior_high"][-1],19/13-1)
    def test_flat_undefined(self):
        g=price_geometry([10],[10],[10],[10])
        self.assertIsNone(g["body_signed_fraction"][0])
        self.assertEqual(g["range_fraction"][0],0)
    def test_reject_inconsistent(self):
        with self.assertRaises(ValueError):price_geometry([10],[9],[8],[10])
        with self.assertRaises(ValueError):price_geometry([10],[11],[8],[10,11])
    def test_prefix_invariance(self):
        v=list(range(10,40))
        a=price_geometry(v[:25],[x+2 for x in v[:25]],[x-1 for x in v[:25]],v[:25])
        b=price_geometry(v,[x+2 for x in v],[x-1 for x in v],v)
        self.assertEqual(a,{k:x[:25] for k,x in b.items()})
    def test_shared_measurement(self):
        f=measure_bars([{"open":100,"close":100,"high":100,"low":100,"volume":10} for _ in range(21)],"USD")
        self.assertEqual(f["PRICE_GEOMETRY:body_signed_fraction"]["state"],"UNDEFINED_ZERO_RANGE")
        self.assertEqual(f["PRICE_GEOMETRY:prior_high"]["value"],100)
