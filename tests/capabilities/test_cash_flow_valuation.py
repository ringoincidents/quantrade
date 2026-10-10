import unittest

from quantrade.capabilities.cash_flow_valuation import (
    CashFlowDCFInput,
    CashFlowDCFScenario,
    CashFlowValuationError,
    evaluate_cash_flow_dcf,
)


class CashFlowValuationTests(unittest.TestCase):
    def _request(self):
        return CashFlowDCFInput(
            case_id="CASE-CF",
            asset_id="KRX:005930",
            as_of="2026-10-05T23:59:59+09:00",
            current_price=100.0,
            currency="KRW",
            owner_cash_flow_per_share=10.0,
            required_return_pct=15.0,
            scenarios=(
                CashFlowDCFScenario(
                    scenario_id="BEAR",
                    label="Bear",
                    probability=0.25,
                    starting_cash_flow_factor=0.80,
                    explicit_growth_pct=0.0,
                    terminal_growth_pct=0.0,
                    discount_rate_pct=10.0,
                ),
                CashFlowDCFScenario(
                    scenario_id="BASE",
                    label="Base",
                    probability=0.50,
                    starting_cash_flow_factor=1.0,
                    explicit_growth_pct=3.0,
                    terminal_growth_pct=2.0,
                    discount_rate_pct=10.0,
                ),
                CashFlowDCFScenario(
                    scenario_id="BULL",
                    label="Bull",
                    probability=0.25,
                    starting_cash_flow_factor=1.20,
                    explicit_growth_pct=5.0,
                    terminal_growth_pct=3.0,
                    discount_rate_pct=10.0,
                ),
            ),
        )

    def test_bear_zero_growth_dcf_equals_perpetuity_value(self):
        result = evaluate_cash_flow_dcf(self._request())
        bear = result.scenarios[0]
        self.assertAlmostEqual(80.0, bear["fair_value"], places=6)

    def test_base_and_bull_reference_values_are_deterministic(self):
        result = evaluate_cash_flow_dcf(self._request())
        self.assertAlmostEqual(
            133.00357516,
            result.scenarios[1]["fair_value"],
            places=6,
        )
        self.assertAlmostEqual(
            192.22508708,
            result.scenarios[2]["fair_value"],
            places=6,
        )

    def test_weighted_value_and_return_are_probability_weighted(self):
        result = evaluate_cash_flow_dcf(self._request())
        expected = (
            0.25 * 80.0
            + 0.50 * 133.00357515709308
            + 0.25 * 192.22508708421555
        )
        self.assertAlmostEqual(
            expected,
            result.metrics["weighted_fair_value"],
            places=6,
        )
        self.assertAlmostEqual(
            expected - 100.0,
            result.metrics["expected_return_pct"],
            places=6,
        )

    def test_discount_rate_must_exceed_terminal_growth(self):
        request = self._request()
        bad = CashFlowDCFInput(
            **{
                **request.__dict__,
                "scenarios": (
                    CashFlowDCFScenario(
                        scenario_id="BAD",
                        label="Bad",
                        probability=1.0,
                        starting_cash_flow_factor=1.0,
                        explicit_growth_pct=3.0,
                        terminal_growth_pct=10.0,
                        discount_rate_pct=10.0,
                    ),
                ),
            }
        )
        with self.assertRaisesRegex(
            CashFlowValuationError,
            "discount_rate must exceed terminal_growth",
        ):
            evaluate_cash_flow_dcf(bad)

    def test_nonpositive_cash_flow_fails_closed(self):
        request = self._request()
        bad = CashFlowDCFInput(
            **{
                **request.__dict__,
                "owner_cash_flow_per_share": 0.0,
            }
        )
        with self.assertRaisesRegex(
            CashFlowValuationError,
            "owner_cash_flow_per_share must be positive",
        ):
            evaluate_cash_flow_dcf(bad)

    def test_probabilities_must_sum_to_one(self):
        request = self._request()
        rows = list(request.scenarios)
        rows[0] = CashFlowDCFScenario(
            **{
                **rows[0].__dict__,
                "probability": 0.20,
            }
        )
        bad = CashFlowDCFInput(
            **{
                **request.__dict__,
                "scenarios": tuple(rows),
            }
        )
        with self.assertRaisesRegex(
            CashFlowValuationError,
            "scenario probabilities must sum to 1",
        ):
            evaluate_cash_flow_dcf(bad)

    def test_capital_authority_remains_false(self):
        result = evaluate_cash_flow_dcf(self._request())
        self.assertFalse(result.authority["model_called"])
        self.assertFalse(
            result.authority["canonical_evidence_created"]
        )
        self.assertFalse(
            result.authority["portfolio_proposal_created"]
        )
        self.assertFalse(
            result.authority["committee_decision_created"]
        )
        self.assertFalse(result.authority["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
