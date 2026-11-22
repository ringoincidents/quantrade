"""Offline, deterministic paper-only regression tests."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from quantrade.alpha_lab.paper import (
    EquityQuote, PaperAccount, PaperRejected, PaperRequest, PaperRules, Side,
)

T = datetime(2026, 10, 12, 14, 30, 0, tzinfo=timezone.utc)


def quote(*, bid="99.90", ask="100.00", open_=True, at=T):
    return EquityQuote("NVDA", D(bid), D(ask), at, open_)


def request(oid, side, qty="1", q=None, at=T):
    return PaperRequest(oid, side, D(qty), q or quote(), at)


class PaperBrokerTests(unittest.TestCase):
    def test_round_trip_counts_both_fees_and_spread(self):
        a = PaperAccount(D("500"))
        a.submit(request("buy-1", Side.BUY))
        self.assertEqual(a.cash, D("399.65"))
        a.submit(request("sell-1", Side.SELL))
        self.assertEqual(a.cash, D("499.20"))
        self.assertEqual(a.positions["NVDA"], D("0"))
        self.assertEqual(len(a.fills), 2)
        self.assertEqual(sum(f.platform_fee for f in a.fills), D("0.70"))

    def test_market_closed(self):
        a = PaperAccount(D("500"))
        with self.assertRaisesRegex(PaperRejected, "market closed"):
            a.submit(request("x", Side.BUY, q=quote(open_=False)))
        self.assertEqual(a.cash, D("500"))

    def test_minimum_notional_and_cost_insufficient_funds(self):
        a = PaperAccount(D("100"))
        with self.assertRaisesRegex(PaperRejected, "minimum"):
            a.submit(request("x", Side.BUY, qty="0.01"))
        with self.assertRaisesRegex(PaperRejected, "insufficient"):
            a.submit(request("x2", Side.BUY, qty="1"))
        self.assertEqual(a.cash, D("100"))

    def test_no_short_selling(self):
        a = PaperAccount(D("500"))
        with self.assertRaisesRegex(PaperRejected, "short selling"):
            a.submit(request("sell", Side.SELL))

    def test_idempotent_retries_and_conflicting_id(self):
        a = PaperAccount(D("500"))
        r = request("stable", Side.BUY)
        first = a.submit(r)
        self.assertIs(first, a.submit(r))
        self.assertEqual(len(a.fills), 1)
        with self.assertRaisesRegex(PaperRejected, "reused"):
            a.submit(request("stable", Side.BUY, qty="2"))
        self.assertEqual(len(a.fills), 1)

    def test_stale_or_future_quotes(self):
        a = PaperAccount(D("500"))
        with self.assertRaisesRegex(PaperRejected, "stale"):
            a.submit(request("stale", Side.BUY, q=quote(at=T-timedelta(seconds=6))))
        with self.assertRaisesRegex(PaperRejected, "future"):
            a.submit(request("future", Side.BUY, q=quote(at=T+timedelta(seconds=1))))

    def test_fee_tier_not_extrapolated(self):
        a = PaperAccount(D("1000"))
        with self.assertRaisesRegex(PaperRejected, "fee tier"):
            a.submit(request("big", Side.BUY, qty="4"))

    def test_quote_input_validation(self):
        with self.assertRaisesRegex(PaperRejected, "crossed"):
            quote(bid="100.1", ask="100.0")
        with self.assertRaisesRegex(PaperRejected, "timezone"):
            quote(at=datetime(2026, 10, 12))
        with self.assertRaisesRegex(PaperRejected, "positive"):
            request("bad", Side.BUY, qty="NaN")

    def test_symbol_specific_minimum_and_slippage(self):
        rules = PaperRules(min_order_notional=D("5.17"), slippage_bps=D("10"))
        a = PaperAccount(D("100"), rules)
        with self.assertRaisesRegex(PaperRejected, "minimum"):
            a.submit(request("small", Side.BUY, qty="0.05"))
        fill = a.submit(request("ok", Side.BUY, qty="0.1"))
        self.assertEqual(fill.price, D("100.10000"))
        self.assertEqual(fill.platform_fee, D("0.35"))


if __name__ == "__main__":
    unittest.main()
