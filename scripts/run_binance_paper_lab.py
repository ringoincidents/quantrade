from __future__ import annotations

import argparse
import json
from pathlib import Path

from quantrade.institutional.trading_lab import (
    BinanceSpotPublicMarketData,
    MarketObservation,
    MarketScope,
    StrategyPassport,
    advance_paper_state,
    build_trading_floor_snapshot,
    new_paper_state,
    paper_account_metrics,
    sma_trend_control,
)


def _read_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("paper state root must be an object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run QT-LIVE-001 as a stateful paper-only Binance experiment."
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="4h")
    parser.add_argument("--capital-usd", type=float, default=30.0)
    parser.add_argument("--fee-rate", type=float, default=0.001)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument(
        "--base-url",
        default="https://data-api.binance.vision",
        help="Binance public market-data base URL; no credential is used.",
    )
    parser.add_argument("--offline-price", type=float)
    parser.add_argument("--observed-at")
    parser.add_argument("--source-url")
    parser.add_argument("--state", default="paper_trading_state.json")
    parser.add_argument("--output", default="paper_trading_snapshot.json")
    args = parser.parse_args()

    scope = MarketScope(
        asset_class="CRYPTO",
        venue="BINANCE_SPOT",
        universe=(args.symbol.upper(),),
        quote_currency="USDT",
        timeframe=args.interval,
    )
    strategy = StrategyPassport(
        strategy_id="STR-BIN-TREND-CONTROL-001",
        name="Binance SMA trend control",
        hypothesis=(
            "A simple short/long moving-average trend rule is useful as an "
            "infrastructure control, not as validated alpha."
        ),
    )

    if args.offline_price is not None:
        if not args.observed_at or not args.source_url:
            parser.error("--offline-price requires --observed-at and --source-url")
        observation = MarketObservation(
            venue="BINANCE_SPOT",
            symbol=args.symbol.upper(),
            price=args.offline_price,
            observed_at=args.observed_at,
            source=args.source_url,
        )
        trend = sma_trend_control([])
    else:
        market = BinanceSpotPublicMarketData(base_url=args.base_url)
        observation = market.ticker_price(args.symbol)
        candles = market.klines(args.symbol, interval=args.interval, limit=61)
        trend = sma_trend_control(candle.close for candle in candles)

    state_path = Path(args.state)
    state = _read_state(state_path)
    if state is None:
        state = new_paper_state(
            starting_capital_usd=args.capital_usd,
            benchmark_seed_price=observation.price,
            benchmark_seed_at=observation.observed_at,
        )

    signal = str(trend.get("signal", "NO_TRADE"))
    state, paper_event = advance_paper_state(
        state,
        observation=observation,
        signal=signal,
        strategy_id=strategy.strategy_id,
        fee_rate=args.fee_rate,
        slippage_bps=args.slippage_bps,
    )
    metrics = paper_account_metrics(
        state,
        mark_price=observation.price,
        fee_rate=args.fee_rate,
    )

    snapshot = build_trading_floor_snapshot(
        observation=observation,
        capital_usd=float(state["starting_capital_usd"]),
        fee_rate=args.fee_rate,
        strategy=strategy,
        scope=scope,
        trend_control=trend,
    )
    snapshot["cash_account_usd"] = metrics["cash_usd"]
    snapshot["paper_account"] = {
        "position": state.get("position"),
        **metrics,
        "fee_rate_assumption": args.fee_rate,
        "slippage_bps_assumption": args.slippage_bps,
    }
    snapshot["benchmark"] = {
        "type": "BUY_AND_HOLD_BENCHMARK",
        "symbol": observation.symbol,
        "seed_price": state["benchmark_seed_price"],
        "seed_observed_at": state["benchmark_seed_at"],
        "capital_usd": state["starting_capital_usd"],
        "current_value_usd_before_costs": metrics[
            "benchmark_value_usd_before_costs"
        ],
        "return_pct_before_costs": metrics[
            "benchmark_return_pct_before_costs"
        ],
        "current_mark_price": observation.price,
    }
    snapshot["trade_episodes"] = state.get("closed_episodes", [])
    snapshot["last_paper_event"] = paper_event
    snapshot["experiment_state"] = (
        "RUNNING" if trend.get("state") == "READY" else "WARMING_UP"
    )
    snapshot["paper_engine"] = {
        "state_schema": state["schema"],
        "real_orders_possible": False,
        "authenticated_exchange_api_used": False,
    }

    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output = Path(args.output)
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
