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
    PortfolioOpportunityInput,
    assess_portfolio_opportunity,
)
from quantrade.capabilities.risk_opinion import (
    CandidateRiskProfile,
    RiskOpinionError,
    RiskOpinionInput,
    RiskPolicySnapshot,
    RiskStateSnapshot,
    create_risk_opinion,
)
from quantrade.capabilities.risk_opinion_evaluation import (
    reference_risk_opinions,
)


class RiskOpinionTests(unittest.TestCase):
    def _portfolio(self):
        case = evaluate_investment_case(
            InvestmentCaseInput(
                case_id="CASE-RISK",
                asset_id="KRX:000000",
                as_of="2026-10-05T12:00:00+09:00",
                current_price=100.0,
                currency="KRW",
                valuation_horizon_days=365,
                required_return_pct=10.0,
                scenarios=(
                    ScenarioAssumption("bear", "Bear", 0.25, 60.0),
                    ScenarioAssumption("base", "Base", 0.50, 125.0),
                    ScenarioAssumption("bull", "Bull", 0.25, 170.0),
                ),
            )
        )
        return assess_portfolio_opportunity(
            PortfolioOpportunityInput(
                case_economics=case,
                alternatives=(
                    CapitalAlternative(
                        alternative_id="CASH",
                        alternative_type="CASH",
                        expected_return_pct=3.0,
                        downside_pct=0.0,
                        basis_refs=("fixture://cash",),
                    ),
                ),
                constraints=PortfolioConstraintSnapshot(
                    snapshot_id="PORT",
                    as_of="2026-10-05T11:00:00+09:00",
                    mandate_allows_new_exposure=True,
                    mandate_ref="fixture://mandate",
                    current_asset_weight_pct=2.0,
                    max_asset_weight_pct=15.0,
                    current_liquidity_pct=25.0,
                    minimum_liquidity_reserve_pct=10.0,
                    available_downside_budget_pct=4.0,
                    constraint_refs=("fixture://portfolio",),
                ),
            )
        )

    def _candidate(self, **overrides):
        values = dict(
            asset_id="KRX:000000",
            worst_case_return_pct=-40.0,
            max_abs_correlation_to_portfolio=0.4,
            estimated_exit_days=2.0,
            uses_leverage=False,
            risk_refs=("fixture://candidate-risk",),
        )
        values.update(overrides)
        return CandidateRiskProfile(**values)

    def _policy(self, **overrides):
        values = dict(
            policy_id="RISK-POLICY",
            as_of="2026-10-05T10:00:00+09:00",
            max_single_asset_weight_pct=10.0,
            max_incremental_downside_budget_pct=2.0,
            max_portfolio_drawdown_pct=-20.0,
            max_abs_correlation_to_portfolio=0.8,
            max_exit_days=5.0,
            leverage_allowed=False,
            require_correlation_data=True,
            require_liquidity_data=True,
            policy_refs=("fixture://risk-policy",),
        )
        values.update(overrides)
        return RiskPolicySnapshot(**values)

    def _state(self, **overrides):
        values = dict(
            snapshot_id="RISK-STATE",
            as_of="2026-10-05T10:30:00+09:00",
            current_asset_weight_pct=2.0,
            current_portfolio_drawdown_pct=-6.0,
            state_refs=("fixture://risk-state",),
        )
        values.update(overrides)
        return RiskStateSnapshot(**values)

    def test_risk_can_reduce_portfolio_headroom_without_setting_target_weight(self):
        result = create_risk_opinion(
            RiskOpinionInput(
                portfolio_assessment=self._portfolio(),
                candidate=self._candidate(),
                policy=self._policy(),
                state=self._state(),
            )
        )
        self.assertEqual("PASS_WITH_LIMITS", result.status)
        self.assertEqual(
            5.0,
            result.limits["risk_downside_budget_ceiling_pct"],
        )
        self.assertEqual(
            5.0,
            result.limits["risk_position_ceiling_pct"],
        )
        self.assertFalse(result.limits["target_weight_set"])
        self.assertTrue(result.limits["risk_ceiling_is_not_target_weight"])
        self.assertTrue(result.authority["risk_opinion_created"])
        self.assertFalse(result.authority["committee_decision_created"])
        self.assertFalse(result.authority["execution_authorized"])

    def test_risk_passes_when_it_adds_no_stricter_limit(self):
        result = create_risk_opinion(
            RiskOpinionInput(
                portfolio_assessment=self._portfolio(),
                candidate=self._candidate(worst_case_return_pct=-20.0),
                policy=self._policy(
                    max_single_asset_weight_pct=20.0,
                    max_incremental_downside_budget_pct=10.0,
                ),
                state=self._state(),
            )
        )
        self.assertEqual("PASS", result.status)
        self.assertIn("NO_ADDITIONAL_RISK_LIMIT_REQUIRED", result.reasons)

    def test_correlation_policy_can_veto(self):
        result = create_risk_opinion(
            RiskOpinionInput(
                portfolio_assessment=self._portfolio(),
                candidate=self._candidate(
                    max_abs_correlation_to_portfolio=0.95,
                ),
                policy=self._policy(
                    max_abs_correlation_to_portfolio=0.8,
                ),
                state=self._state(),
            )
        )
        self.assertEqual("VETO", result.status)
        self.assertIn("CORRELATION_LIMIT_BREACH", result.reasons)
        self.assertTrue(result.authority["risk_veto_present"])
        self.assertFalse(result.authority["execution_authorized"])

    def test_liquidity_exit_policy_can_veto(self):
        result = create_risk_opinion(
            RiskOpinionInput(
                portfolio_assessment=self._portfolio(),
                candidate=self._candidate(estimated_exit_days=10.0),
                policy=self._policy(max_exit_days=5.0),
                state=self._state(),
            )
        )
        self.assertEqual("VETO", result.status)
        self.assertIn("LIQUIDITY_EXIT_LIMIT_BREACH", result.reasons)

    def test_leverage_policy_can_veto(self):
        result = create_risk_opinion(
            RiskOpinionInput(
                portfolio_assessment=self._portfolio(),
                candidate=self._candidate(uses_leverage=True),
                policy=self._policy(leverage_allowed=False),
                state=self._state(),
            )
        )
        self.assertEqual("VETO", result.status)
        self.assertIn("LEVERAGE_NOT_ALLOWED", result.reasons)

    def test_drawdown_limit_reached_can_veto_new_risk(self):
        result = create_risk_opinion(
            RiskOpinionInput(
                portfolio_assessment=self._portfolio(),
                candidate=self._candidate(),
                policy=self._policy(max_portfolio_drawdown_pct=-20.0),
                state=self._state(current_portfolio_drawdown_pct=-21.0),
            )
        )
        self.assertEqual("VETO", result.status)
        self.assertIn("PORTFOLIO_DRAWDOWN_LIMIT_REACHED", result.reasons)

    def test_missing_required_risk_data_never_implicitly_passes(self):
        result = create_risk_opinion(
            RiskOpinionInput(
                portfolio_assessment=self._portfolio(),
                candidate=self._candidate(
                    max_abs_correlation_to_portfolio=None,
                    estimated_exit_days=None,
                ),
                policy=self._policy(
                    require_correlation_data=True,
                    require_liquidity_data=True,
                ),
                state=self._state(),
            )
        )
        self.assertEqual("REQUIRE_MORE_INFORMATION", result.status)
        self.assertIn("MISSING_CORRELATION_DATA", result.reasons)
        self.assertIn("MISSING_LIQUIDITY_DATA", result.reasons)
        self.assertFalse(result.authority["execution_authorized"])

    def test_noneligible_portfolio_case_cannot_enter_risk(self):
        portfolio = replace(
            self._portfolio(),
            status="NOT_COMPETITIVE",
        )
        with self.assertRaisesRegex(
            RiskOpinionError,
            "requires ELIGIBLE_FOR_PORTFOLIO_REVIEW",
        ):
            create_risk_opinion(
                RiskOpinionInput(
                    portfolio_assessment=portfolio,
                    candidate=self._candidate(),
                    policy=self._policy(),
                    state=self._state(),
                )
            )

    def test_risk_policy_cannot_come_from_future_of_portfolio_snapshot(self):
        with self.assertRaisesRegex(
            RiskOpinionError,
            "policy snapshot cannot be after Portfolio snapshot",
        ):
            create_risk_opinion(
                RiskOpinionInput(
                    portfolio_assessment=self._portfolio(),
                    candidate=self._candidate(),
                    policy=self._policy(
                        as_of="2026-10-05T11:30:00+09:00",
                    ),
                    state=self._state(),
                )
            )

    def test_risk_state_cannot_come_from_future_of_portfolio_snapshot(self):
        with self.assertRaisesRegex(
            RiskOpinionError,
            "state snapshot cannot be after Portfolio snapshot",
        ):
            create_risk_opinion(
                RiskOpinionInput(
                    portfolio_assessment=self._portfolio(),
                    candidate=self._candidate(),
                    policy=self._policy(),
                    state=self._state(
                        as_of="2026-10-05T11:30:00+09:00",
                    ),
                )
            )

    def test_single_asset_limit_reached_is_veto(self):
        result = create_risk_opinion(
            RiskOpinionInput(
                portfolio_assessment=self._portfolio(),
                candidate=self._candidate(),
                policy=self._policy(max_single_asset_weight_pct=10.0),
                state=self._state(current_asset_weight_pct=10.0),
            )
        )
        self.assertEqual("VETO", result.status)
        self.assertIn("RISK_SINGLE_ASSET_LIMIT_REACHED", result.reasons)

    def test_reference_harness_contains_pass_limit_veto_and_missing_paths(self):
        artifact = reference_risk_opinions()
        self.assertEqual(
            "PASS_WITH_LIMITS",
            artifact["cases"]["pass_with_limits"]["status"],
        )
        self.assertEqual(
            "VETO",
            artifact["cases"]["correlation_veto"]["status"],
        )
        self.assertEqual(
            "REQUIRE_MORE_INFORMATION",
            artifact["cases"]["missing_information"]["status"],
        )
        self.assertTrue(artifact["authority"]["risk_opinion_created"])
        self.assertFalse(
            artifact["authority"]["committee_decision_created"]
        )
        self.assertFalse(artifact["authority"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
