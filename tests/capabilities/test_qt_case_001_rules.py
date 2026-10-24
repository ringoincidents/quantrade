import unittest

from scripts.run_qt_case_001 import (
    EPS_PERIOD_KEY,
    EPS_YTD_KEY,
    GoldenRunError,
    build_historical_pe,
    compute_ttm_eps,
    last_close_on_or_before,
    percentile_linear,
)


class QTCase001FrozenRulesTests(unittest.TestCase):
    def test_percentile_linear_matches_frozen_interpolation(self):
        values = [10.0, 20.0, 30.0, 40.0]
        self.assertEqual(17.5, percentile_linear(values, 0.25))
        self.assertEqual(25.0, percentile_linear(values, 0.50))
        self.assertEqual(32.5, percentile_linear(values, 0.75))

    def test_last_close_can_use_prior_trading_day(self):
        rows = [
            {"date": "2026-10-01", "close": 100.0},
            {"date": "2026-10-02", "close": 101.0},
            {"date": "2026-10-06", "close": 103.0},
        ]
        selected = last_close_on_or_before(
            rows,
            "2026-10-05",
            same_calendar_year=True,
        )
        self.assertEqual("2026-10-02", selected["date"])
        self.assertEqual(101.0, selected["close"])

    def test_last_close_never_uses_future_price(self):
        rows = [
            {"date": "2026-10-06", "close": 103.0},
        ]
        with self.assertRaisesRegex(
            GoldenRunError,
            "no Naver close available",
        ):
            last_close_on_or_before(
                rows,
                "2026-10-05",
                same_calendar_year=True,
            )

    def test_ttm_eps_uses_exact_preregistered_bridge_formula(self):
        observations = [
            {
                "observation_id": "FY2025",
                "fiscal_period_end": "2025-12-31",
                "metric_key": EPS_PERIOD_KEY,
                "value": 6605.0,
                "evidence_ref": "fixture://fy2025",
            },
            {
                "observation_id": "H1-2025",
                "fiscal_period_end": "2025-06-30",
                "metric_key": EPS_YTD_KEY,
                "value": 1929.0,
                "evidence_ref": "fixture://h12025",
            },
            {
                "observation_id": "H1-2026",
                "fiscal_period_end": "2026-06-30",
                "metric_key": EPS_YTD_KEY,
                "value": 4000.0,
                "evidence_ref": "fixture://h12026",
            },
        ]
        result = compute_ttm_eps(observations)
        self.assertEqual(8676.0, result["ttm_eps"])
        self.assertEqual(
            ("FY2025", "H1-2025", "H1-2026"),
            result["source_observation_ids"],
        )

    def test_ttm_missing_required_row_fails_closed(self):
        observations = [
            {
                "observation_id": "FY2025",
                "fiscal_period_end": "2025-12-31",
                "metric_key": EPS_PERIOD_KEY,
                "value": 6605.0,
                "evidence_ref": "fixture://fy2025",
            }
        ]
        with self.assertRaisesRegex(
            GoldenRunError,
            "must be unique",
        ):
            compute_ttm_eps(observations)

    def test_historical_pe_keeps_all_four_frozen_years(self):
        observations = []
        eps_values = {
            2022: 1000.0,
            2023: 2000.0,
            2024: 2500.0,
            2025: 3000.0,
        }
        for year, eps in eps_values.items():
            observations.append(
                {
                    "observation_id": f"EPS-{year}",
                    "fiscal_period_end": f"{year}-12-31",
                    "metric_key": EPS_PERIOD_KEY,
                    "value": eps,
                    "evidence_ref": f"fixture://eps/{year}",
                }
            )
        prices = [
            {"date": "2022-12-29", "close": 60000.0},
            {"date": "2023-12-28", "close": 70000.0},
            {"date": "2024-12-30", "close": 50000.0},
            {"date": "2025-12-30", "close": 90000.0},
        ]
        result = build_historical_pe(observations, prices)
        self.assertEqual(4, len(result["rows"]))
        self.assertEqual(
            [2022, 2023, 2024, 2025],
            [row["year"] for row in result["rows"]],
        )
        self.assertEqual(60.0, result["rows"][0]["pe"])
        self.assertEqual(35.0, result["rows"][1]["pe"])
        self.assertEqual(20.0, result["rows"][2]["pe"])
        self.assertEqual(30.0, result["rows"][3]["pe"])

    def test_nonpositive_annual_eps_cannot_be_dropped_as_outlier(self):
        observations = []
        for year, eps in {
            2022: 1000.0,
            2023: 0.0,
            2024: 2500.0,
            2025: 3000.0,
        }.items():
            observations.append(
                {
                    "observation_id": f"EPS-{year}",
                    "fiscal_period_end": f"{year}-12-31",
                    "metric_key": EPS_PERIOD_KEY,
                    "value": eps,
                    "evidence_ref": f"fixture://eps/{year}",
                }
            )
        prices = [
            {"date": "2022-12-29", "close": 60000.0},
            {"date": "2023-12-28", "close": 70000.0},
            {"date": "2024-12-30", "close": 50000.0},
            {"date": "2025-12-30", "close": 90000.0},
        ]
        with self.assertRaisesRegex(
            GoldenRunError,
            "2023 annual EPS is non-positive",
        ):
            build_historical_pe(observations, prices)


if __name__ == "__main__":
    unittest.main()
