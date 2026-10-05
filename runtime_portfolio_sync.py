"""Push the read-only Toss portfolio observation into private LLM Holdings Runtime.

This is the scheduled production sync path after TASK-101. It deliberately does
not persist holdings or P&L artifacts in this public repository.

Authority boundary:
- reads broker account state only through real_portfolio_sync.sync_portfolio();
- obtains a short-lived GitHub Actions OIDC token;
- posts a minimized portfolio observation to the private Runtime;
- never places, modifies or cancels an order.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from real_portfolio_sync import check_proxy_ip, sync_portfolio


OIDC_AUDIENCE = "llm-holdings-quantrade-portfolio-sync"
DEFAULT_RUNTIME_URL = "https://llm-holdings-runtime-production.up.railway.app"
EXPECTED_EGRESS_IP = "141.164.41.178"

_ALLOWED_POSITION_KEYS = (
    "symbol",
    "name",
    "market_country",
    "asset_type",
    "currency",
    "quantity",
    "avg_price",
    "current_price",
    "eval_amount_krw",
    "valuation_pnl_krw",
    "return_pct",
)


class RuntimePortfolioSyncError(RuntimeError):
    pass


def _oidc_url(base_url: str) -> str:
    if not base_url:
        raise RuntimePortfolioSyncError("ACTIONS_ID_TOKEN_REQUEST_URL is required")
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["audience"] = OIDC_AUDIENCE
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def build_runtime_payload(
    data: dict,
    *,
    synced_at: str | None = None,
) -> dict:
    """Minimize broker output to the Runtime's private portfolio contract."""
    positions = []
    for raw in list(data.get("positions") or []):
        if not isinstance(raw, dict):
            raise RuntimePortfolioSyncError("position must be an object")
        symbol = str(raw.get("symbol") or "").strip()
        if not symbol:
            raise RuntimePortfolioSyncError("position symbol is required")
        item = {
            key: raw[key]
            for key in _ALLOWED_POSITION_KEYS
            if key in raw and raw[key] is not None
        }
        item["symbol"] = symbol
        positions.append(item)

    return {
        "synced_at": synced_at or datetime.now(timezone.utc).isoformat(),
        "cash_krw": data.get("cash"),
        "positions": positions,
    }


def request_github_oidc_token(
    *,
    request_url: str,
    request_token: str,
    session=requests,
) -> str:
    if not request_token:
        raise RuntimePortfolioSyncError("ACTIONS_ID_TOKEN_REQUEST_TOKEN is required")
    response = session.get(
        _oidc_url(request_url),
        headers={
            "Authorization": f"Bearer {request_token}",
            "Accept": "application/json",
        },
        timeout=15,
    )
    response.raise_for_status()
    token = str((response.json() or {}).get("value") or "")
    if not token:
        raise RuntimePortfolioSyncError("GitHub OIDC response did not contain a token")
    return token


def push_runtime_snapshot(
    payload: dict,
    *,
    runtime_url: str,
    oidc_token: str,
    session=requests,
) -> dict:
    base = (runtime_url or "").rstrip("/")
    if not base.startswith("https://"):
        raise RuntimePortfolioSyncError("Runtime URL must use https")
    if not oidc_token:
        raise RuntimePortfolioSyncError("OIDC token is required")

    response = session.post(
        f"{base}/clients/quantrade/portfolio-state/github-oidc",
        headers={
            "Authorization": f"Bearer {oidc_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    state = (body or {}).get("portfolio_state") or {}
    if state.get("status") not in {"FRESH", "STALE"}:
        raise RuntimePortfolioSyncError(
            f"Unexpected Runtime portfolio status: {state.get('status')}"
        )
    return body


def main() -> None:
    matched = check_proxy_ip(expected_ip=EXPECTED_EGRESS_IP)
    if matched is not True:
        raise RuntimePortfolioSyncError("Configured fixed egress IP did not match")

    data = sync_portfolio()
    payload = build_runtime_payload(data)

    oidc_token = request_github_oidc_token(
        request_url=os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", ""),
        request_token=os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", ""),
    )
    result = push_runtime_snapshot(
        payload,
        runtime_url=os.environ.get("LLM_HOLDINGS_RUNTIME_URL", DEFAULT_RUNTIME_URL),
        oidc_token=oidc_token,
    )

    state = result["portfolio_state"]
    snapshot = state.get("snapshot") or {}
    # Never print raw holdings values, symbols, cash or token material.
    print(
        "Private Runtime portfolio sync complete: "
        f"status={state.get('status')} "
        f"snapshot_id={snapshot.get('id')} "
        f"position_count={snapshot.get('position_count')} "
        f"synced_at={snapshot.get('synced_at')}"
    )


if __name__ == "__main__":
    main()
