"""Only synthetic data. Never call a broker or use real API keys."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from toss_one_shot_aapl import one_shot, OrderPreflightBlocked, LIVE_AUTHORIZATION

TIME = datetime(2026, 10, 15, 14, 37, tzinfo=timezone.utc)


class FakeBroker:
    def __init__(self, qty="0.008731", sellable="0.008731", price="320",
                 open_orders=None, closed_orders=None, market_open=True):
        self.qty, self.sellable, self.price = qty, sellable, price
        self.open_orders = open_orders or []
        self.closed_orders = closed_orders or []
        self.calls = []
        self.market_open = market_open

    def login(self):
        self.calls.append("login")
        return "FAKE_TOKEN", [{"accountSeq": "FAKE"}]

    def calendar(self, date):
        self.calls.append("calendar")
        return {"today": {
            "date": date,
            "regularMarket": {
                "startTime": "2026-10-15T22:30:00+09:00",
                "endTime": "2026-10-16T05:00:00+09:00",
            } if self.market_open else None,
        }}

    def get(self, path, token, account, params=None):
        self.calls.append("GET " + path)
        if path == "/api/v1/holdings":
            return {"items": [{"symbol": "AAPL", "marketCountry": "US",
                              "quantity": self.qty, "lastPrice": self.price}]}
        if path == "/api/v1/sellable-quantity":
            return {"sellableQuantity": self.sellable}
        if path == "/api/v1/orders" and params and params["status"] == "OPEN":
            return {"orders": self.open_orders, "hasNext": False}
        if path == "/api/v1/orders" and params and params["status"] == "CLOSED":
            return {"orders": self.closed_orders, "hasNext": False}
        if path.startswith("/api/v1/orders/"):
            return {"status": "PENDING"}
        raise AssertionError("unknown GET path")

    def post_once(self, path, token, account, payload):
        self.calls.append("POST " + path)
        self.last_payload = payload
        return {"orderId": "fake-id", "clientOrderId": payload["clientOrderId"]}


class OneShotTests(unittest.TestCase):
    def live(self, broker, now=TIME, confirm=LIVE_AUTHORIZATION):
        with patch.dict(os.environ, {
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_RUN_ATTEMPT": "1",
            "TOSS_LIVE_ORDER_GATE": "EXPLICIT_ONE_SHOT",
        }):
            return one_shot(broker, now=now, mode="LIVE_ONCE", authorization=confirm)

    def test_read_only_no_post(self):
        b = FakeBroker()
        self.assertEqual(one_shot(b, now=TIME)["status"], "READ_ONLY_READY")
        self.assertFalse(any(c.startswith("POST") for c in b.calls))

    def test_exactly_one_bounded_market_sell(self):
        b = FakeBroker()
        result = self.live(b)
        self.assertEqual(result["status"], "BROKER_ACK_RECEIVED")
        self.assertEqual(sum(c.startswith("POST") for c in b.calls), 1)
        self.assertEqual(b.last_payload, {
            "symbol": "AAPL", "side": "SELL", "orderType": "MARKET",
            "quantity": "0.008731", "timeInForce": "DAY",
            "clientOrderId": "qtAAPL20261015once01",
        })

    def test_wrong_confirmation_blocks(self):
        b = FakeBroker()
        with self.assertRaises(OrderPreflightBlocked):
            self.live(b, confirm="")
        self.assertFalse(any(c.startswith("POST") for c in b.calls))

    def test_push_trigger_blocks_live(self):
        with patch.dict(os.environ, {
            "GITHUB_EVENT_NAME": "push", "GITHUB_RUN_ATTEMPT": "1",
            "TOSS_LIVE_ORDER_GATE": "EXPLICIT_ONE_SHOT",
        }):
            with self.assertRaises(OrderPreflightBlocked):
                one_shot(FakeBroker(), now=TIME, mode="LIVE_ONCE",
                         authorization=LIVE_AUTHORIZATION)

    def test_schedule_retry_blocks(self):
        with patch.dict(os.environ, {
            "GITHUB_EVENT_NAME": "schedule", "GITHUB_RUN_ATTEMPT": "2",
            "TOSS_LIVE_ORDER_GATE": "EXPLICIT_ONE_SHOT",
        }):
            with self.assertRaises(OrderPreflightBlocked):
                one_shot(FakeBroker(), now=TIME, mode="LIVE_ONCE",
                         authorization=LIVE_AUTHORIZATION)

    def test_wrong_date_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(), now=TIME + timedelta(days=1))

    def test_before_regular_session_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(), now=datetime(2026, 10, 15, 13, 32,
                                                tzinfo=timezone.utc))

    def test_after_fractional_session_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(), now=TIME + timedelta(hours=5))

    def test_holiday_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(market_open=False))

    def test_qty_greater_than_small_fraction_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(qty="0.01"))

    def test_sellable_shortfall_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(sellable="0"))

    def test_existing_open_sell_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(open_orders=[{"symbol":"AAPL","side":"SELL"}]))

    def test_prior_order_id_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(closed_orders=[
                {"symbol":"AAPL", "clientOrderId":"qtAAPL20261015once01"}]))

    def test_high_notional_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(price="5000"))

    def test_bad_quantity_blocks(self):
        with self.assertRaises(OrderPreflightBlocked):
            self.live(FakeBroker(qty="NaN"))

    def test_ambiguous_response_never_retries_post(self):
        class UnknownAck(FakeBroker):
            def post_once(self, path, token, account, payload):
                self.calls.append("POST " + path)
                return {}
        b = UnknownAck()
        self.assertEqual(self.live(b)["status"], "AMBIGUOUS_SUBMIT")
        self.assertEqual(sum(c.startswith("POST") for c in b.calls), 1)

    def test_ack_key_mismatch_flags_error(self):
        class BadAck(FakeBroker):
            def post_once(self, path, token, account, payload):
                return {"orderId":"x", "clientOrderId":"wrong"}
        self.assertEqual(self.live(BadAck())["status"], "BROKER_ACK_KEY_MISMATCH")

    def test_ambiguous_pagination_blocks(self):
        class Paged(FakeBroker):
            def get(self, path, token, account, params=None):
                if path == "/api/v1/orders" and params and params["status"] == "CLOSED":
                    return {"orders": [], "hasNext": True}
                return super().get(path, token, account, params)
        with self.assertRaises(OrderPreflightBlocked):
            self.live(Paged())


if __name__ == "__main__":
    unittest.main()
