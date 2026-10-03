from __future__ import annotations

import json
import unittest

from scripts.run_live_institutional_precheck import build_precheck


def _bars(count: int = 120):
    rows = []
    price = 100.0
    for index in range(count):
        delta = 0.08 if index % 2 == 0 else -0.08
        open_price = price
        close = price + delta
        rows.append(
            {
                "timestamp": f"2026-10-{(index % 28) + 1:02d}T00:00:00+00:00",
                "open": open_price,
                "high": max(open_price, close) + 0.05,
                "low": min(open_price, close) - 0.05,
                "close": close,
                "volume": 100.0,
            }
        )
        price = close
    return rows


def _brief(*, ready: bool, missing=None, facts=None):
    return {
        "schema": "quantrade_private_client_strategy_brief_v1",
        "source": "LLM_HOLDINGS_CLIENT_INTELLIGENCE",
        "request_id": "CIR-TEST",
        "brief_id": "CIB-TEST",
        "strategy_ready": ready,
        "requested_keys": ["goals.short_term"],
        "facts": facts or [],
        "missing_information": missing or [],
        "withheld_client_office_only": [],
        "boundaries": {
            "investment_decision_authority": False,
            "capital_movement_authority": False,
            "public_repository_persistence_allowed": False,
        },
    }


class LiveInstitutionalPrecheckTests(unittest.TestCase):
    def test_incomplete_client_context_blocks_opportunity_path(self):
        result = build_precheck(
            private_client_brief=_brief(
                ready=False,
                missing=["liquidity.minimum_reserve"],
            ),
            bars=_bars(),
            symbol="BTCUSDT",
            timeframe="4h",
            market_source="fixture://binance",
            run_id="RUN-1",
        )

        self.assertEqual("QT-LIVE-003", result["experiment_id"])
        self.assertEqual("CLIENT_STRATEGY_REVIEW", result["next_stage"])
        self.assertEqual(
            "CLIENT_REVIEW_REQUIRED",
            result["strategy_directive"]["posture"],
        )
        self.assertTrue(result["ai_call_gate"]["call_ai"])
        self.assertIn(
            "CLIENT_MANDATE_CONFLICT",
            result["ai_call_gate"]["reasons"],
        )
        self.assertFalse(result["authority"]["paper_execution_created"])
        self.assertFalse(result["authority"]["live_execution_authorized"])

    def test_private_client_values_never_enter_public_precheck(self):
        secret = "PRIVATE-CLIENT-VALUE-123"
        result = build_precheck(
            private_client_brief=_brief(
                ready=True,
                facts=[
                    {
                        "fact_key": "goals.short_term",
                        "value": {"secret": secret},
                    }
                ],
            ),
            bars=_bars(),
            symbol="BTCUSDT",
            timeframe="4h",
            market_source="fixture://binance",
            run_id="RUN-2",
        )

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertTrue(result["client_context"]["strategy_ready"])
        self.assertEqual(1, result["client_context"]["available_fact_count"])
        self.assertFalse(result["client_context"]["raw_values_persisted"])
        self.assertFalse(result["privacy"]["private_client_values_in_output"])

    def test_ready_client_context_does_not_create_execution(self):
        result = build_precheck(
            private_client_brief=_brief(ready=True),
            bars=_bars(),
            symbol="BTCUSDT",
            timeframe="4h",
            market_source="fixture://binance",
            run_id="RUN-3",
        )

        self.assertEqual("MAINTAIN", result["strategy_directive"]["posture"])
        self.assertIn(
            result["next_stage"],
            {"NO_AI_REVIEW", "BOUNDED_AI_REVIEW"},
        )
        self.assertFalse(result["authority"]["ai_called"])
        self.assertFalse(
            result["authority"]["investment_committee_decision_created"]
        )
        self.assertFalse(result["authority"]["decision_plan_created"])
        self.assertFalse(result["authority"]["paper_execution_created"])

    def test_private_brief_must_forbid_public_persistence(self):
        brief = _brief(ready=True)
        brief["boundaries"]["public_repository_persistence_allowed"] = True

        with self.assertRaisesRegex(
            ValueError,
            "forbid public persistence",
        ):
            build_precheck(
                private_client_brief=brief,
                bars=_bars(),
                symbol="BTCUSDT",
                timeframe="4h",
                market_source="fixture://binance",
            )


if __name__ == "__main__":
    unittest.main()
