from __future__ import annotations

import json
import unittest

from quantrade.institutional.paper_risk import (
    PAPER_RISK_POLICY_VERSION,
    PaperRiskPacketError,
    build_paper_review_inputs,
)


def _floor():
    return {
        "schema": "quantrade_trading_floor_v1",
        "experiment_id": "QT-LIVE-001",
        "mode": "PAPER",
        "live_execution_authorized": False,
        "starting_capital_usd": 30.0,
        "market_observation": {
            "symbol": "BTCUSDT",
            "price": 84589.26,
        },
        "market_scope": {
            "asset_class": "CRYPTO",
            "venue": "BINANCE_SPOT",
            "quote_currency": "USDT",
            "timeframe": "4h",
        },
        "current_validation": "EXPERIMENT_ONLY",
        "paper_account": {
            "position": {
                "symbol": "BTCUSDT",
                "quantity": 0.000354,
                "entry_total_cost_usd": 30.0,
            },
            "cash_usd": 0.0,
            "position_market_value_usd": 29.955,
            "equity_usd": 29.955,
            "total_return_pct": -0.15,
        },
        "generated_at": "2026-10-03T07:08:22+00:00",
    }


def _envelope(*, max_drawdown=18.0, max_loss_krw=5000000):
    return {
        "schema": "quantrade_private_strategy_envelope_v1",
        "risk_capacity": {
            "effective_max_drawdown_pct": max_drawdown,
            "max_loss_krw": max_loss_krw,
        },
    }


class PaperRiskPacketTests(unittest.TestCase):
    def test_builds_deterministic_paper_snapshot_and_risk(self):
        result = build_paper_review_inputs(
            trading_floor=_floor(),
            private_strategy_envelope=_envelope(),
        )

        self.assertEqual(
            "quantrade_paper_review_inputs_v1",
            result["schema"],
        )
        self.assertEqual(
            PAPER_RISK_POLICY_VERSION,
            result["risk_policy_version"],
        )
        snapshot = result["portfolio_snapshot"]
        risk = result["deterministic_risk_result"]
        self.assertAlmostEqual(29.955, snapshot["equity_usd"])
        self.assertAlmostEqual(
            99.85,
            snapshot["exposure_pct_of_starting_capital"],
            places=2,
        )
        self.assertTrue(risk["deterministic"])
        self.assertFalse(risk["llm_used"])
        self.assertFalse(risk["policy_breach"])
        self.assertAlmostEqual(0.15, risk["capital_loss_from_start_pct"])
        self.assertFalse(risk["live_execution_authorized"])

    def test_percentage_limit_can_trigger_breach(self):
        floor = _floor()
        floor["paper_account"]["total_return_pct"] = -20.0
        result = build_paper_review_inputs(
            trading_floor=floor,
            private_strategy_envelope=_envelope(max_drawdown=18.0),
        )

        risk = result["deterministic_risk_result"]
        self.assertTrue(risk["drawdown_limit_breach"])
        self.assertTrue(risk["policy_breach"])

    def test_krw_loss_amount_is_not_compared_to_usd_without_fx(self):
        private_limit = 987654321
        result = build_paper_review_inputs(
            trading_floor=_floor(),
            private_strategy_envelope=_envelope(
                max_loss_krw=private_limit,
            ),
        )

        risk = result["deterministic_risk_result"]
        policy = risk["currency_policy"]
        self.assertEqual("USD", policy["paper_currency"])
        self.assertEqual("KRW", policy["client_loss_limit_currency"])
        self.assertFalse(policy["fx_rate_supplied"])
        self.assertFalse(policy["cross_currency_loss_limit_compared"])

        public_safe = {
            "schema": result["schema"],
            "risk_policy_version": result["risk_policy_version"],
            "live_execution_authorized": result[
                "live_execution_authorized"
            ],
        }
        self.assertNotIn(str(private_limit), json.dumps(public_safe))

    def test_unvalidated_strategy_is_warning_not_silent_alpha_claim(self):
        result = build_paper_review_inputs(
            trading_floor=_floor(),
            private_strategy_envelope=_envelope(),
        )
        self.assertEqual(
            "STRATEGY_NOT_VALIDATED_AS_ALPHA",
            result["deterministic_risk_result"]["validation_warning"],
        )

    def test_refuses_non_paper_or_live_authorized_floor(self):
        live = _floor()
        live["mode"] = "LIVE"
        with self.assertRaisesRegex(PaperRiskPacketError, "PAPER"):
            build_paper_review_inputs(
                trading_floor=live,
                private_strategy_envelope=_envelope(),
            )

        authorized = _floor()
        authorized["live_execution_authorized"] = True
        with self.assertRaisesRegex(
            PaperRiskPacketError,
            "must not grant live execution",
        ):
            build_paper_review_inputs(
                trading_floor=authorized,
                private_strategy_envelope=_envelope(),
            )


if __name__ == "__main__":
    unittest.main()
