import unittest

from quantrade.capabilities.fundamental_semantics import (
    BASIC_EPS_ACCOUNT_ID,
    SemanticMetricApplicabilityInput,
    SemanticMetricRequirement,
    collect_requested_metric_keys,
    evaluate_semantic_metric_applicability,
)


def observation(oid, metric_key, period, value=1.0):
    return {
        "observation_id": oid,
        "asset_id": "KRX:006400",
        "metric_key": metric_key,
        "value": value,
        "unit": "KRW",
        "fiscal_period_end": period,
        "published_at": "2026-03-10T23:59:59+09:00",
        "evidence_ref": f"fixture://{oid}",
    }


class FundamentalSemanticApplicabilityTests(unittest.TestCase):
    def _eps_requirement(self):
        return SemanticMetricRequirement(
            requirement_id="BASIC_EPS_FY2025",
            account_id=BASIC_EPS_ACCOUNT_ID,
            allowed_statement_divisions=("IS", "CIS"),
            amount_suffix="CURRENT_PERIOD",
            fiscal_period_ends=("2025-12-31",),
        )

    def test_generates_predeclared_is_and_cis_keys(self):
        keys = collect_requested_metric_keys(
            (self._eps_requirement(),)
        )
        self.assertEqual(
            (
                "DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:"
                "IS:CURRENT_PERIOD",
                "DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:"
                "CIS:CURRENT_PERIOD",
            ),
            keys,
        )

    def test_resolves_same_ifrs_account_under_cis(self):
        result = evaluate_semantic_metric_applicability(
            SemanticMetricApplicabilityInput(
                case_id="CASE-SEM",
                observations=(
                    observation(
                        "EPS-CIS",
                        "DART_ACCOUNT:"
                        "ifrs-full_BasicEarningsLossPerShare:"
                        "CIS:CURRENT_PERIOD",
                        "2025-12-31",
                        1234.0,
                    ),
                ),
                requirements=(self._eps_requirement(),),
            )
        )
        self.assertEqual("READY", result.status)
        self.assertEqual(1, len(result.resolved))
        self.assertEqual(
            "CIS",
            result.resolved[0]["actual_statement_division"],
        )
        self.assertEqual(
            "EXACT_ACCOUNT_ID_ALLOWED_DIVISION",
            result.resolved[0]["semantic_match_kind"],
        )

    def test_missing_metric_is_explicit(self):
        result = evaluate_semantic_metric_applicability(
            SemanticMetricApplicabilityInput(
                case_id="CASE-MISSING",
                observations=(),
                requirements=(self._eps_requirement(),),
            )
        )
        self.assertEqual("MISSING", result.status)
        self.assertEqual(1, len(result.missing))
        self.assertEqual(0, len(result.resolved))

    def test_is_and_cis_both_present_is_ambiguous(self):
        result = evaluate_semantic_metric_applicability(
            SemanticMetricApplicabilityInput(
                case_id="CASE-AMB",
                observations=(
                    observation(
                        "EPS-IS",
                        "DART_ACCOUNT:"
                        "ifrs-full_BasicEarningsLossPerShare:"
                        "IS:CURRENT_PERIOD",
                        "2025-12-31",
                    ),
                    observation(
                        "EPS-CIS",
                        "DART_ACCOUNT:"
                        "ifrs-full_BasicEarningsLossPerShare:"
                        "CIS:CURRENT_PERIOD",
                        "2025-12-31",
                    ),
                ),
                requirements=(self._eps_requirement(),),
            )
        )
        self.assertEqual("AMBIGUOUS", result.status)
        self.assertEqual(1, len(result.ambiguous))

    def test_unapproved_statement_division_is_not_guessed(self):
        requirement = SemanticMetricRequirement(
            requirement_id="EPS",
            account_id=BASIC_EPS_ACCOUNT_ID,
            allowed_statement_divisions=("IS",),
            amount_suffix="CURRENT_PERIOD",
            fiscal_period_ends=("2025-12-31",),
        )
        result = evaluate_semantic_metric_applicability(
            SemanticMetricApplicabilityInput(
                case_id="CASE-NO-GUESS",
                observations=(
                    observation(
                        "EPS-CIS",
                        "DART_ACCOUNT:"
                        "ifrs-full_BasicEarningsLossPerShare:"
                        "CIS:CURRENT_PERIOD",
                        "2025-12-31",
                    ),
                ),
                requirements=(requirement,),
            )
        )
        self.assertEqual("MISSING", result.status)
        self.assertFalse(
            result.validation["issuer_specific_alias_inference_used"]
        )

    def test_periods_are_resolved_independently(self):
        requirement = SemanticMetricRequirement(
            requirement_id="EPS-YTD",
            account_id=BASIC_EPS_ACCOUNT_ID,
            allowed_statement_divisions=("IS", "CIS"),
            amount_suffix="CURRENT_YTD",
            fiscal_period_ends=(
                "2025-06-30",
                "2026-06-30",
            ),
        )
        result = evaluate_semantic_metric_applicability(
            SemanticMetricApplicabilityInput(
                case_id="CASE-PERIODS",
                observations=(
                    observation(
                        "H125",
                        "DART_ACCOUNT:"
                        "ifrs-full_BasicEarningsLossPerShare:"
                        "CIS:CURRENT_YTD",
                        "2025-06-30",
                    ),
                    observation(
                        "H126",
                        "DART_ACCOUNT:"
                        "ifrs-full_BasicEarningsLossPerShare:"
                        "CIS:CURRENT_YTD",
                        "2026-06-30",
                    ),
                ),
                requirements=(requirement,),
            )
        )
        self.assertEqual("READY", result.status)
        self.assertEqual(2, len(result.resolved))

    def test_no_capital_authority(self):
        result = evaluate_semantic_metric_applicability(
            SemanticMetricApplicabilityInput(
                case_id="CASE-SEM",
                observations=(
                    observation(
                        "EPS-CIS",
                        "DART_ACCOUNT:"
                        "ifrs-full_BasicEarningsLossPerShare:"
                        "CIS:CURRENT_PERIOD",
                        "2025-12-31",
                    ),
                ),
                requirements=(self._eps_requirement(),),
            )
        )
        self.assertFalse(result.authority["model_called"])
        self.assertFalse(result.authority["valuation_created"])
        self.assertFalse(
            result.authority["portfolio_proposal_created"]
        )
        self.assertFalse(result.authority["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
