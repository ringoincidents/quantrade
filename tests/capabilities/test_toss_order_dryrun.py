"""Independent offline contract tests: NEVER use real credentials or a broker POST."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest

from quantrade.capabilities.toss_order_dryrun import (
    DryRunRejected, OfflineTossPaperGateway, OrderIntent, PaperContext, dec,
)


UTC = timezone.utc


def ctx(**overrides):
    t = datetime(2026, 10, 14, 10, 30, tzinfo=UTC)
    fields = dict(now=t, quote_at=t - timedelta(seconds=5), market_open=True,
                  reference_price=D("100"), buying_power=D("500"),
                  sellable_quantity=D("3"), max_notional=D("300"),
                  stopped=False, simulated_approval=True)
    fields.update(overrides)
    return PaperContext(**fields)


def intent(**overrides):
    fields = dict(symbol="005930", side="BUY", order_type="LIMIT", quantity=D("2"),
                  price=D("100"), client_order_id="test-001")
    fields.update(overrides)
    return OrderIntent(**fields)


class TossDryRunTests(unittest.TestCase):
    def test_build_toss_like_payload_no_secrets(self):
        p = intent().payload()
        self.assertEqual(p, {"symbol": "005930", "side": "BUY", "orderType": "LIMIT",
                             "quantity": "2", "clientOrderId": "test-001",
                             "timeInForce": "DAY", "price": "100"})
        self.assertNotIn("confirmHighValueOrder", p)

    def test_market_omits_price(self):
        self.assertNotIn("price", intent(symbol="AAPL", market_country="US", order_type="MARKET", price=None).payload())

    def test_reject_bad_order_shape(self):
        for params in (dict(side="HOLD"), dict(order_type="STOP"), dict(symbol="??"),
                       dict(order_type="LIMIT", price=None), dict(order_type="MARKET"),
                       dict(quantity=D("0")), dict(quantity=D("1.1")),
                       dict(quantity=D("NaN")), dict(quantity=1.5),
                       dict(client_order_id="x" * 37), dict(time_in_force="GTC")):
            with self.subTest(params=params), self.assertRaises(DryRunRejected):
                intent(**params).payload()

    def test_reject_stopped_or_unapproved(self):
        for context in (ctx(stopped=True), ctx(simulated_approval=False)):
            with self.assertRaises(DryRunRejected):
                OfflineTossPaperGateway().submit(intent(), context)

    def test_reject_closed_market_and_bad_clock(self):
        for context in (ctx(market_open=False), ctx(quote_at=ctx().now + timedelta(seconds=1)),
                        ctx(quote_at=ctx().now - timedelta(seconds=21))):
            with self.assertRaises(DryRunRejected):
                OfflineTossPaperGateway().submit(intent(), context)

    def test_reject_cap_or_funds_or_inventory(self):
        cases = [(intent(), ctx(max_notional=D("100"))),
                 (intent(), ctx(buying_power=D("199"))),
                 (intent(side="SELL", quantity=D("4")), ctx(max_notional=D("500")))]
        for i, c in cases:
            with self.assertRaises(DryRunRejected):
                OfflineTossPaperGateway().submit(i, c)

    def test_payload_not_mutated_and_preview_is_not_order(self):
        gateway = OfflineTossPaperGateway()
        v = gateway.preview(intent(), ctx())
        self.assertEqual(v["referenceNotional"], "200")
        self.assertEqual(v["mode"], "OFFLINE_PAPER_ONLY")
        self.assertEqual(gateway.orders, {})

    def test_paper_submit_idempotent(self):
        gateway = OfflineTossPaperGateway()
        a = gateway.submit(intent(), ctx())
        b = gateway.submit(intent(), ctx(stopped=True))
        self.assertIs(a, b)
        self.assertEqual(len(gateway.orders), 1)
        self.assertTrue(a.paper_order_id.startswith("paper-"))

    def test_idempotency_key_payload_conflict_rejected(self):
        gateway = OfflineTossPaperGateway()
        gateway.submit(intent(), ctx())
        with self.assertRaises(DryRunRejected):
            gateway.submit(intent(side="SELL"), ctx())

    def test_partial_then_full_fills(self):
        gateway = OfflineTossPaperGateway()
        gateway.submit(intent(), ctx())
        a = gateway.fill("test-001", quantity="1", price="101", fee="0.1")
        self.assertEqual(a.status, "PARTIAL_FILLED")
        self.assertEqual(a.snapshot()["filledQuantity"], "1")
        b = gateway.fill("test-001", quantity="1", price="99", fee="0.2")
        self.assertEqual(b.status, "FILLED")
        self.assertEqual(b.snapshot()["averageFilledPrice"], "100")
        self.assertEqual(b.snapshot()["fees"], "0.3")
        with self.assertRaises(DryRunRejected):
            gateway.fill("test-001", quantity=1, price=100)

    def test_partial_cancel_keeps_realized_paper_fill(self):
        gateway = OfflineTossPaperGateway()
        gateway.submit(intent(), ctx())
        gateway.fill("test-001", quantity=1, price=100)
        s = gateway.cancel("test-001")
        self.assertEqual((s.status, s.filled_quantity), ("CANCELED", D("1")))
        with self.assertRaises(DryRunRejected):
            gateway.cancel("test-001")

    def test_overfill_does_not_mutate_state(self):
        gateway = OfflineTossPaperGateway()
        before = gateway.submit(intent(), ctx()).snapshot()
        with self.assertRaises(DryRunRejected):
            gateway.fill("test-001", quantity=3, price=100)
        self.assertEqual(gateway.orders["test-001"].snapshot(), before)

    def test_invalid_fee_or_decimal(self):
        gateway = OfflineTossPaperGateway()
        gateway.submit(intent(), ctx())
        with self.assertRaises(DryRunRejected):
            gateway.fill("test-001", quantity=1, price=100, fee="-1")
        for value in ["Infinity", "NaN", "-4", True, 1.1]:
            with self.assertRaises(DryRunRejected):
                dec(value)

    def test_module_has_no_network_imports(self):
        import inspect
        import quantrade.capabilities.toss_order_dryrun as m
        text = inspect.getsource(m)
        for forbidden in ("import requests", "import httpx", "import urllib", ".post(",
                          "requests.request(", "TOSS_CLIENT_SECRET", "get_access_token("):
            self.assertNotIn(forbidden, text)



    def test_aapl_synthetic_fractional_sell_six_places_matches_official_spec(self):
        paper = intent(symbol="AAPL", market_country="US", side="SELL",
                       order_type="MARKET", price=None, quantity=D("0.012345"),
                       client_order_id="aapl-sell-fraction-test")
        self.assertEqual(paper.payload(), {
            "symbol": "AAPL", "side": "SELL", "orderType": "MARKET",
            "quantity": "0.012345", "clientOrderId": "aapl-sell-fraction-test",
            "timeInForce": "DAY",
        })

    def test_synthetic_aapl_fractional_paper_sale_within_ny_regular_session(self):
        # 2026-10-15 14:00 UTC is 10:00 EDT (regular session).
        t = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
        order = intent(symbol="AAPL", market_country="US", side="SELL",
                       order_type="MARKET", price=None, quantity=D("0.012345"))
        context = ctx(now=t, quote_at=t - timedelta(seconds=2),
                      reference_price=D("320"), max_notional=D("100"),
                      sellable_quantity=D("0.012345"))
        gw = OfflineTossPaperGateway()
        self.assertEqual(gw.preview(order, context)["referenceNotional"], "3.950400")
        result = gw.submit(order, context)
        gw.fill(order.client_order_id, quantity=D("0.012345"),
                price=D("320"), fee=D("0"))
        self.assertEqual(result.snapshot()["status"], "FILLED")
        self.assertEqual(result.snapshot()["filledQuantity"], "0.012345")
        self.assertEqual(len(gw.orders), 1)

    def test_fractional_rejected_for_buy_limit_or_korean_share(self):
        variants = [
            dict(symbol="AAPL", market_country="US", side="BUY",
                 order_type="MARKET", price=None),
            dict(symbol="AAPL", market_country="US", side="SELL",
                 order_type="LIMIT", price=D("321")),
            dict(symbol="005930", market_country="KR", side="SELL",
                 order_type="MARKET", price=None),
        ]
        for params in variants:
            with self.subTest(params=params), self.assertRaises(DryRunRejected):
                intent(quantity=D("0.012345"), **params).payload()

    def test_fractional_more_than_six_places_fails_closed(self):
        with self.assertRaises(DryRunRejected):
            intent(symbol="AAPL", market_country="US", side="SELL",
                   order_type="MARKET", price=None,
                   quantity=D("0.0123451")).payload()

    def test_fractional_requires_us_regular_session_not_just_market_open(self):
        order = intent(symbol="AAPL", market_country="US", side="SELL",
                       order_type="MARKET", price=None, quantity=D("0.012345"))
        # In October daylight time: 13:29 UTC is 09:29 EDT; 19:00 UTC is 15:00 EDT.
        for t in (datetime(2026, 10, 15, 13, 29, tzinfo=UTC),
                  datetime(2026, 10, 15, 19, 0, tzinfo=UTC),
                  datetime(2026, 10, 17, 14, 0, tzinfo=UTC)):
            with self.subTest(t=t), self.assertRaises(DryRunRejected):
                OfflineTossPaperGateway().preview(
                    order, ctx(now=t, quote_at=t - timedelta(seconds=2),
                               reference_price=D("320"),
                               sellable_quantity=D("0.012345"),
                               max_notional=D("100")))

    def test_fractional_sellable_quantity_must_cover_full_position(self):
        t = datetime(2026, 10, 15, 14, tzinfo=UTC)
        order = intent(symbol="AAPL", market_country="US", side="SELL",
                       order_type="MARKET", price=None, quantity=D("0.012345"))
        with self.assertRaises(DryRunRejected):
            OfflineTossPaperGateway().preview(
                order, ctx(now=t, quote_at=t - timedelta(seconds=2),
                           reference_price=D("320"), max_notional=D("100"),
                           sellable_quantity=D("0.012344")))


if __name__ == "__main__":
    unittest.main()
