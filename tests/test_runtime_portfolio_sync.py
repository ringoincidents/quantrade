from __future__ import annotations

from runtime_portfolio_sync import (
    OIDC_AUDIENCE,
    RuntimePortfolioSyncError,
    _oidc_url,
    build_runtime_payload,
    push_runtime_snapshot,
)


def test_payload_minimizes_broker_output():
    payload = build_runtime_payload(
        {
            "cash": 100.0,
            "positions": [
                {
                    "symbol": "AAA",
                    "name": "Alpha",
                    "currency": "USD",
                    "quantity": "2",
                    "eval_amount": 123.45,
                    "eval_amount_krw": 200000.0,
                    "return_pct": 3.2,
                    "account_number": "must-not-leak",
                }
            ],
        },
        synced_at="2026-10-05T05:00:00+00:00",
    )

    assert payload["cash_krw"] == 100.0
    assert payload["synced_at"] == "2026-10-05T05:00:00+00:00"
    position = payload["positions"][0]
    assert position["symbol"] == "AAA"
    assert position["eval_amount_krw"] == 200000.0
    assert "eval_amount" not in position
    assert "account_number" not in position


def test_payload_requires_symbol():
    try:
        build_runtime_payload({"positions": [{"quantity": 1}]})
        raised = False
    except RuntimePortfolioSyncError:
        raised = True
    assert raised is True


def test_oidc_url_adds_exact_audience_without_dropping_existing_query():
    url = _oidc_url("https://token.actions.example/id?api-version=2.0")
    assert "api-version=2.0" in url
    assert f"audience={OIDC_AUDIENCE}" in url


class _Response:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class _Session:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response(
            {
                "portfolio_state": {
                    "status": "FRESH",
                    "snapshot": {"id": "QTPS-TEST", "position_count": 1},
                }
            }
        )


def test_runtime_push_uses_oidc_bearer_and_private_endpoint():
    session = _Session()
    result = push_runtime_snapshot(
        {
            "synced_at": "2026-10-05T05:00:00+00:00",
            "cash_krw": 0,
            "positions": [{"symbol": "AAA"}],
        },
        runtime_url="https://runtime.example",
        oidc_token="short-lived",
        session=session,
    )

    assert result["portfolio_state"]["status"] == "FRESH"
    url, kwargs = session.calls[0]
    assert url == "https://runtime.example/clients/quantrade/portfolio-state/github-oidc"
    assert kwargs["headers"]["Authorization"] == "Bearer short-lived"
