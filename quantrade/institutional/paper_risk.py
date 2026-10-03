from __future__ import annotations

from typing import Any


PAPER_RISK_POLICY_VERSION = "qt-live-003-paper-risk-v1"


class PaperRiskPacketError(ValueError):
    pass


def build_paper_review_inputs(
    *,
    trading_floor: dict[str, Any],
    private_strategy_envelope: dict[str, Any],
) -> dict[str, Any]:
    """Build deterministic portfolio/risk inputs for QT-LIVE-003 PAPER review.

    This adapter deliberately does not convert KRW Client loss amounts into USD.
    Only percentage-based Client limits may be applied without an explicit,
    versioned FX input.
    """

    if trading_floor.get("schema") != "quantrade_trading_floor_v1":
        raise PaperRiskPacketError("unsupported trading floor schema")
    if trading_floor.get("mode") != "PAPER":
        raise PaperRiskPacketError("paper review requires PAPER trading floor")
    if trading_floor.get("live_execution_authorized") is not False:
        raise PaperRiskPacketError("paper review must not grant live execution")
    if (
        private_strategy_envelope.get("schema")
        != "quantrade_private_strategy_envelope_v1"
    ):
        raise PaperRiskPacketError("private Strategy Envelope is required")

    starting_capital = float(trading_floor.get("starting_capital_usd") or 0.0)
    if starting_capital <= 0:
        raise PaperRiskPacketError("starting_capital_usd must be positive")

    paper = trading_floor.get("paper_account") or {}
    equity = float(paper.get("equity_usd") or 0.0)
    cash = float(paper.get("cash_usd") or 0.0)
    position = paper.get("position")
    position_value = float(paper.get("position_market_value_usd") or 0.0)
    total_return_pct = float(paper.get("total_return_pct") or 0.0)

    if equity < 0 or cash < 0 or position_value < 0:
        raise PaperRiskPacketError("paper account values cannot be negative")

    exposure_pct_of_start = (
        position_value / starting_capital * 100.0
        if starting_capital
        else 0.0
    )
    loss_from_start_pct = max(0.0, -total_return_pct)

    risk_capacity = private_strategy_envelope.get("risk_capacity") or {}
    max_drawdown_pct_raw = risk_capacity.get("effective_max_drawdown_pct")
    max_drawdown_pct = (
        float(max_drawdown_pct_raw)
        if max_drawdown_pct_raw is not None
        else None
    )
    if max_drawdown_pct is not None and not 0 <= max_drawdown_pct <= 100:
        raise PaperRiskPacketError("effective_max_drawdown_pct is invalid")

    drawdown_limit_breach = bool(
        max_drawdown_pct is not None
        and loss_from_start_pct > max_drawdown_pct
    )

    venue = str(
        (trading_floor.get("market_scope") or {}).get("venue") or ""
    )
    asset_class = str(
        (trading_floor.get("market_scope") or {}).get("asset_class") or ""
    )
    quote_currency = str(
        (trading_floor.get("market_scope") or {}).get("quote_currency") or ""
    )
    validation = str(trading_floor.get("current_validation") or "UNKNOWN")

    snapshot = {
        "schema": "quantrade_paper_portfolio_snapshot_v1",
        "experiment_id": "QT-LIVE-003",
        "mode": "PAPER",
        "starting_capital_usd": starting_capital,
        "equity_usd": equity,
        "cash_usd": cash,
        "position_market_value_usd": position_value,
        "position": position,
        "total_return_pct": total_return_pct,
        "exposure_pct_of_starting_capital": exposure_pct_of_start,
        "market_scope": {
            "venue": venue,
            "asset_class": asset_class,
            "quote_currency": quote_currency,
            "symbol": (
                (trading_floor.get("market_observation") or {}).get("symbol")
            ),
        },
        "strategy_validation": validation,
        "live_execution_authorized": False,
        "source_experiment_id": trading_floor.get("experiment_id"),
        "source_generated_at": trading_floor.get("generated_at"),
    }

    client_max_loss_krw = risk_capacity.get("max_loss_krw")
    risk_result = {
        "schema": "quantrade_paper_risk_assessment_v1",
        "deterministic": True,
        "llm_used": False,
        "policy_version": PAPER_RISK_POLICY_VERSION,
        "policy_breach": drawdown_limit_breach,
        "drawdown_limit_breach": drawdown_limit_breach,
        "capital_loss_from_start_pct": loss_from_start_pct,
        "client_percentage_limit_available": max_drawdown_pct is not None,
        "client_max_drawdown_pct": max_drawdown_pct,
        "position_exposure_pct_of_starting_capital": exposure_pct_of_start,
        "spot_only_scope": venue.upper() == "BINANCE_SPOT",
        "leverage_authorized": False,
        "strategy_validation": validation,
        "validation_warning": (
            None
            if validation in {"PAPER_VALIDATED", "MICRO_LIVE_VALIDATED"}
            else "STRATEGY_NOT_VALIDATED_AS_ALPHA"
        ),
        "currency_policy": {
            "paper_currency": "USD",
            "client_loss_limit_currency": (
                "KRW" if client_max_loss_krw is not None else None
            ),
            "fx_rate_supplied": False,
            "cross_currency_loss_limit_compared": False,
            "reason": (
                "Client KRW max-loss amount is not compared with PAPER USD "
                "capital without an explicit versioned FX input."
            ),
        },
        "limitations": [
            (
                "capital_loss_from_start_pct is a loss-from-start measure, "
                "not peak-to-trough maximum drawdown"
            ),
            "PAPER execution is not evidence of live execution quality",
            "strategy validation does not transfer across venues or markets",
        ],
        "live_execution_authorized": False,
    }

    return {
        "schema": "quantrade_paper_review_inputs_v1",
        "portfolio_snapshot": snapshot,
        "deterministic_risk_result": risk_result,
        "risk_policy_version": PAPER_RISK_POLICY_VERSION,
        "private_values_publicly_persistable": False,
        "live_execution_authorized": False,
    }
