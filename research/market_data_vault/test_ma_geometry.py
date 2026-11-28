import unittest
from indicators import ma_geometry
from feature_bridge import measure_bars

class GeometryTests(unittest.TestCase):
    def test_flat(self):
        g=ma_geometry([100]*80,(5,20,60),5)
        self.assertEqual(g["width"][-1],0)
        self.assertEqual(g["width_change"][-1],0)
        self.assertEqual(g["slopes"][60][-1],0)
        self.assertEqual(g["pair_gaps"]["5:20"][-1],0)
    def test_known_geometry(self):
        g=ma_geometry([1,2,3,4,5],(2,3),1)
        # Last SMA2=4.5, SMA3=4, mean=4.25.
        self.assertAlmostEqual(g["width"][-1],.5/4.25)
        self.assertAlmostEqual(g["pair_gaps"]["2:3"][-1],4.5/4-1)
        self.assertAlmostEqual(g["slopes"][2][-1],4.5/3.5-1)
        self.assertLess(g["width_change"][-1],0)
    def test_warmup(self):
        g=ma_geometry([1,2,3,4,5],(2,6),2)
        self.assertTrue(all(x is None for x in g["width"]))
        self.assertTrue(all(x is None for x in g["width_change"]))
        self.assertIsNotNone(g["slopes"][2][-1])
        self.assertIsNone(g["slopes"][6][-1])
    def test_prefix_invariance(self):
        p=list(range(100,190))
        a=ma_geometry(p[:70]);b=ma_geometry(p)
        for k in ("width","width_change"):
            self.assertEqual(a[k],b[k][:70])
        for k in ("slopes","pair_gaps"):
            self.assertEqual(a[k],{n:v[:70] for n,v in b[k].items()})
    def test_scale_invariance(self):
        p=list(range(100,180))
        a=ma_geometry(p);b=ma_geometry([x*10 for x in p])
        for k in ("width","width_change"):
            self.assertAlmostEqual(a[k][-1],b[k][-1])
        for k in ("slopes","pair_gaps"):
            for n in a[k]:self.assertAlmostEqual(a[k][n][-1],b[k][n][-1])
    def test_invalid(self):
        for windows in ((5,5),(20,5),(True,5),(5,)):
            with self.assertRaises(ValueError):ma_geometry([1,2,3],windows)
    def test_shared_measurement(self):
        f=measure_bars([{"close":100,"high":101,"low":99,"volume":10} for _ in range(65)],"USD")
        self.assertEqual(f["MA_WIDTH:5:20:60"]["value"],0)
        self.assertIsNone(f["MA_WIDTH:20:60:200"]["value"])
        self.assertEqual(f["MA_WIDTH_DELTA_5:5:20:60"]["value"],0)
        self.assertEqual(f["MA_SLOPE_5:60"]["value"],0)
