"""Offline regression: read-only methods and Binance signing without secrets or network."""
import hashlib
import hmac
import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from quantrade.connectors.binance_spot_readonly import (
    AccountReadOnly, BinanceReadOnlyError, PublicSpotData, _signed_query,
)


class Reply:
    def __init__(self, payload):
        self.payload = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, n):
        return self.payload.read(n)


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, req, timeout):
        self.calls.append((req, timeout))
        assert req.get_method() == "GET"
        assert timeout == 8
        if "apiRestrictions" in req.full_url:
            return Reply({"enableReading": True, "enableSpotAndMarginTrading": False,
                          "enableFutures": False, "enableWithdrawals": False})
        if "/account?" in req.full_url:
            return Reply({"balances": [{"asset": "USDT", "free": "10.00", "locked": "0.00"},
                                       {"asset": "BTC", "free": "0", "locked": "0"}]})
        if "exchangeInfo" in req.full_url:
            return Reply({"symbols": [{"symbol": "BTCUSDT", "status": "TRADING", "filters": []}]})
        if "bookTicker" in req.full_url:
            return Reply({"bidPrice": "100", "askPrice": "101"})
        if "klines" in req.full_url:
            return Reply([[1, "100", "101", "99", "100", "5"]])
        return Reply({"serverTime": 123})


class BinanceSpotReadOnlyTests(unittest.TestCase):
    def test_public_only_uses_public_host_and_no_api_key(self):
        spy = Spy()
        public = PublicSpotData(opener=spy)
        self.assertEqual(public.exchange_info("BTCUSDT")["status"], "TRADING")
        self.assertEqual(public.book_ticker("BTCUSDT")["askPrice"], "101")
        self.assertEqual(public.klines("BTCUSDT", "5m", 3)[0][0], 1)
        self.assertEqual(public.server_time(), 123)
        for req, _ in spy.calls:
            self.assertTrue(req.full_url.startswith("https://data-api.binance.vision/api/v3/"))
            self.assertFalse(req.has_header("X-mbx-apikey"))
            self.assertEqual(req.get_method(), "GET")

    def test_bad_symbol_interval_and_limit_fail_before_network(self):
        spy = Spy()
        public = PublicSpotData(opener=spy)
        for symbol in ("btcUSDT", "BTC/USDT", "", "BTCUSDT&evil=1"):
            with self.assertRaises(ValueError): public.exchange_info(symbol)
        for interval in ("9m", "", "1w"):
            with self.assertRaises(ValueError): public.klines("BTCUSDT", interval)
        for limit in (0, 1001, True, "100"):
            with self.assertRaises(ValueError): public.klines("BTCUSDT", "5m", limit)
        self.assertEqual(len(spy.calls), 0)

    def test_hmac_signature_matches_reference(self):
        query = _signed_query("secret", {"timestamp": 123456789, "recvWindow": 5000})
        payload = "timestamp=123456789&recvWindow=5000"
        self.assertEqual(query, payload + "&signature=" + hmac.new(b"secret", payload.encode(), hashlib.sha256).hexdigest())

    def test_private_account_reads_only_with_credentials_and_safe_permissions(self):
        spy = Spy()
        account = AccountReadOnly("key123", "secret456", opener=spy, clock_ms=lambda: 123456789)
        self.assertEqual(account.balances(), [{"asset": "USDT", "free": "10.00", "locked": "0.00"}])
        self.assertEqual(len(spy.calls), 2)
        for req, timeout in spy.calls:
            self.assertTrue(req.full_url.startswith("https://api.binance.com/"))
            self.assertIn("&signature=", req.full_url)
            self.assertEqual(req.get_header("X-mbx-apikey"), "key123")
            self.assertEqual(req.get_method(), "GET")
            self.assertNotIn("secret456", req.full_url)

    def test_trade_enabled_key_is_rejected_before_balances(self):
        class Elevated(Spy):
            def __call__(self, req, timeout):
                self.calls.append((req, timeout))
                return Reply({"enableReading": True, "enableSpotAndMarginTrading": True})
        spy = Elevated()
        with self.assertRaisesRegex(BinanceReadOnlyError, "read-only key"):
            AccountReadOnly("key", "secret", opener=spy, clock_ms=lambda: 1).balances()
        self.assertEqual(len(spy.calls), 1)

    def test_read_permission_is_required(self):
        spy = lambda request, timeout: Reply({"enableReading": False})
        with self.assertRaisesRegex(BinanceReadOnlyError, "lacks verified read"):
            AccountReadOnly("key", "secret", opener=spy).verified_permissions()

    def test_environment_requires_both_credentials(self):
        with patch.dict(os.environ, {"QUANTRADE_BINANCE_API_KEY": "", "QUANTRADE_BINANCE_API_SECRET": ""}):
            with self.assertRaises(BinanceReadOnlyError): AccountReadOnly.from_environment()

    def test_http_errors_do_not_leak_url_or_signature(self):
        def forbidden(req, timeout):
            raise HTTPError(req.full_url, 451, "block", {}, None)
        with self.assertRaises(BinanceReadOnlyError) as caught:
            AccountReadOnly("key", "top-secret", opener=forbidden, clock_ms=lambda: 123).balances()
        self.assertNotIn("signature", str(caught.exception))
        self.assertNotIn("top-secret", str(caught.exception))
        self.assertNotIn("api.binance.com", str(caught.exception))

    def test_error_unavailable_network_sanitized(self):
        def blocked(req, timeout):
            raise OSError("connection failed details")
        with self.assertRaisesRegex(BinanceReadOnlyError, "unavailable"):
            PublicSpotData(opener=blocked).server_time()


if __name__ == "__main__":
    unittest.main()
