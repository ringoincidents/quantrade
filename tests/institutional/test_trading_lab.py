from __future__ import annotations

import math
import unittest

from quantrade.institutional.trading_lab import (
    BinanceSpotPublicMarketData,
    MarketObservation,
    MarketScope,
    MarketTransferGate,
    StrategyPassport,
    TransferClass,
    ValidationState,
    build_trading_floor_snapshot,
    seed_buy_and_hold_benchmark,
    sma_trend_control,
)


class TradingLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.binance_scope = MarketScope(
            asset_class="CRYPTO",
            venue="BINANCE_SPOT",
            universe=("BTCUSDT",),
            quote_currency="USDT",
            timeframe="4h",
        )
        self.upbit_scope = MarketScope(
            asset_class="CRYPTO",
            venue="UPBIT",
            universe=("KRW-BTC",),
            quote_currency="KRW",
            timeframe="4h",
        )
        self.toss_scope = MarketScope(
            asset_class="US_EQUITY",
            venue="TOSS_SECURITIES",
            universe=("SPY",),
            quote_currency="USD",
            timeframe="1d",
        )

    def test_strategy_validation_is_scope_bound(self):
        passport = StrategyPassport(
            strategy_id="STR-1",
            name="fixture",
            hypothesis="fixture hypothesis",
        )
        passport.record(self.binance_scope, ValidationState.PAPER_VALIDATED)

        self.assertEqual(
            ValidationState.PAPER_VALIDATED,
            passport.state_for(self.binance_scope),
        )
        self.assertEqual(
            ValidationState.EXPERIMENT_ONLY,
            passport.state_for(self.upbit_scope),
        )

    def test_binance_to_upbit_requires_revalidation(self):
        decision = MarketTransferGate.evaluate(
            self.binance_scope,
            self.upbit_scope,
        )
        self.assertEqual(
            TransferClass.SAME_ASSET_CLASS_NEW_VENUE,
            decision.classification,
        )
        self.assertTrue(decision.requires_revalidation)
        self.assertIn("quote_currency", decision.must_revalidate)
        self.assertIn("microstructure", decision.must_revalidate)

    def test_crypto_to_equity_requires_full_validation(self):
        decision = MarketTransferGate.evaluate(
            self.binance_scope,
            self.toss_scope,
        )
        self.assertEqual(
            TransferClass.NEW_ASSET_CLASS_FULL_VALIDATION,
            decision.classification,
        )
        self.assertIn("corporate_actions", decision.must_revalidate)
        self.assertIn("market_sessions", decision.must_revalidate)

    def test_public_binance_adapter_parses_ticker_and_klines(self):
        seen: list[str] = []

        def fake_get_json(url: str):
            seen.append(url)
            if "/ticker/price" in url:
                return {"symbol": "BTCUSDT", "price": "84601.23"}
            return [
                [
                    1000,
                    "84000.0",
                    "85000.0",
                    "83500.0",
                    "84601.23",
                    "123.4",
                    2000,
                    "0",
                    1,
                    "0",
                    "0",
                    "0",
                ]
            ]

        market = BinanceSpotPublicMarketData(get_json=fake_get_json)
        observation = market.ticker_price("btcusdt")
        candles = market.klines("btcusdt", interval="4h", limit=1)

        self.assertEqual("BTCUSDT", observation.symbol)
        self.assertAlmostEqual(84601.23, observation.price)
        self.assertEqual(1, len(candles))
        self.assertAlmostEqual(84601.23, candles[0].close)
        self.assertIn("symbol=BTCUSDT", seen[0])
        self.assertIn("interval=4h", seen[1])

    def test_benchmark_math_uses_explicit_fee_assumption(self):
        observation = MarketObservation(
            venue="BINANCE_SPOT",
            symbol="BTCUSDT",
            price=84601.23,
            observed_at="2026-10-03T05:26:00+00:00",
            source="fixture://binance",
        )
        benchmark = seed_buy_and_hold_benchmark(
            observation,
            capital_usd=30.0,
            fee_rate=0.001,
        )

        self.assertAlmostEqual(0.03, benchmark["entry_fee_assumption_usd"])
        self.assertAlmostEqual(29.97, benchmark["initial_mark_value_usd"])
        self.assertTrue(math.isclose(
            0.000354250168703221,
            benchmark["quantity"],
            rel_tol=1e-12,
        ))

    def test_trend_control_warms_up_then_becomes_deterministic(self):
        warmup = sma_trend_control([1.0] * 59)
        self.assertEqual("WARMING_UP", warmup["state"])
        self.assertEqual("NO_TRADE", warmup["signal"])

        values = [float(i) for i in range(1, 62)]
        ready = sma_trend_control(values)
        self.assertEqual("READY", ready["state"])
        self.assertEqual("LONG", ready["signal"])
        self.assertEqual(
            "INFRASTRUCTURE_BASELINE_NOT_VALIDATED_ALPHA",
            ready["strategy_role"],
        )

    def test_snapshot_never_authorizes_live_execution(self):
        observation = MarketObservation(
            venue="BINANCE_SPOT",
            symbol="BTCUSDT",
            price=84601.23,
            observed_at="2026-10-03T05:26:00+00:00",
            source="fixture://binance",
        )
        passport = StrategyPassport(
            strategy_id="STR-BIN-TREND-CONTROL-001",
            name="trend control",
            hypothesis="fixture",
        )

        snapshot = build_trading_floor_snapshot(
            observation=observation,
            strategy=passport,
            scope=self.binance_scope,
        )

        self.assertEqual("PAPER", snapshot["mode"])
        self.assertFalse(snapshot["live_execution_authorized"])
        self.assertEqual("EXPERIMENT_ONLY", snapshot["current_validation"])
        self.assertEqual([], snapshot["trade_episodes"])


if __name__ == "__main__":
    unittest.main()
