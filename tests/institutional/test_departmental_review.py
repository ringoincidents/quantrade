from __future__ import annotations

import json
import os
import tempfile
import unittest

from quantrade.institutional.departmental_review import (
    BoundedDepartmentalReview,
    DepartmentalReviewError,
)
from quantrade.institutional.employee_agent import (
    ModelAction,
    ScriptedModelProvider,
)
from quantrade.institutional.service import InstitutionalKernel


def _precheck(*, ready: bool = True, next_stage: str = "BOUNDED_AI_REVIEW"):
    return {
        "schema": "quantrade_institutional_case_precheck_v1",
        "run_id": "RUN-DEPT-001",
        "mode": "PAPER_PRECHECK",
        "market_source": "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=120",
        "market_state": {
            "schema": "quantrade_market_state_v1",
            "symbol": "BTCUSDT",
            "timeframe": "4h",
            "timestamp": "2026-10-03T08:00:00+00:00",
            "trend": {"regime": "UPTREND"},
            "returns": {"20_bar_pct": 1.5},
        },
        "client_context": {
            "strategy_ready": ready,
            "raw_values_persisted": False,
        },
        "strategy_directive": {
            "schema": "quantrade_strategy_directive_v1",
            "posture": "REBALANCE_REVIEW",
            "actions": ["RESEARCH", "REBALANCE_REVIEW"],
            "reasons": ["MATERIAL_RESEARCH_UPDATE"],
            "required_offices": ["SPMG", "IPRO"],
            "private_constraints_applied": True,
            "sensitive_values_persisted": False,
            "execution_authority": False,
        },
        "next_stage": next_stage,
        "authority": {
            "ai_called": False,
            "live_execution_authorized": False,
        },
    }


def _private_envelope():
    return {
        "schema": "quantrade_private_strategy_envelope_v1",
        "normalized_facts": {
            "capacity_max_loss_krw": 987654321,
            "preferred_max_drawdown_pct": 20,
        },
        "invalid_information": [],
        "client_state": {
            "liquidity_reserve": 3000000,
            "urgent_cash_need_amount": 0,
        },
        "mandate": {
            "max_drawdown_pct": 18,
            "planning_conflicts": [],
        },
        "risk_capacity": {
            "max_loss_krw": 987654321,
            "effective_max_drawdown_pct": 18,
        },
        "required_external_inputs": [],
        "boundaries": {
            "free_text_inference_performed": False,
            "investment_decision_authority": False,
            "public_persistence_allowed": False,
        },
    }


class DepartmentalReviewTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def _provider_factory(self, employee_id: str, work_order_id: str):
        employee = self.kernel.conn.execute(
            "SELECT office_id FROM employees WHERE employee_id=?",
            (employee_id,),
        ).fetchone()
        office = employee["office_id"]

        evidence = self.kernel.conn.execute(
            "SELECT evidence_id FROM evidence ORDER BY created_at LIMIT 1"
        ).fetchone()
        evidence_refs = [evidence["evidence_id"]] if evidence else []

        if office == "IID":
            actions = [
                ModelAction(
                    "TOOL",
                    {
                        "tool_name": "case.submit_research_evidence",
                        "arguments": {
                            "evidence_key": "MARKET_STATE",
                            "source": "https://invented.invalid/fake",
                            "fact": "invented fact that must be ignored",
                        },
                    },
                ),
                ModelAction(
                    "FINISH",
                    {"summary": "Research evidence submitted."},
                ),
            ]
        elif office == "SPMG":
            actions = [
                ModelAction(
                    "TOOL",
                    {
                        "tool_name": "case.submit_portfolio_position",
                        "arguments": {
                            "stance": "WAIT",
                            "rationale": "Evidence is not sufficient for immediate entry.",
                            "evidence_refs": evidence_refs,
                        },
                    },
                ),
                ModelAction(
                    "FINISH",
                    {"summary": "Portfolio stance submitted."},
                ),
            ]
        elif office == "IPRO":
            actions = [
                ModelAction(
                    "TOOL",
                    {
                        "tool_name": "case.submit_risk_position",
                        "arguments": {
                            "stance": "WITHIN_LIMITS",
                            "rationale": "Deterministic risk output is within policy.",
                            "evidence_refs": evidence_refs,
                            "deterministic_risk_result": {
                                "policy_breach": True,
                                "model_attempted_override": True,
                            },
                        },
                    },
                ),
                ModelAction(
                    "FINISH",
                    {"summary": "Risk stance submitted."},
                ),
            ]
        elif office == "ARU":
            actions = [
                ModelAction(
                    "TOOL",
                    {
                        "tool_name": "case.submit_adversarial_challenge",
                        "arguments": {
                            "thesis": "The current evidence supports action.",
                            "counter_thesis": (
                                "The signal may be regime-dependent and lacks "
                                "sufficient execution evidence."
                            ),
                            "unresolved": True,
                        },
                    },
                ),
                ModelAction(
                    "FINISH",
                    {"summary": "Adversarial challenge submitted."},
                ),
            ]
        else:
            raise AssertionError(office)

        return ScriptedModelProvider(actions)

    def test_role_bounded_review_opens_committee_only_after_all_artifacts(self):
        coordinator = BoundedDepartmentalReview(
            self.kernel,
            self._provider_factory,
            max_iterations=4,
        )
        result = coordinator.run(
            precheck=_precheck(),
            private_strategy_envelope=_private_envelope(),
            portfolio_snapshot={
                "cash_usd": 30.0,
                "positions": [],
                "source": "fixture",
            },
            deterministic_risk_result={
                "policy_breach": False,
                "concentration_pct": 0.0,
                "max_drawdown_limit_applied": True,
            },
            risk_policy_version="fixture-risk-v1",
        )

        self.assertEqual("COMMITTEE", result["status"])
        self.assertEqual("PAPER_REVIEW", result["mode"])
        self.assertEqual(8, result["model_call_count"])
        self.assertFalse(result["live_execution_authorized"])
        self.assertFalse(result["private_strategy_values_persisted_publicly"])
        self.assertTrue(result["unresolved_challenge_ids"])

        artifacts = result["artifacts"]
        self.assertTrue(artifacts["evidence_id"].startswith("EVD-"))
        self.assertTrue(
            artifacts["portfolio_position_id"].startswith("POS-")
        )
        self.assertTrue(artifacts["risk_assessment_id"].startswith("RSK-"))
        self.assertTrue(artifacts["risk_position_id"].startswith("POS-"))
        self.assertTrue(
            artifacts["adversarial_challenge_id"].startswith("CHL-")
        )

        case = self.kernel.get_case(result["case_id"])
        self.assertEqual("COMMITTEE", case["status"])
        self.assertTrue(self.kernel.verify_ledger_chain())

    def test_research_model_cannot_invent_canonical_source_or_fact(self):
        coordinator = BoundedDepartmentalReview(
            self.kernel,
            self._provider_factory,
        )
        result = coordinator.run(
            precheck=_precheck(),
            private_strategy_envelope=_private_envelope(),
            portfolio_snapshot={"cash_usd": 30.0, "positions": []},
            deterministic_risk_result={"policy_breach": False},
            risk_policy_version="fixture-risk-v1",
        )

        row = self.kernel.conn.execute(
            "SELECT source,fact,provenance FROM evidence WHERE case_id=?",
            (result["case_id"],),
        ).fetchone()
        self.assertEqual(
            "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=120",
            row["source"],
        )
        self.assertNotIn("invented.invalid", row["source"])
        self.assertNotIn("invented fact", row["fact"])
        fact = json.loads(row["fact"])
        self.assertEqual("BTCUSDT", fact["symbol"])
        self.assertEqual("UPTREND", fact["trend"]["regime"])
        provenance = json.loads(row["provenance"])
        self.assertEqual(
            "deterministic_market_state",
            provenance["source_type"],
        )

    def test_unknown_evidence_key_fails_without_canonical_evidence(self):
        def bad_provider_factory(employee_id: str, work_order_id: str):
            office = self.kernel.conn.execute(
                "SELECT office_id FROM employees WHERE employee_id=?",
                (employee_id,),
            ).fetchone()["office_id"]
            if office == "IID":
                return ScriptedModelProvider([
                    ModelAction(
                        "TOOL",
                        {
                            "tool_name": "case.submit_research_evidence",
                            "arguments": {"evidence_key": "INVENTED_SOURCE"},
                        },
                    ),
                    ModelAction("FINISH", {"summary": "done"}),
                ])
            return self._provider_factory(employee_id, work_order_id)

        coordinator = BoundedDepartmentalReview(
            self.kernel,
            bad_provider_factory,
            max_iterations=3,
        )
        with self.assertRaisesRegex(
            DepartmentalReviewError,
            "Research produced no canonical Evidence",
        ):
            coordinator.run(
                precheck=_precheck(),
                private_strategy_envelope=_private_envelope(),
                portfolio_snapshot={"cash_usd": 30.0, "positions": []},
                deterministic_risk_result={"policy_breach": False},
                risk_policy_version="fixture-risk-v1",
            )
        count = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM evidence"
        ).fetchone()["c"]
        self.assertEqual(0, count)

    def test_risk_model_cannot_override_deterministic_risk_result(self):
        coordinator = BoundedDepartmentalReview(
            self.kernel,
            self._provider_factory,
        )
        result = coordinator.run(
            precheck=_precheck(),
            private_strategy_envelope=_private_envelope(),
            portfolio_snapshot={"cash_usd": 30.0, "positions": []},
            deterministic_risk_result={
                "policy_breach": False,
                "source": "deterministic-engine",
            },
            risk_policy_version="fixture-risk-v1",
        )

        row = self.kernel.conn.execute(
            "SELECT result FROM risk_assessments WHERE case_id=?",
            (result["case_id"],),
        ).fetchone()
        risk = json.loads(row["result"])
        self.assertEqual(
            {
                "policy_breach": False,
                "source": "deterministic-engine",
            },
            risk,
        )
        self.assertNotIn("model_attempted_override", risk)

    def test_role_tool_grants_are_separated(self):
        coordinator = BoundedDepartmentalReview(
            self.kernel,
            self._provider_factory,
        )
        coordinator.run(
            precheck=_precheck(),
            private_strategy_envelope=_private_envelope(),
            portfolio_snapshot={"cash_usd": 30.0, "positions": []},
            deterministic_risk_result={"policy_breach": False},
            risk_policy_version="fixture-risk-v1",
        )

        offices = {}
        for row in self.kernel.conn.execute(
            "SELECT employee_id,office_id FROM employees"
        ):
            offices[row["office_id"]] = row["employee_id"]

        self.assertEqual(
            ["case.submit_research_evidence"],
            [x["name"] for x in coordinator.tools.discover(offices["IID"])],
        )
        self.assertEqual(
            ["case.submit_portfolio_position"],
            [x["name"] for x in coordinator.tools.discover(offices["SPMG"])],
        )
        self.assertEqual(
            ["case.submit_risk_position"],
            [x["name"] for x in coordinator.tools.discover(offices["IPRO"])],
        )
        self.assertEqual(
            ["case.submit_adversarial_challenge"],
            [x["name"] for x in coordinator.tools.discover(offices["ARU"])],
        )

    def test_public_review_summary_does_not_leak_private_strategy_values(self):
        coordinator = BoundedDepartmentalReview(
            self.kernel,
            self._provider_factory,
        )
        result = coordinator.run(
            precheck=_precheck(),
            private_strategy_envelope=_private_envelope(),
            portfolio_snapshot={"cash_usd": 30.0, "positions": []},
            deterministic_risk_result={"policy_breach": False},
            risk_policy_version="fixture-risk-v1",
        )

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("987654321", serialized)
        self.assertNotIn("max_loss_krw", serialized)
        self.assertNotIn("max_drawdown_pct", serialized)

    def test_review_refuses_client_gate_or_ai_gate_bypass(self):
        coordinator = BoundedDepartmentalReview(
            self.kernel,
            self._provider_factory,
        )
        with self.assertRaisesRegex(
            DepartmentalReviewError,
            "Client Strategy Gate",
        ):
            coordinator.run(
                precheck=_precheck(ready=False),
                private_strategy_envelope=_private_envelope(),
                portfolio_snapshot={"cash_usd": 30.0, "positions": []},
                deterministic_risk_result={"policy_breach": False},
                risk_policy_version="fixture-risk-v1",
            )

        with self.assertRaisesRegex(
            DepartmentalReviewError,
            "did not request BOUNDED_AI_REVIEW",
        ):
            coordinator.run(
                precheck=_precheck(next_stage="NO_AI_REVIEW"),
                private_strategy_envelope=_private_envelope(),
                portfolio_snapshot={"cash_usd": 30.0, "positions": []},
                deterministic_risk_result={"policy_breach": False},
                risk_policy_version="fixture-risk-v1",
            )


if __name__ == "__main__":
    unittest.main()
