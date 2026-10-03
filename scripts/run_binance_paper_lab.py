from __future__ import annotations

import argparse
import json
from pathlib import Path

from quantrade.institutional.trading_lab import (
    BinanceSpotPublicMarketData,
    MarketObservation,
    MarketScope,
    StrategyPassport,
    build_trading_floor_snapshot,
    sma_trend_control,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run QT-LIVE-001 as a paper-only Binance market-data experiment."
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="4h")
    parser.add_argument("--capital-usd", type=float, default=30.0)
    parser.add_argument("--fee-rate", type=float, default=0.001)
    parser.add_argument("--offline-price", type=float)
    parser.add_argument("--observed-at")
    parser.add_argument("--source-url")
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
        market = BinanceSpotPublicMarketData()
        observation = market.ticker_price(args.symbol)
        candles = market.klines(args.symbol, interval=args.interval, limit=61)
        trend = sma_trend_control(candle.close for candle in candles)

    snapshot = build_trading_floor_snapshot(
        observation=observation,
        capital_usd=args.capital_usd,
        fee_rate=args.fee_rate,
        strategy=strategy,
        scope=scope,
        trend_control=trend,
    )

    output = Path(args.output)
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
