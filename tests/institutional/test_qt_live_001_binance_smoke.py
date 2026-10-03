from __future__ import annotations

import json
import unittest

from quantrade.institutional.trading_lab import (
    BinanceSpotPublicMarketData,
    MarketScope,
    StrategyPassport,
    advance_paper_state,
    paper_account_metrics,
    sma_trend_control,
)


class QtLive001BinanceSmoke(unittest.TestCase):
    def test_live_public_market_smoke(self):
        market = BinanceSpotPublicMarketData(
            base_url="https://data-api.binance.vision"
        )
        observation = market.ticker_price("BTCUSDT")
        candles = market.klines("BTCUSDT", interval="4h", limit=61)
        trend = sma_trend_control(c.close for c in candles)

        with open("paper_trading_state.json", encoding="utf-8") as fh:
            state = json.load(fh)

        strategy = StrategyPassport(
            strategy_id="STR-BIN-TREND-CONTROL-001",
            name="Binance SMA trend control",
            hypothesis="Infrastructure control, not validated alpha.",
        )
        scope = MarketScope(
            asset_class="CRYPTO",
            venue="BINANCE_SPOT",
            universe=("BTCUSDT",),
            quote_currency="USDT",
            timeframe="4h",
        )
        self.assertEqual("EXPERIMENT_ONLY", strategy.state_for(scope).value)

        state, event = advance_paper_state(
            state,
            observation=observation,
            signal=trend["signal"],
            strategy_id=strategy.strategy_id,
            fee_rate=0.001,
            slippage_bps=5.0,
        )
        metrics = paper_account_metrics(
            state,
            mark_price=observation.price,
            fee_rate=0.001,
        )
        result = {
            "experiment_id": "QT-LIVE-001",
            "mode": "PAPER",
            "live_execution_authorized": False,
            "observed_at": observation.observed_at,
            "source": observation.source,
            "price": observation.price,
            "bars": len(candles),
            "trend": trend,
            "paper_event": event,
            "paper_state": state,
            "metrics": metrics,
        }
        print("QT_LIVE_RESULT=" + json.dumps(result, sort_keys=True))
        self.assertEqual(61, len(candles))
        self.assertIn(trend["signal"], {"LONG", "CASH"})
        self.assertFalse(result["live_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
