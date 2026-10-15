"""One-shot read-only AAPL fractional-order preflight.

No broker order/modify/cancel endpoint is called. Never print account IDs,
position sizes, balances, tokens, or full broker responses to public CI logs.
Main-branch-only workflow can supply existing read-only OAuth credentials.
"""
from decimal import Decimal, InvalidOperation

from real_portfolio_sync import check_proxy_ip, get_access_token, _get_result

EXPECTED_EGRESS = "141.164.41.178"
SYMBOL = "AAPL"


def parse_decimal(s):
    try:
        n = Decimal(str(s))
        if not n.is_finite() or n < 0:
            return None
        return n
    except (InvalidOperation, ValueError):
        return None


def main():
    if check_proxy_ip(expected_ip=EXPECTED_EGRESS) is not True:
        print("AAPL_PREFLIGHT=BLOCKED_PROXY_IP")
        return
    try:
        token = get_access_token()
        accounts = _get_result("/api/v1/accounts", token)
        if not accounts:
            print("AAPL_PREFLIGHT=BLOCKED_ACCOUNT_NOT_FOUND")
            return

        # Same default account selection as existing real_portfolio_sync.py.
        account_seq = accounts[0]["accountSeq"]
        positions = _get_result("/api/v1/holdings", token, account_seq=account_seq)
        aapl = [p for p in positions.get("items", []) if p.get("symbol") == SYMBOL]
        if len(aapl) != 1:
            print("AAPL_PREFLIGHT=NO_SINGLE_MATCHING_AAPL_POSITION")
            return

        held = parse_decimal(aapl[0].get("quantity"))
        if held is None:
            print("AAPL_PREFLIGHT=BLOCKED_INVALID_HOLDING_RESPONSE")
            return
        available_data = _get_result("/api/v1/sellable-quantity", token,
                                     account_seq=account_seq, params={"symbol": SYMBOL})
        available = parse_decimal(available_data.get("sellableQuantity"))
        if available is None:
            print("AAPL_PREFLIGHT=BLOCKED_INVALID_SELLABLE_RESPONSE")
            return
        order_data = _get_result("/api/v1/orders", token, account_seq=account_seq,
                                 params={"status": "OPEN"})
        open_orders = order_data.get("orders")
        if not isinstance(open_orders, list):
            print("AAPL_PREFLIGHT=BLOCKED_INVALID_ORDERS_RESPONSE")
            return
        has_open_sell = any(o.get("symbol") == SYMBOL and o.get("side") == "SELL"
                            for o in open_orders)
        fraction = held > 0 and held < 1 and max(0, -held.as_tuple().exponent) <= 6
        print("AAPL_PREFLIGHT=GET_ONLY_COMPLETE")
        print("POSITION_EXISTS_AND_FRACTIONAL_6DP=" + str(fraction).lower())
        print("SELLABLE_COVERS_POSITION=" + str(available >= held and held > 0).lower())
        print("HAS_OPEN_AAPL_SELL=" + str(has_open_sell).lower())
        print("ORDER_SUBMITTED=false")
    except Exception as exc:
        # Sanitize diagnostics: never print OAuth errors or raw broker bodies.
        print("AAPL_PREFLIGHT=READ_ONLY_ERROR")
        print("ERROR_CLASS=" + exc.__class__.__name__)


if __name__ == "__main__":
    main()
