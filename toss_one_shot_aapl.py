"""Dated, user-authorized AAPL fractional SELL experiment. Default READ_ONLY.
One POST attempt only; no retry on errors or ambiguous broker responses.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import os
from zoneinfo import ZoneInfo

SYMBOL = "AAPL"
MAX_QUANTITY = Decimal("0.01")
MAX_NOTIONAL_USD = Decimal("10")
EXPECTED_US_SESSION_DATE = "2026-10-15"
CLIENT_ORDER_ID = "qtAAPL20261015once01"
LIVE_AUTHORIZATION = "CONFIRM_AAPL_FRACTIONAL_MARKET_SELL"
NY = ZoneInfo("America/New_York")


class OrderPreflightBlocked(Exception):
    pass


def _number(value):
    if isinstance(value, (float, bool)):
        raise OrderPreflightBlocked("INVALID_DECIMAL")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise OrderPreflightBlocked("INVALID_DECIMAL") from None
    if not d.is_finite() or d < 0:
        raise OrderPreflightBlocked("INVALID_DECIMAL")
    return d


def _timestamp(s):
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            raise ValueError
        return d
    except (ValueError, TypeError):
        raise OrderPreflightBlocked("INVALID_MARKET_CALENDAR") from None


def _date_and_session(calendar, now):
    day = now.astimezone(NY).date().isoformat()
    if day != EXPECTED_US_SESSION_DATE:
        raise OrderPreflightBlocked("WRONG_US_TRADING_DATE")
    session = calendar.get("today", {})
    if session.get("date") != day:
        raise OrderPreflightBlocked("MARKET_DATE_MISMATCH")
    regular = session.get("regularMarket") or {}
    begin = _timestamp(regular.get("startTime"))
    end = _timestamp(regular.get("endTime"))
    if not (begin + timedelta(minutes=5) <= now <= end - timedelta(hours=1, minutes=5)):
        raise OrderPreflightBlocked("OUTSIDE_FRACTIONAL_ORDER_WINDOW")


def _holding_and_open_orders(client, token, account, *, want_live):
    holdings = client.get("/api/v1/holdings", token, account)
    matched = [h for h in holdings.get("items", [])
               if h.get("symbol") == SYMBOL and h.get("marketCountry") == "US"]
    if len(matched) != 1:
        raise OrderPreflightBlocked("AAPL_POSITION_AMBIGUOUS")
    quantity = _number(matched[0].get("quantity"))
    # Never publish the actual client holding in source code or workflow logs.
    if not (Decimal("0") < quantity < MAX_QUANTITY):
        raise OrderPreflightBlocked("AAPL_OUTSIDE_SMALL_FRACTIONAL_SCOPE")
    if max(0, -quantity.as_tuple().exponent) > 6:
        raise OrderPreflightBlocked("AAPL_FRACTIONAL_SCALE_UNSUPPORTED")
    quote = _number(matched[0].get("lastPrice"))
    if quote <= 0 or quantity * quote > MAX_NOTIONAL_USD:
        raise OrderPreflightBlocked("QUOTE_NOTIONAL_EXCEEDS_CAP")
    sellable = client.get("/api/v1/sellable-quantity", token, account,
                          params={"symbol": SYMBOL})
    if _number(sellable.get("sellableQuantity")) < quantity:
        raise OrderPreflightBlocked("INSUFFICIENT_SELLABLE_AAPL")
    opened = client.get("/api/v1/orders", token, account, params={"status": "OPEN"})
    if not isinstance(opened.get("orders"), list) or opened.get("hasNext") is not False:
        raise OrderPreflightBlocked("INCOMPLETE_OPEN_ORDER_LIST")
    if any(o.get("symbol") == SYMBOL and o.get("side") == "SELL"
           for o in opened["orders"]):
        raise OrderPreflightBlocked("OPEN_AAPL_SELL_EXISTS")
    if want_live:
        cursor = None
        seen = set()
        for _ in range(25):
            params = {"status": "CLOSED"}
            if cursor:
                params["cursor"] = cursor
            closed = client.get("/api/v1/orders", token, account, params=params)
            if not isinstance(closed.get("orders"), list):
                raise OrderPreflightBlocked("MALFORMED_CLOSED_ORDER_LIST")
            if any(o.get("clientOrderId") == CLIENT_ORDER_ID
                   for o in closed["orders"]):
                raise OrderPreflightBlocked("ORDER_ALREADY_ATTEMPTED")
            if closed.get("hasNext") is False:
                break
            cursor = closed.get("nextCursor")
            if not cursor or cursor in seen:
                raise OrderPreflightBlocked("CLOSED_ORDER_PAGINATION_FAILED")
            seen.add(cursor)
        else:
            raise OrderPreflightBlocked("CLOSED_ORDER_PAGINATION_LIMIT")
    return quantity


def one_shot(client, *, now, mode="READ_ONLY", authorization=""):
    if mode not in ("READ_ONLY", "LIVE_ONCE"):
        raise OrderPreflightBlocked("INVALID_MODE")
    if now.tzinfo is None:
        raise OrderPreflightBlocked("CLOCK_NOT_AWARE")
    live = mode == "LIVE_ONCE"
    if live and authorization != LIVE_AUTHORIZATION:
        raise OrderPreflightBlocked("EXPLICIT_EXECUTION_CONFIRMATION_REQUIRED")
    if live and os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        raise OrderPreflightBlocked("ONLY_EXPLICIT_ONE_TIME_SCHEDULE_ALLOWED")
    if live and os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise OrderPreflightBlocked("SCHEDULE_RERUN_FORBIDDEN")
    if live and os.environ.get("TOSS_LIVE_ORDER_GATE") != "EXPLICIT_ONE_SHOT":
        raise OrderPreflightBlocked("LIVE_GATE_DISABLED")
    if live:
        _date_and_session(client.calendar(now.astimezone(NY).date().isoformat()), now)
    token, accounts = client.login()
    if len(accounts) != 1:
        raise OrderPreflightBlocked("ACCOUNT_SELECTION_AMBIGUOUS")
    account = accounts[0]["accountSeq"]
    quantity = _holding_and_open_orders(client, token, account, want_live=live)
    if not live:
        return {"status": "READ_ONLY_READY", "broker_order_sent": False}
    payload = {
        "symbol": SYMBOL, "side": "SELL", "orderType": "MARKET",
        "quantity": format(quantity, "f"), "timeInForce": "DAY",
        "clientOrderId": CLIENT_ORDER_ID,
    }
    # NEVER retry the order POST: after timeout acceptance is unknown.
    response = client.post_once("/api/v1/orders", token, account, payload)
    if not isinstance(response, dict) or not isinstance(response.get("orderId"), str) or not response["orderId"]:
        return {"status": "AMBIGUOUS_SUBMIT", "broker_order_sent": True}
    order_id = response["orderId"]
    if response.get("clientOrderId") != CLIENT_ORDER_ID:
        return {"status": "BROKER_ACK_KEY_MISMATCH", "broker_order_sent": True}
    try:
        state = client.get(f"/api/v1/orders/{order_id}", token, account)
        status = str(state.get("status", "UNKNOWN"))
    except Exception:
        status = "STATUS_QUERY_FAILED"
    return {"status": "BROKER_ACK_RECEIVED", "order_status": status, "broker_order_sent": True}


class RealTossClient:
    def __init__(self):
        from real_portfolio_sync import _get_result, get_access_token, _request
        self._get = _get_result
        self._token = get_access_token
        self._request = _request

    def login(self):
        token = self._token()
        return token, self._get("/api/v1/accounts", token)

    def calendar(self, date):
        token = self._token()
        return self._get("/api/v1/market-calendar/US", token, params={"date": date})

    def get(self, path, token, account, params=None):
        return self._get(path, token, account_seq=account, params=params)

    def post_once(self, path, token, account, payload):
        # Existing wrapper makes a single HTTP request (no retry policy).
        body = self._request("POST", path, token=token, account_seq=account, json=payload)
        return body.get("result")


def main():
    from real_portfolio_sync import check_proxy_ip
    mode = os.environ.get("ONE_SHOT_MODE", "READ_ONLY")
    try:
        if check_proxy_ip(expected_ip="141.164.41.178") is not True:
            raise OrderPreflightBlocked("PROXY_IP_MISMATCH")
        result = one_shot(
            RealTossClient(),
            now=datetime.now(timezone.utc),
            mode=mode,
            authorization=os.environ.get("ONE_SHOT_CONFIRMATION", ""),
        )
        print("ONE_SHOT_STATUS=" + result["status"])
        print("BROKER_ORDER_SENT=" + str(result["broker_order_sent"]).lower())
        if "order_status" in result:
            print("BROKER_ORDER_STATUS=" + result["order_status"])
        if result["status"] not in ("READ_ONLY_READY", "BROKER_ACK_RECEIVED"):
            raise SystemExit(2)
    except OrderPreflightBlocked as exc:
        print("ONE_SHOT_STATUS=BLOCKED_" + str(exc))
        print("BROKER_ORDER_SENT=false")
        raise SystemExit(2)
    except Exception as exc:
        # No raw broker response, credentials, holdings, prices or IDs in public logs.
        print("ONE_SHOT_STATUS=ERROR_OR_AMBIGUOUS")
        print("ERROR_TYPE=" + type(exc).__name__)
        print("BROKER_ORDER_SENT=UNKNOWN_IF_LIVE")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
