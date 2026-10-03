from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quantrade.institutional.chart_workstation import (
    AICallGate,
    MarketStateCompiler,
)
from quantrade.institutional.strategy_director import compile_company_strategy
from quantrade.institutional.trading_lab import BinanceSpotPublicMarketData


PRIVATE_CLIENT_SCHEMA = "quantrade_private_client_strategy_brief_v1"
PRECHECK_SCHEMA = "quantrade_institutional_case_precheck_v1"


def _iso_from_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).isoformat()


def _bars_from_binance(candles) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": _iso_from_ms(candle.open_time_ms),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        for candle in candles
    ]


def build_precheck(
    *,
    private_client_brief: dict[str, Any],
    bars: list[dict[str, Any]],
    symbol: str,
    timeframe: str,
    market_source: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    if private_client_brief.get("schema") != PRIVATE_CLIENT_SCHEMA:
        raise ValueError("unsupported private Client strategy brief schema")
    if private_client_brief.get("source") != "LLM_HOLDINGS_CLIENT_INTELLIGENCE":
        raise ValueError("unsupported private Client strategy brief source")
    boundaries = private_client_brief.get("boundaries") or {}
    if boundaries.get("public_repository_persistence_allowed") is not False:
        raise ValueError(
            "private Client brief must explicitly forbid public persistence"
        )

    strategy_ready = bool(private_client_brief.get("strategy_ready"))
    missing = list(private_client_brief.get("missing_information") or [])
    withheld = list(
        private_client_brief.get("withheld_client_office_only") or []
    )
    facts = list(private_client_brief.get("facts") or [])

    # Raw Client values are intentionally not copied into the public artifact.
    planning_conflicts: list[str] = []
    if not strategy_ready:
        planning_conflicts.append("CLIENT_INTELLIGENCE_INCOMPLETE")

    mandate = {
        "planning_conflicts": planning_conflicts,
        "human_approval_required_for_live_execution": True,
    }
    strategy_directive = compile_company_strategy(
        mandate=mandate,
        client_state={},
        portfolio_state={},
        research_state={},
    )

    market_state = MarketStateCompiler.compile(
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": bars,
        }
    )
    ai_gate = AICallGate.evaluate(
        {
            "market_state": market_state,
            "mandate_state": mandate,
            "portfolio_state": {},
            "research_state": {},
        }
    )

    if not strategy_ready:
        next_stage = "CLIENT_STRATEGY_REVIEW"
    elif ai_gate["call_ai"]:
        next_stage = "BOUNDED_AI_REVIEW"
    else:
        next_stage = "NO_AI_REVIEW"

    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema": PRECHECK_SCHEMA,
        "experiment_id": "QT-LIVE-003",
        "run_id": run_id,
        "mode": "PAPER_PRECHECK",
        "generated_at": generated_at,
        "market_source": market_source,
        "market_state": market_state,
        "client_context": {
            "strategy_ready": strategy_ready,
            "available_fact_count": len(facts),
            "missing_information_keys": missing,
            "withheld_information_keys": withheld,
            "raw_values_persisted": False,
            "source_request_id": private_client_brief.get("request_id"),
            "source_brief_id": private_client_brief.get("brief_id"),
        },
        "strategy_directive": strategy_directive,
        "ai_call_gate": ai_gate,
        "next_stage": next_stage,
        "authority": {
            "ai_called": False,
            "investment_committee_decision_created": False,
            "decision_plan_created": False,
            "paper_execution_created": False,
            "live_execution_authorized": False,
        },
        "privacy": {
            "private_client_values_in_output": False,
            "private_client_input_should_be_deleted_after_run": True,
        },
        "note": (
            "This artifact is a deterministic pre-check. It does not create a "
            "security recommendation or bypass Research / Portfolio / Risk / IC."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the first deterministic live-data Institutional Case pre-check. "
            "No AI provider or order API is used."
        )
    )
    parser.add_argument(
        "--client-brief",
        default="client_strategy_input.json",
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--bar-limit", type=int, default=120)
    parser.add_argument(
        "--base-url",
        default="https://data-api.binance.vision",
    )
    parser.add_argument(
        "--output",
        default="institutional_case_precheck.json",
    )
    parser.add_argument("--run-id")
    args = parser.parse_args()

    private_brief = json.loads(
        Path(args.client_brief).read_text(encoding="utf-8")
    )
    market = BinanceSpotPublicMarketData(base_url=args.base_url)
    candles = market.klines(
        args.symbol,
        interval=args.timeframe,
        limit=args.bar_limit,
    )
    bars = _bars_from_binance(candles)
    market_source = market._url(
        "/api/v3/klines",
        {
            "symbol": args.symbol.upper(),
            "interval": args.timeframe,
            "limit": args.bar_limit,
        },
    )
    result = build_precheck(
        private_client_brief=private_brief,
        bars=bars,
        symbol=args.symbol.upper(),
        timeframe=args.timeframe,
        market_source=market_source,
        run_id=args.run_id,
    )
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "schema": result["schema"],
        "experiment_id": result["experiment_id"],
        "next_stage": result["next_stage"],
        "strategy_ready": result["client_context"]["strategy_ready"],
        "ai_review_requested": result["ai_call_gate"]["call_ai"],
        "private_values_persisted": False,
        "live_execution_authorized": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
