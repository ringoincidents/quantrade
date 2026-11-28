import unittest
from unittest.mock import Mock
from probe import request, proxy_config, holdings_ok, page_complete, Blocked

class TestProbe(unittest.TestCase):
    def test_mutations_blocked_before_transport(self):
        session = Mock()
        for method, path in [("POST", "/api/v1/orders"), ("POST", "/api/v1/orders/1/cancel"),
                             ("POST", "/api/v1/conditional-orders"), ("GET", "https://example.com")]:
            with self.assertRaises(Blocked):
                request(session, method, path)
        session.request.assert_not_called()

    def test_proxy_fail_closed(self):
        for url in ["http://x:y@example.com:3128", "http://141.164.41.178:3128",
                    "http://x:y@141.164.41.178:80"]:
            with self.assertRaises(Blocked):
                proxy_config(url)
        self.assertEqual(proxy_config("http://x:y@141.164.41.178:3128").port, 3128)

    def test_holdings_shape(self):
        self.assertTrue(holdings_ok({"items":[]}))
        self.assertFalse(holdings_ok({"items":[{}]}))
        self.assertFalse(page_complete({"hasNext":True}))
        self.assertFalse(page_complete({"nextCursor":"x"}))

if __name__ == "__main__":
    unittest.main()
