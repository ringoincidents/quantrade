"""Binance Spot REST read-only adapter for QuanTrade research.

Fixed official hosts, allowlisted GET endpoints, no order code or HTTP writes.
Public endpoints require no key; private account balance + permission check
require an HMAC Binance API key with ENABLE READING ONLY.

Not related to the Binance Stocks equity endpoints. This client does not
connect to the user's exchange account until a credential is supplied via
environment variables in a secure runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PUBLIC_ORIGIN = "https://data-api.binance.vision"
ACCOUNT_ORIGIN = "https://api.binance.com"
_PUBLIC_PATHS = frozenset({
    "/api/v3/time", "/api/v3/exchangeInfo", "/api/v3/ticker/bookTicker", "/api/v3/klines"
})
_PRIVATE_PATHS = frozenset({"/sapi/v1/account/apiRestrictions", "/api/v3/account"})
_INTERVALS = frozenset({"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"})
_SYMBOL = re.compile(r"^[A-Z0-9]{4,20}$")
_READ_ONLY_KEY_FIELDS = (
    "enableSpotAndMarginTrading", "enableFutures", "enableWithdrawals",
    "enableMargin", "enableVanillaOptions", "enableInternalTransfer",
    "enablePortfolioMarginTrading",
)


class BinanceReadOnlyError(RuntimeError):
    """Error without credential-bearing URLs or raw HTTP response details."""


def _symbol(value: str) -> str:
    if not isinstance(value, str) or not _SYMBOL.fullmatch(value):
        raise ValueError("symbol must be uppercase alphanumeric (e.g. BTCUSDT)")
    return value


def _signed_query(secret: str, params: dict[str, int]) -> str:
    payload = urlencode(params)
    signature = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return payload + "&signature=" + signature


def _request(url: str, api_key: str | None = None, *, opener: Callable = urlopen) -> object:
    headers = {"Accept": "application/json", "User-Agent": "QuanTrade-Spot-ReadOnly/0.1"}
    if api_key is not None:
        headers["X-MBX-APIKEY"] = api_key
    request = Request(url, headers=headers, method="GET")
    try:
        with opener(request, timeout=8) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise BinanceReadOnlyError("Binance response exceeds 2MB safety limit")
        return json.loads(raw)
    except HTTPError as exc:
        # Do not include exc or URL: signed query must not be exposed.
        raise BinanceReadOnlyError(f"Binance returned HTTP {exc.code}; check eligibility, region or permissions") from None
    except (URLError, TimeoutError, OSError):
        raise BinanceReadOnlyError("Binance connection unavailable; check network/region/time") from None
    except (ValueError, UnicodeDecodeError):
        raise BinanceReadOnlyError("Binance returned invalid JSON") from None


class PublicSpotData:
    def __init__(self, *, opener: Callable = urlopen):
        self._opener = opener

    def _get(self, path: str, params: dict | None = None) -> object:
        if path not in _PUBLIC_PATHS:
            raise ValueError("unsupported public endpoint")
        query = "?" + urlencode(params) if params else ""
        return _request(PUBLIC_ORIGIN + path + query, opener=self._opener)

    def server_time(self) -> int:
        return int(self._get("/api/v3/time")["serverTime"])

    def exchange_info(self, symbol: str) -> dict:
        data = self._get("/api/v3/exchangeInfo", {"symbol": _symbol(symbol)})
        return data["symbols"][0]

    def book_ticker(self, symbol: str) -> dict:
        return self._get("/api/v3/ticker/bookTicker", {"symbol": _symbol(symbol)})

    def klines(self, symbol: str, interval: str = "5m", limit: int = 100) -> list:
        if interval not in _INTERVALS:
            raise ValueError("interval not allowlisted")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be integer from 1 to 1000")
        return self._get("/api/v3/klines", {"symbol": _symbol(symbol), "interval": interval, "limit": limit})


class AccountReadOnly:
    def __init__(self, api_key: str, secret: str, *, opener: Callable = urlopen, clock_ms: Callable = lambda: int(time.time() * 1000)):
        if not api_key or not secret:
            raise BinanceReadOnlyError("API key and secret must both be set")
        self._api_key = api_key
        self._secret = secret
        self._opener = opener
        self._clock_ms = clock_ms

    @classmethod
    def from_environment(cls, *, opener: Callable = urlopen, clock_ms: Callable = lambda: int(time.time() * 1000)) -> "AccountReadOnly":
        return cls(
            os.getenv("QUANTRADE_BINANCE_API_KEY", ""),
            os.getenv("QUANTRADE_BINANCE_API_SECRET", ""),
            opener=opener, clock_ms=clock_ms,
        )

    def _signed_get(self, path: str) -> dict:
        if path not in _PRIVATE_PATHS:
            raise ValueError("unsupported private endpoint")
        params = {"timestamp": int(self._clock_ms()), "recvWindow": 5000}
        url = ACCOUNT_ORIGIN + path + "?" + _signed_query(self._secret, params)
        return _request(url, self._api_key, opener=self._opener)

    def verified_permissions(self) -> dict:
        permissions = self._signed_get("/sapi/v1/account/apiRestrictions")
        if permissions.get("enableReading") is not True:
            raise BinanceReadOnlyError("API key lacks verified read permission")
        unexpected = [name for name in _READ_ONLY_KEY_FIELDS if permissions.get(name) is True]
        if unexpected:
            raise BinanceReadOnlyError("Refusing a key with trading/withdrawal/transfer permissions; generate a read-only key")
        return {"read_only_verified": True, "trade_permissions": False}

    def balances(self) -> list[dict[str, str]]:
        self.verified_permissions()
        response = self._signed_get("/api/v3/account")
        filtered = []
        for entry in response.get("balances", []):
            try:
                free, locked = Decimal(entry["free"]), Decimal(entry["locked"])
            except (KeyError, InvalidOperation):
                raise BinanceReadOnlyError("Malformed account balance returned") from None
            if free > 0 or locked > 0:
                filtered.append({"asset": entry["asset"], "free": str(free), "locked": str(locked)})
        return filtered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Binance Spot preflight (NEVER trades)")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--private", action="store_true", help="Read authenticated balances via ENABLE READING key from env")
    args = parser.parse_args(argv)
    try:
        public = PublicSpotData()
        info = public.exchange_info(args.symbol)
        ticker = public.book_ticker(args.symbol)
        result = {
            "exchange": "BINANCE_SPOT", "symbol": args.symbol,
            "status": info["status"], "bid": ticker["bidPrice"], "ask": ticker["askPrice"],
            "rules": [f for f in info["filters"] if f.get("filterType") in ("MIN_NOTIONAL", "NOTIONAL", "LOT_SIZE", "MARKET_LOT_SIZE")],
            "api_mode": "PUBLIC_READ_ONLY", "orders_enabled": False,
        }
        if args.private:
            account = AccountReadOnly.from_environment()
            result["balances"] = account.balances()
            result["api_mode"] = "VERIFIED_PRIVATE_READ_ONLY"
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (BinanceReadOnlyError, ValueError, KeyError, IndexError) as exc:
        # Only sanitized custom errors / internal constants; never print an HTTP URL.
        print(json.dumps({"ok": False, "error": str(exc), "orders_enabled": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
