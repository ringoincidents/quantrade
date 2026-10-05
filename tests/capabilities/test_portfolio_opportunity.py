import unittest
from dataclasses import replace

from quantrade.capabilities.investment_case import (
    InvestmentCaseInput,
    ScenarioAssumption,
    evaluate_investment_case,
)
from quantrade.capabilities.portfolio_opportunity import (
    CapitalAlternative,
    PortfolioConstraintSnapshot,
    PortfolioOpportunityError,
    PortfolioOpportunityInput,
    assess_portfolio_opportunity,
)
from quantrade.capabilities.portfolio_opportunity_evaluation import (
    reference_portfolio_opportunities,
)


class PortfolioOpportunityTests(unittest.TestCase):
    def _case(self, *, required_return_pct=10.0):
        return evaluate_investment_case(
            InvestmentCaseInput(
                case_id="CASE-PORT",
                asset_id="KRX:000000",
                as_of="2026-10-05T12:00:00+09:00",
                current_price=100.0,
                currency="KRW",
                valuation_horizon_days=365,
                required_return_pct=required_return_pct,
                scenarios=(
                    ScenarioAssumption("bear", "Bear", 0.25, 60.0),
                    ScenarioAssumption("base", "Base", 0.50, 125.0),
                    ScenarioAssumption("bull", "Bull", 0.25, 170.0),
                ),
            )
        )

    def _alternatives(self):
        return (
            CapitalAlternative(
                alternative_id="CASH",
                alternative_type="CASH",
                expected_return_pct=3.0,
                downside_pct=0.0,
                basis_refs=("fixture://cash",),
            ),
            CapitalAlternative(
                alternative_id="CORE",
                alternative_type="CORE_BENCHMARK",
                expected_return_pct=8.0,
                downside_pct=-20.0,
                basis_refs=("fixture://core",),
            ),
        )

    def _constraints(self, **overrides):
        values = dict(
            snapshot_id="SNAP",
            as_of="2026-10-05T11:00:00+09:00",
            mandate_allows_new_exposure=True,
            mandate_ref="fixture://mandate",
            current_asset_weight_pct=4.0,
            max_asset_weight_pct=12.0,
            current_liquidity_pct=20.0,
            minimum_liquidity_reserve_pct=12.0,
            available_downside_budget_pct=2.0,
            constraint_refs=("fixture://constraints",),
        )
        values.update(overrides)
        return PortfolioConstraintSnapshot(**values)

    def test_competitive_case_is_only_eligible_for_review(self):
        result = assess_portfolio_opportunity(
            PortfolioOpportunityInput(
                case_economics=self._case(),
                alternatives=self._alternatives(),
                constraints=self._constraints(),
            )
        )
        self.assertEqual(
            "ELIGIBLE_FOR_PORTFOLIO_REVIEW",
            result.status,
        )
        self.assertEqual(
            "CORE",
            result.opportunity_cost["best_alternative_id"],
        )
        self.assertGreater(
            result.opportunity_cost[
                "candidate_excess_vs_best_alternative_pct"
            ],
            0,
        )
        self.assertFalse(result.authority["portfolio_proposal_created"])
        self.assertFalse(result.authority["target_weight_set"])
        self.assertFalse(result.authority["risk_opinion_created"])
        self.assertFalse(result.authority["committee_decision_created"])
        self.assertFalse(result.authority["execution_authorized"])

    def test_capital_upper_bound_is_minimum_of_explicit_constraints(self):
        result = assess_portfolio_opportunity(
            PortfolioOpportunityInput(
                case_economics=self._case(),
                alternatives=self._alternatives(),
                constraints=self._constraints(),
            )
        )
        headroom = result.capital_headroom
        self.assertEqual(8.0, headroom["concentration_headroom_pct"])
        self.assertEqual(8.0, headroom["liquidity_headroom_pct"])
        # Candidate bear case is -40%; 2% portfolio downside budget / 40%
        # loss severity = 5 percentage points of portfolio capital.
        self.assertEqual(5.0, headroom["risk_limited_headroom_pct"])
        self.assertEqual(5.0, headroom["deterministic_upper_bound_pct"])
        self.assertFalse(headroom["target_weight_proposed"])
        self.assertTrue(headroom["upper_bound_is_not_target_weight"])

    def test_no_alternatives_is_missing_context_not_implicit_approval(self):
        result = assess_portfolio_opportunity(
            PortfolioOpportunityInput(
                case_economics=self._case(),
                alternatives=(),
                constraints=self._constraints(),
            )
        )
        self.assertEqual("MISSING_CONTEXT", result.status)
        self.assertIn("NO_CAPITAL_ALTERNATIVES", result.reasons)
        self.assertFalse(result.authority["portfolio_proposal_created"])

    def test_candidate_that_does_not_beat_best_alternative_is_not_competitive(self):
        alternatives = (
            CapitalAlternative(
                alternative_id="BETTER",
                alternative_type="ACTIVE_CASE",
                expected_return_pct=40.0,
                downside_pct=-30.0,
                basis_refs=("fixture://better-case",),
            ),
        )
        result = assess_portfolio_opportunity(
            PortfolioOpportunityInput(
                case_economics=self._case(),
                alternatives=alternatives,
                constraints=self._constraints(),
            )
        )
        self.assertEqual("NOT_COMPETITIVE", result.status)
        self.assertIn(
            "DOES_NOT_BEAT_BEST_CAPITAL_ALTERNATIVE",
            result.reasons,
        )

    def test_mandate_can_block_review_eligibility(self):
        result = assess_portfolio_opportunity(
            PortfolioOpportunityInput(
                case_economics=self._case(),
                alternatives=self._alternatives(),
                constraints=self._constraints(
                    mandate_allows_new_exposure=False,
                ),
            )
        )
        self.assertEqual("NOT_COMPETITIVE", result.status)
        self.assertIn(
            "MANDATE_DISALLOWS_NEW_EXPOSURE",
            result.reasons,
        )

    def test_zero_concentration_headroom_blocks_review(self):
        result = assess_portfolio_opportunity(
            PortfolioOpportunityInput(
                case_economics=self._case(),
                alternatives=self._alternatives(),
                constraints=self._constraints(
                    current_asset_weight_pct=12.0,
                    max_asset_weight_pct=12.0,
                ),
            )
        )
        self.assertEqual("NOT_COMPETITIVE", result.status)
        self.assertEqual(
            0.0,
            result.capital_headroom["deterministic_upper_bound_pct"],
        )
        self.assertIn(
            "NO_DETERMINISTIC_CAPITAL_HEADROOM",
            result.reasons,
        )

    def test_liquidity_below_reserve_yields_zero_deployment_headroom(self):
        result = assess_portfolio_opportunity(
            PortfolioOpportunityInput(
                case_economics=self._case(),
                alternatives=self._alternatives(),
                constraints=self._constraints(
                    current_liquidity_pct=8.0,
                    minimum_liquidity_reserve_pct=12.0,
                ),
            )
        )
        self.assertEqual(
            0.0,
            result.capital_headroom["liquidity_headroom_pct"],
        )
        self.assertEqual("NOT_COMPETITIVE", result.status)

    def test_case_hurdle_failure_remains_blocking_even_if_it_beats_alternative(self):
        case = self._case(required_return_pct=30.0)
        result = assess_portfolio_opportunity(
            PortfolioOpportunityInput(
                case_economics=case,
                alternatives=self._alternatives(),
                constraints=self._constraints(),
            )
        )
        self.assertEqual("NOT_COMPETITIVE", result.status)
        self.assertIn("CASE_RETURN_HURDLE_NOT_MET", result.reasons)

    def test_future_portfolio_snapshot_is_rejected(self):
        with self.assertRaisesRegex(
            PortfolioOpportunityError,
            "cannot be after case as_of",
        ):
            assess_portfolio_opportunity(
                PortfolioOpportunityInput(
                    case_economics=self._case(),
                    alternatives=self._alternatives(),
                    constraints=self._constraints(
                        as_of="2026-10-05T13:00:00+09:00",
                    ),
                )
            )

    def test_duplicate_alternative_ids_are_rejected(self):
        duplicate = CapitalAlternative(
            alternative_id="SAME",
            alternative_type="CASH",
            expected_return_pct=3.0,
            downside_pct=0.0,
            basis_refs=("fixture://a",),
        )
        with self.assertRaisesRegex(
            PortfolioOpportunityError,
            "duplicate alternative_id",
        ):
            assess_portfolio_opportunity(
                PortfolioOpportunityInput(
                    case_economics=self._case(),
                    alternatives=(duplicate, duplicate),
                    constraints=self._constraints(),
                )
            )

    def test_input_case_cannot_already_carry_portfolio_authority(self):
        case = self._case()
        bad = replace(
            case,
            authority={
                **case.authority,
                "portfolio_proposal_created": True,
            },
        )
        with self.assertRaisesRegex(
            PortfolioOpportunityError,
            "must not already contain Portfolio authority",
        ):
            assess_portfolio_opportunity(
                PortfolioOpportunityInput(
                    case_economics=bad,
                    alternatives=self._alternatives(),
                    constraints=self._constraints(),
                )
            )

    def test_reference_harness_preserves_separation_of_attractiveness_and_allocation(self):
        artifact = reference_portfolio_opportunities()
        eligible = artifact["cases"]["eligible_for_review"]
        crowded = artifact["cases"]["no_headroom"]
        self.assertEqual(
            "ELIGIBLE_FOR_PORTFOLIO_REVIEW",
            eligible["status"],
        )
        self.assertEqual("NOT_COMPETITIVE", crowded["status"])
        self.assertFalse(
            artifact["authority"]["portfolio_proposal_created"]
        )
        self.assertFalse(artifact["authority"]["target_weight_set"])
        self.assertFalse(
            artifact["authority"]["committee_decision_created"]
        )
        self.assertFalse(artifact["authority"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
