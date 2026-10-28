import unittest

from quantrade.capabilities.fundamental_counter_research import (
    AnnualCashConversion,
    FundamentalCounterResearchError,
    FundamentalCounterResearchInput,
    FundamentalCounterResearchPolicy,
    evaluate_fundamental_counter_research,
)


class FundamentalCounterResearchTests(unittest.TestCase):
    def _request(self):
        return FundamentalCounterResearchInput(
            case_id="CASE-COUNTER",
            annual_cash_conversion=(
                AnnualCashConversion(2022, 80.0, 100.0),
                AnnualCashConversion(2023, 60.0, 100.0),
                AnnualCashConversion(2024, 90.0, 100.0),
                AnnualCashConversion(2025, 100.0, 100.0),
            ),
            ttm_owner_cash_flow_proxy=70.0,
            ttm_profit_attributable_to_owners=100.0,
            historical_pe_values=(7.0, 37.0, 11.0, 18.0),
            historical_pb_values=(1.0, 1.5, 1.2, 1.8),
            current_pb=2.0,
            policy=FundamentalCounterResearchPolicy(
                multiple_dispersion_ratio_threshold=4.0,
                cash_conversion_threshold=0.75,
            ),
        )

    def test_flags_multiple_dispersion_ttm_conversion_and_pb(self):
        result = evaluate_fundamental_counter_research(
            self._request()
        )
        self.assertEqual(
            "MATERIAL_COUNTER_EVIDENCE",
            result.status,
        )
        self.assertIn(
            "HIGH_MULTIPLE_REGIME_DISPERSION",
            result.flags,
        )
        self.assertIn(
            "WEAK_TTM_CASH_CONVERSION",
            result.flags,
        )
        self.assertIn(
            "CURRENT_PB_ABOVE_HISTORICAL_P75",
            result.flags,
        )
        self.assertNotIn(
            "WEAK_MEDIAN_CASH_CONVERSION",
            result.flags,
        )

    def test_negative_cash_flow_year_is_explicit(self):
        request = self._request()
        annual = list(request.annual_cash_conversion)
        annual[1] = AnnualCashConversion(
            2023,
            -10.0,
            100.0,
        )
        result = evaluate_fundamental_counter_research(
            FundamentalCounterResearchInput(
                **{
                    **request.__dict__,
                    "annual_cash_conversion": tuple(annual),
                }
            )
        )
        self.assertIn(
            "NEGATIVE_OWNER_CASH_FLOW_YEAR",
            result.flags,
        )

    def test_weak_median_cash_conversion_is_deterministic(self):
        request = self._request()
        annual = (
            AnnualCashConversion(2022, 50.0, 100.0),
            AnnualCashConversion(2023, 60.0, 100.0),
            AnnualCashConversion(2024, 70.0, 100.0),
            AnnualCashConversion(2025, 80.0, 100.0),
        )
        result = evaluate_fundamental_counter_research(
            FundamentalCounterResearchInput(
                **{
                    **request.__dict__,
                    "annual_cash_conversion": annual,
                }
            )
        )
        self.assertIn(
            "WEAK_MEDIAN_CASH_CONVERSION",
            result.flags,
        )
        self.assertEqual(
            0.65,
            result.metrics["median_annual_cash_conversion"],
        )

    def test_duplicate_fiscal_year_fails_closed(self):
        request = self._request()
        with self.assertRaisesRegex(
            FundamentalCounterResearchError,
            "duplicate fiscal_year",
        ):
            evaluate_fundamental_counter_research(
                FundamentalCounterResearchInput(
                    **{
                        **request.__dict__,
                        "annual_cash_conversion": (
                            AnnualCashConversion(2022, 80.0, 100.0),
                            AnnualCashConversion(2022, 90.0, 100.0),
                        ),
                    }
                )
            )

    def test_nonpositive_profit_fails_closed(self):
        request = self._request()
        with self.assertRaisesRegex(
            FundamentalCounterResearchError,
            "annual profit attributable to owners must be positive",
        ):
            evaluate_fundamental_counter_research(
                FundamentalCounterResearchInput(
                    **{
                        **request.__dict__,
                        "annual_cash_conversion": (
                            AnnualCashConversion(2022, 80.0, 0.0),
                        ),
                    }
                )
            )

    def test_no_counter_flag_when_all_checks_clear(self):
        result = evaluate_fundamental_counter_research(
            FundamentalCounterResearchInput(
                case_id="CASE-CLEAN",
                annual_cash_conversion=(
                    AnnualCashConversion(2022, 90.0, 100.0),
                    AnnualCashConversion(2023, 100.0, 100.0),
                    AnnualCashConversion(2024, 95.0, 100.0),
                    AnnualCashConversion(2025, 105.0, 100.0),
                ),
                ttm_owner_cash_flow_proxy=95.0,
                ttm_profit_attributable_to_owners=100.0,
                historical_pe_values=(10.0, 12.0, 14.0, 16.0),
                historical_pb_values=(1.0, 1.2, 1.4, 1.6),
                current_pb=1.3,
                policy=FundamentalCounterResearchPolicy(
                    multiple_dispersion_ratio_threshold=4.0,
                    cash_conversion_threshold=0.75,
                ),
            )
        )
        self.assertEqual(
            "NO_MATERIAL_COUNTER_FLAG",
            result.status,
        )
        self.assertEqual((), result.flags)

    def test_no_capital_authority(self):
        result = evaluate_fundamental_counter_research(
            self._request()
        )
        self.assertFalse(result.authority["model_called"])
        self.assertFalse(
            result.authority["portfolio_proposal_created"]
        )
        self.assertFalse(
            result.authority["committee_decision_created"]
        )
        self.assertFalse(result.authority["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
