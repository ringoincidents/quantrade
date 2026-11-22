"""Log-safe, manual GitHub Actions read-only Binance Spot credential probe.

No trades, no balances in logs, no HTTP write requests.
"""
from __future__ import annotations

import json
import os
from quantrade.connectors.binance_spot_readonly import (
    AccountReadOnly, BinanceReadOnlyError, PublicSpotData,
)


def main() -> int:
    result = {
        "connector": "binance_spot_readonly",
        "public_data": "NOT_TESTED",
        "private_account": "NOT_CONFIGURED",
        "orders_enabled": False,
    }
    try:
        PublicSpotData().server_time()
        result["public_data"] = "OK"
    except BinanceReadOnlyError:
        result["public_data"] = "FAILED"

    key = os.getenv("QUANTRADE_BINANCE_API_KEY")
    secret = os.getenv("QUANTRADE_BINANCE_API_SECRET")
    if key and secret:
        try:
            account = AccountReadOnly.from_environment()
            account.verified_permissions()
            # Verify signed account response without exposing actual balances.
            account.balances()
            result["private_account"] = "VERIFIED_READ_ONLY"
        except BinanceReadOnlyError:
            result["private_account"] = "FAILED"
    elif key or secret:
        result["private_account"] = "PARTIAL_CREDENTIALS"

    print(json.dumps(result))
    return 0 if result["private_account"] == "VERIFIED_READ_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
