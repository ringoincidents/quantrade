import unittest

from scripts.run_qt_case_002 import (
    BASIC_EPS_PERIOD_KEY,
    CFO_KEY,
    INTANGIBLE_CAPEX_KEY,
    OWNER_PROFIT_PERIOD_KEY,
    OWNER_PROFIT_YTD_KEY,
    PARENT_EQUITY_KEY,
    PPE_CAPEX_KEY,
    GoldenRunError,
    annual_cash_flow_history,
    historical_pb,
    implied_basic_shares,
    owner_cash_flow_for_period,
    ttm_cash_flow,
    ttm_parent_profit,
)


def obs(period, key, value, oid):
    return {
        "observation_id": oid,
        "fiscal_period_end": period,
        "metric_key": key,
        "value": value,
        "evidence_ref": f"fixture://{oid}",
    }


class QTCase002FrozenRulesTests(unittest.TestCase):
    def test_owner_cash_flow_proxy_subtracts_both_capex_lines(self):
        rows = [
            obs("2025-12-31", CFO_KEY, 100.0, "CFO"),
            obs("2025-12-31", PPE_CAPEX_KEY, 30.0, "PPE"),
            obs("2025-12-31", INTANGIBLE_CAPEX_KEY, 10.0, "INT"),
        ]
        result = owner_cash_flow_for_period(
            rows,
            "2025-12-31",
        )
        self.assertEqual(60.0, result["owner_cash_flow_proxy"])

    def test_ttm_cash_flow_uses_exact_bridge_formula(self):
        rows = []
        for period, cfo, ppe, intangible, prefix in (
            ("2025-12-31", 100.0, 30.0, 10.0, "FY"),
            ("2025-06-30", 40.0, 12.0, 3.0, "H125"),
            ("2026-06-30", 80.0, 20.0, 5.0, "H126"),
        ):
            rows.extend(
                (
                    obs(period, CFO_KEY, cfo, f"{prefix}-CFO"),
                    obs(period, PPE_CAPEX_KEY, ppe, f"{prefix}-PPE"),
                    obs(
                        period,
                        INTANGIBLE_CAPEX_KEY,
                        intangible,
                        f"{prefix}-INT",
                    ),
                )
            )
        result = ttm_cash_flow(rows)
        # FY=60, H1-25=25, H1-26=55 => TTM=90.
        self.assertEqual(
            90.0,
            result["ttm_owner_cash_flow_proxy"],
        )

    def test_nonpositive_ttm_cash_flow_fails_closed(self):
        rows = []
        for period, cfo, ppe, intangible, prefix in (
            ("2025-12-31", 30.0, 20.0, 10.0, "FY"),
            ("2025-06-30", 40.0, 20.0, 10.0, "H125"),
            ("2026-06-30", 20.0, 15.0, 5.0, "H126"),
        ):
            rows.extend(
                (
                    obs(period, CFO_KEY, cfo, f"{prefix}-CFO"),
                    obs(period, PPE_CAPEX_KEY, ppe, f"{prefix}-PPE"),
                    obs(
                        period,
                        INTANGIBLE_CAPEX_KEY,
                        intangible,
                        f"{prefix}-INT",
                    ),
                )
            )
        with self.assertRaisesRegex(
            GoldenRunError,
            "NON_POSITIVE_TTM_OWNER_CASH_FLOW",
        ):
            ttm_cash_flow(rows)

    def test_ttm_parent_profit_uses_annual_plus_h1_bridge(self):
        rows = [
            obs(
                "2025-12-31",
                OWNER_PROFIT_PERIOD_KEY,
                100.0,
                "FY-P",
            ),
            obs(
                "2025-06-30",
                OWNER_PROFIT_YTD_KEY,
                40.0,
                "H125-P",
            ),
            obs(
                "2026-06-30",
                OWNER_PROFIT_YTD_KEY,
                70.0,
                "H126-P",
            ),
        ]
        result = ttm_parent_profit(rows)
        self.assertEqual(
            130.0,
            result["ttm_profit_attributable_to_owners"],
        )

    def test_implied_basic_shares_uses_fy2025_parent_profit_over_eps(self):
        rows = [
            obs(
                "2025-12-31",
                OWNER_PROFIT_PERIOD_KEY,
                60_000.0,
                "PROFIT",
            ),
            obs(
                "2025-12-31",
                BASIC_EPS_PERIOD_KEY,
                10.0,
                "EPS",
            ),
        ]
        result = implied_basic_shares(rows)
        self.assertEqual(
            6000.0,
            result["implied_basic_shares"],
        )
        self.assertTrue(
            result["accounting_derived_approximation"]
        )

    def test_annual_cash_conversion_requires_all_frozen_years(self):
        rows = []
        for year in (2022, 2023, 2024, 2025):
            period = f"{year}-12-31"
            rows.extend(
                (
                    obs(period, CFO_KEY, 100.0, f"{year}-CFO"),
                    obs(period, PPE_CAPEX_KEY, 20.0, f"{year}-PPE"),
                    obs(
                        period,
                        INTANGIBLE_CAPEX_KEY,
                        10.0,
                        f"{year}-INT",
                    ),
                    obs(
                        period,
                        OWNER_PROFIT_PERIOD_KEY,
                        100.0,
                        f"{year}-PROFIT",
                    ),
                )
            )
        result = annual_cash_flow_history(rows)
        self.assertEqual(
            [2022, 2023, 2024, 2025],
            list(result),
        )
        for year in result:
            self.assertEqual(
                0.7,
                result[year]["cash_conversion_ratio"],
            )

    def test_historical_pb_uses_same_frozen_implied_share_denominator(self):
        rows = []
        for year, equity in (
            (2022, 1000.0),
            (2023, 1200.0),
            (2024, 1400.0),
            (2025, 1600.0),
        ):
            rows.append(
                obs(
                    f"{year}-12-31",
                    PARENT_EQUITY_KEY,
                    equity,
                    f"{year}-EQ",
                )
            )
        prices = [
            {"date": "2022-12-29", "close": 10.0},
            {"date": "2023-12-28", "close": 12.0},
            {"date": "2024-12-30", "close": 14.0},
            {"date": "2025-12-30", "close": 16.0},
        ]
        result = historical_pb(
            rows,
            prices,
            shares=100.0,
            current_price=20.0,
        )
        self.assertEqual(4, len(result["rows"]))
        self.assertEqual(1.0, result["rows"][0]["pb"])
        self.assertEqual(1.25, result["current_pb"])


if __name__ == "__main__":
    unittest.main()
