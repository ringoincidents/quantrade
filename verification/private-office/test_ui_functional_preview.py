import unittest
from unittest.mock import patch
import ui_functional_preview as u
class Preview(unittest.TestCase):
    def test_home(self):
        for s in ("field","lab","office"):
            h=u.home(s)
            self.assertEqual(h.count('aria-current="page"'),1)
            self.assertIn('공개·합성 검토',h)
    def test_fragments(self):
        for p in sorted(u.ALLOWED):
            title,html=u.fragment(p)
            self.assertTrue(title,p)
            self.assertTrue(html,p)
        t,h=u.fragment("date:2026-12-10")
        self.assertIn("FOMC",h)
        self.assertIn("CPI",h)
    def test_no_private_paths(self):
        for p in ("/api/portfolio","/reports/fundamental/live/005930","/inbox/live","/market/macro/D","/assets","/login","/api/link-check"):
            with self.assertRaises(ValueError):u.fragment(p)
    def test_asset_engine(self):
        h=u.office()
        self.assertIn("1,452,000",h)
        self.assertIn("660,000",h)
        self.assertIn("14.95%",h)
        self.assertIn("실제 순자산 미확인",h)
if __name__=="__main__":unittest.main()
