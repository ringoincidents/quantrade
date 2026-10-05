from __future__ import annotations

import json
import os
import tempfile
import unittest

from quantrade.institutional.investment_office_bridge import (
    InvestmentOfficeBridgeError,
    InvestmentOfficeInstitutionalBridge,
)
from quantrade.institutional.service import InstitutionalKernel


DOMAIN_CASE_ID = "CASE-IO-DOMAIN-001"
SOURCE_OBSERVED_AT = "2026-03-15T23:59:59+09:00"
PORTFOLIO_AS_OF = "2026-10-05T11:00:00+09:00"


def _fundamental():
    return {
        "schema": "quantrade_fundamental_observation_query_v1",
        "query": {
            "asset_id": "KRX:005930",
            "as_of": "2026-10-05T12:00:00+09:00",
        },
        "provider": {
            "provider_id": "OPEN_DART",
            "provider_version": "fixture",
        },
        "observations": [
            {
                "observation_id": "OBS-DART-001",
                "asset_id": "KRX:005930",
                "metric_key": "OPERATING_INCOME:IS:CURRENT_PERIOD",
                "value": 12345.0,
                "unit": "KRW",
                "currency": "KRW",
                "fiscal_period_end": "2025-12-31",
                "published_at": SOURCE_OBSERVED_AT,
                "retrieved_at": "2026-10-05T03:00:00+00:00",
                "source_provider": "OPEN_DART",
                "source_document_id": "20260315000123",
                "source_ref": (
                    "https://dart.fss.or.kr/dsaf001/main.do"
                    "?rcpNo=20260315000123"
                ),
                "evidence_ref": (
                    "https://dart.fss.or.kr/dsaf001/main.do"
                    "?rcpNo=20260315000123#account=operating_income"
                ),
                "revision_id": None,
                "revision_of": None,
                "restated": False,
                "normalization_method": "DART:CFS:IS:test",
                "published_at_precision": "DATE",
                "point_in_time_selected": True,
                "canonical_evidence_created": False,
                "investment_authority": False,
            }
        ],
        "excluded_future_observation_ids": [],
        "revision_resolution": [],
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "thesis_created": False,
            "portfolio_proposal_created": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    }


def _thesis(*, with_counter=True, source_timestamp=SOURCE_OBSERVED_AT):
    counters = []
    if with_counter:
        counters.append(
            {
                "counter_id": "COUNTER-1",
                "thesis_id": "THESIS-1",
                "statement": (
                    "Inventory pressure may prevent margin improvement "
                    "from persisting."
                ),
                "basis_refs": ["OBS-DART-001"],
            }
        )
    return {
        "schema": "quantrade_thesis_contract_v1",
        "case_id": DOMAIN_CASE_ID,
        "as_of": "2026-10-05T12:00:00+09:00",
        "nodes": {
            "observations": [
                {
                    "observation_id": "OBS-DART-001",
                    "statement": "Operating income improved.",
                    "source_ref": (
                        "https://dart.fss.or.kr/dsaf001/main.do"
                        "?rcpNo=20260315000123#account=operating_income"
                    ),
                    "source_kind": "EXTERNAL_EVIDENCE",
                    "observed_at": source_timestamp,
                    "evidence_eligible_reference": True,
                    "canonical_evidence_created": False,
                },
                {
                    "observation_id": "OBS-MODEL-001",
                    "statement": "Model narrative only.",
                    "source_ref": "fixture://model",
                    "source_kind": "MODEL_ARTIFACT",
                    "observed_at": "2026-10-05T10:00:00+09:00",
                    "evidence_eligible_reference": False,
                    "canonical_evidence_created": False,
                },
            ],
            "assumptions": [
                {
                    "assumption_id": "ASM-1",
                    "statement": "Improvement persists.",
                    "rationale": "Synthetic assumption.",
                    "provenance_refs": [],
                }
            ],
            "inferences": [
                {
                    "inference_id": "INF-1",
                    "statement": "Forward earnings may rise.",
                    "input_refs": ["OBS-DART-001", "ASM-1"],
                }
            ],
            "thesis_claims": [
                {
                    "thesis_id": "THESIS-1",
                    "statement": "The market may understate earnings power.",
                    "support_refs": ["INF-1", "OBS-MODEL-001"],
                }
            ],
            "counter_claims": counters,
            "falsification_conditions": [
                {
                    "condition_id": "FAL-1",
                    "thesis_id": "THESIS-1",
                    "statement": "Operating income reverses materially.",
                    "observable": "reported_operating_income",
                    "evaluation_horizon": "next_two_quarters",
                }
            ],
        },
        "thesis_assessments": [
            {
                "thesis_id": "THESIS-1",
                "eligible_evidence_observation_refs": ["OBS-DART-001"],
                "non_evidence_observation_refs": ["OBS-MODEL-001"],
                "assumption_refs": ["ASM-1"],
                "evidence_backed": True,
                "counter_claim_ids": (
                    ["COUNTER-1"] if with_counter else []
                ),
                "counter_research_present": with_counter,
                "falsification_condition_ids": ["FAL-1"],
                "falsification_defined": True,
                "thesis_truth_validated": False,
                "investment_authority": False,
            }
        ],
        "completeness": {
            "thesis_count": 1,
            "all_theses_falsifiable": True,
            "all_theses_evidence_backed": True,
            "all_theses_have_counter_research": with_counter,
        },
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "thesis_truth_validated": False,
            "portfolio_proposal_created": False,
            "position_size_set": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    }


def _portfolio():
    return {
        "schema": "quantrade_portfolio_opportunity_v1",
        "case_id": DOMAIN_CASE_ID,
        "status": "ELIGIBLE_FOR_PORTFOLIO_REVIEW",
        "reasons": ["CLEARS_RETURN_AND_HEADROOM_GATES"],
        "opportunity_cost": {
            "candidate_expected_return_pct": 18.0,
            "best_alternative_id": "CORE",
            "best_alternative_type": "CORE_BENCHMARK",
            "best_alternative_expected_return_pct": 8.0,
            "candidate_excess_vs_best_alternative_pct": 10.0,
            "return_competition_evaluated": True,
            "investment_score_created": False,
        },
        "capital_headroom": {
            "concentration_headroom_pct": 8.0,
            "liquidity_headroom_pct": 8.0,
            "risk_limited_headroom_pct": 5.0,
            "deterministic_upper_bound_pct": 5.0,
            "candidate_downside_pct": -40.0,
            "target_weight_proposed": False,
            "upper_bound_is_not_target_weight": True,
        },
        "alternatives": [],
        "constraints": {
            "snapshot_id": "PORT-SNAPSHOT-001",
            "as_of": PORTFOLIO_AS_OF,
            "mandate_allows_new_exposure": True,
            "mandate_ref": "fixture://mandate",
            "current_asset_weight_pct": 2.0,
            "max_asset_weight_pct": 10.0,
            "current_liquidity_pct": 20.0,
            "minimum_liquidity_reserve_pct": 12.0,
            "available_downside_budget_pct": 2.0,
            "constraint_refs": ["fixture://portfolio-policy"],
        },
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "thesis_validated": False,
            "portfolio_review_eligibility_created": True,
            "portfolio_proposal_created": False,
            "target_weight_set": False,
            "risk_opinion_created": False,
            "risk_limit_changed": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    }


def _risk(status="PASS_WITH_LIMITS"):
    reasons = {
        "PASS": ["NO_ADDITIONAL_RISK_LIMIT_REQUIRED"],
        "PASS_WITH_LIMITS": ["RISK_REDUCED_PORTFOLIO_HEADROOM"],
        "VETO": ["CORRELATION_LIMIT_BREACH"],
        "REQUIRE_MORE_INFORMATION": ["MISSING_CORRELATION_DATA"],
    }[status]
    return {
        "schema": "quantrade_risk_opinion_v1",
        "case_id": DOMAIN_CASE_ID,
        "status": status,
        "reasons": reasons,
        "candidate": {
            "asset_id": "KRX:005930",
            "worst_case_return_pct": -40.0,
            "max_abs_correlation_to_portfolio": (
                None if status == "REQUIRE_MORE_INFORMATION" else 0.45
            ),
            "estimated_exit_days": 2.0,
            "uses_leverage": False,
            "risk_refs": ["fixture://candidate-risk"],
        },
        "policy": {
            "policy_id": "RISK-POLICY-V1",
            "as_of": "2026-10-05T10:00:00+09:00",
        },
        "state": {
            "snapshot_id": "RISK-STATE-1",
            "as_of": "2026-10-05T10:30:00+09:00",
        },
        "limits": {
            "portfolio_opportunity_upper_bound_pct": 5.0,
            "risk_single_asset_headroom_pct": 8.0,
            "risk_downside_budget_ceiling_pct": 4.0,
            "risk_position_ceiling_pct": 4.0,
            "target_weight_set": False,
            "risk_ceiling_is_not_target_weight": True,
        },
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "target_weight_set": False,
            "risk_opinion_created": True,
            "risk_veto_present": status == "VETO",
            "risk_limit_changed": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    }


class InvestmentOfficeInstitutionalBridgeTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        event = self.kernel.ingest_event(
            "MATERIAL_REVIEW_REQUIRED",
            "IO-BRIDGE-TEST",
            "KRX:005930",
            {"mode": "TEST"},
            title="Investment Office bridge test",
        )
        self.case_id = event["case_id"]
        self.bridge = InvestmentOfficeInstitutionalBridge(self.kernel)

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def _bind(self, **overrides):
        values = {
            "fundamental": _fundamental(),
            "thesis": _thesis(),
            "portfolio": _portfolio(),
            "risk": _risk(),
        }
        values.update(overrides)
        return self.bridge.bind(self.case_id, **values)

    def test_full_handoff_enters_existing_committee_without_decision(self):
        result = self._bind()

        self.assertTrue(result["committee_readiness"]["ready"])
        self.assertTrue(result["committee_entered"])
        self.assertFalse(result["risk_veto_preserved"])
        self.assertFalse(result["authority"]["founder_decision_created"])
        self.assertFalse(result["authority"]["decision_plan_created"])
        self.assertFalse(result["authority"]["execution_authorized"])

        case = self.kernel.get_case(self.case_id)
        self.assertEqual("COMMITTEE", case["status"])

        decisions = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM decisions WHERE case_id=?",
            (self.case_id,),
        ).fetchone()["c"]
        plans = self.kernel.conn.execute(
            """SELECT COUNT(*) c FROM decision_plans p
            JOIN decisions d ON d.decision_id=p.decision_id
            WHERE d.case_id=?""",
            (self.case_id,),
        ).fetchone()["c"]
        self.assertEqual(0, decisions)
        self.assertEqual(0, plans)
        self.assertTrue(self.kernel.verify_ledger_chain())

    def test_source_observed_at_survives_canonical_evidence_handoff(self):
        result = self._bind()
        row = self.kernel.conn.execute(
            """SELECT observed_at,source,fact,provenance
            FROM evidence WHERE evidence_id=?""",
            (result["evidence_ids"][0],),
        ).fetchone()
        self.assertEqual(SOURCE_OBSERVED_AT, row["observed_at"])
        fact = json.loads(row["fact"])
        self.assertEqual("OBS-DART-001", fact["observation_id"])
        self.assertEqual(
            "OPERATING_INCOME:IS:CURRENT_PERIOD",
            fact["metric_key"],
        )
        provenance = json.loads(row["provenance"])
        self.assertEqual(
            SOURCE_OBSERVED_AT,
            provenance["published_at"],
        )

    def test_model_artifact_and_assumption_never_become_evidence(self):
        self._bind()
        count = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM evidence WHERE case_id=?",
            (self.case_id,),
        ).fetchone()["c"]
        self.assertEqual(1, count)
        serialized = " ".join(
            row["fact"]
            for row in self.kernel.conn.execute(
                "SELECT fact FROM evidence WHERE case_id=?",
                (self.case_id,),
            )
        )
        self.assertNotIn("Model narrative only", serialized)
        self.assertNotIn("Improvement persists", serialized)

    def test_mismatched_source_timestamp_fails_closed(self):
        with self.assertRaisesRegex(
            InvestmentOfficeBridgeError,
            "must exactly match source published_at",
        ):
            self._bind(
                thesis=_thesis(
                    source_timestamp="2026-03-16T23:59:59+09:00"
                )
            )
        count = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM evidence WHERE case_id=?",
            (self.case_id,),
        ).fetchone()["c"]
        self.assertEqual(0, count)

    def test_portfolio_snapshot_preserves_original_as_of(self):
        result = self._bind()
        row = self.kernel.conn.execute(
            "SELECT as_of,created_at FROM portfolio_snapshots WHERE snapshot_id=?",
            (result["portfolio_snapshot_id"],),
        ).fetchone()
        self.assertEqual(PORTFOLIO_AS_OF, row["as_of"])
        self.assertNotEqual(row["as_of"], row["created_at"])

    def test_risk_veto_survives_into_ipro_position_and_committee_package(self):
        result = self._bind(risk=_risk("VETO"))
        self.assertTrue(result["risk_veto_preserved"])
        self.assertTrue(result["committee_entered"])

        position = self.kernel.conn.execute(
            "SELECT stance,rationale FROM institutional_positions WHERE position_id=?",
            (result["risk_position_id"],),
        ).fetchone()
        self.assertEqual("VETO", position["stance"])
        self.assertIn(
            "CORRELATION_LIMIT_BREACH",
            position["rationale"],
        )

        package = self.kernel.build_committee_package(
            self.case_id,
            "UNSET",
            ["Risk VETO requires governed resolution."],
        )
        ipro = [
            item
            for item in package["positions"]
            if item["office"] == "IPRO"
        ][0]
        self.assertEqual("VETO", ipro["stance"])

    def test_missing_risk_information_blocks_committee_entry(self):
        result = self._bind(
            risk=_risk("REQUIRE_MORE_INFORMATION")
        )
        self.assertTrue(result["committee_readiness"]["ready"])
        self.assertTrue(result["risk_information_block"])
        self.assertFalse(result["committee_entered"])
        self.assertEqual(
            "OPEN",
            self.kernel.get_case(self.case_id)["status"],
        )

    def test_missing_counterclaim_is_preserved_as_committee_gap(self):
        result = self._bind(thesis=_thesis(with_counter=False))
        self.assertFalse(result["committee_readiness"]["ready"])
        self.assertIn(
            "adversarial_challenge_id",
            result["committee_readiness"]["missing"],
        )
        self.assertFalse(result["committee_entered"])

    def test_noncompetitive_portfolio_cannot_be_rescued_by_integration(self):
        portfolio = _portfolio()
        portfolio["status"] = "NOT_COMPETITIVE"
        with self.assertRaisesRegex(
            InvestmentOfficeBridgeError,
            "ELIGIBLE_FOR_PORTFOLIO_REVIEW",
        ):
            self._bind(portfolio=portfolio)

    def test_handoff_is_idempotent(self):
        first = self._bind()
        second = self._bind()

        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(first["handoff_id"], second["handoff_id"])
        self.assertEqual(
            first["evidence_ids"],
            second["evidence_ids"],
        )

        evidence_count = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM evidence WHERE case_id=?",
            (self.case_id,),
        ).fetchone()["c"]
        position_count = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM institutional_positions WHERE case_id=?",
            (self.case_id,),
        ).fetchone()["c"]
        challenge_count = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM challenges WHERE case_id=?",
            (self.case_id,),
        ).fetchone()["c"]
        self.assertEqual(1, evidence_count)
        self.assertEqual(2, position_count)
        self.assertEqual(1, challenge_count)

    def test_execution_authoritative_input_is_rejected(self):
        risk = _risk()
        risk["authority"]["execution_authorized"] = True
        with self.assertRaisesRegex(
            InvestmentOfficeBridgeError,
            "execution_authorized=false",
        ):
            self._bind(risk=risk)


if __name__ == "__main__":
    unittest.main()
