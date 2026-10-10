import unittest

from quantrade.capabilities.fundamental_semantics import (
    SemanticMetricApplicabilityInput,
    evaluate_semantic_metric_applicability,
)
from scripts.run_qt_case_004 import (
    CASE_ID,
    DCF_REQUIREMENTS,
    PE_REQUIREMENTS,
    PREREGISTRATION_COMMIT,
    SYMBOL,
    method_gate,
)


def observation(oid, metric_key, period, value):
    return {
        "observation_id": oid,
        "asset_id": "KRX:005380",
        "metric_key": metric_key,
        "value": float(value),
        "unit": "KRW",
        "fiscal_period_end": period,
        "published_at": "2026-03-10T23:59:59+09:00",
        "evidence_ref": f"fixture://{oid}",
    }


def build_semantics(*, fy2025_eps=100.0, ttm_cf_positive=True):
    observations = []

    for year, eps in (
        (2022, 80.0),
        (2023, 90.0),
        (2024, 95.0),
        (2025, fy2025_eps),
    ):
        observations.append(
            observation(
                f"EPS-{year}",
                "DART_ACCOUNT:"
                "ifrs-full_BasicEarningsLossPerShare:"
                "CIS:CURRENT_PERIOD",
                f"{year}-12-31",
                eps,
            )
        )

    observations.extend(
        (
            observation(
                "EPS-H125",
                "DART_ACCOUNT:"
                "ifrs-full_BasicEarningsLossPerShare:"
                "CIS:CURRENT_YTD",
                "2025-06-30",
                40.0,
            ),
            observation(
                "EPS-H126",
                "DART_ACCOUNT:"
                "ifrs-full_BasicEarningsLossPerShare:"
                "CIS:CURRENT_YTD",
                "2026-06-30",
                60.0,
            ),
        )
    )

    for year, profit in (
        (2022, 8000.0),
        (2023, 9000.0),
        (2024, 9500.0),
        (2025, 10000.0),
    ):
        observations.append(
            observation(
                f"PROFIT-{year}",
                "DART_ACCOUNT:"
                "ifrs-full_ProfitLossAttributableToOwnersOfParent:"
                "CIS:CURRENT_PERIOD",
                f"{year}-12-31",
                profit,
            )
        )

    observations.extend(
        (
            observation(
                "PROFIT-H125",
                "DART_ACCOUNT:"
                "ifrs-full_ProfitLossAttributableToOwnersOfParent:"
                "CIS:CURRENT_YTD",
                "2025-06-30",
                4000.0,
            ),
            observation(
                "PROFIT-H126",
                "DART_ACCOUNT:"
                "ifrs-full_ProfitLossAttributableToOwnersOfParent:"
                "CIS:CURRENT_YTD",
                "2026-06-30",
                6000.0,
            ),
        )
    )

    for period in (
        "2022-12-31",
        "2023-12-31",
        "2024-12-31",
        "2025-12-31",
        "2025-06-30",
        "2026-06-30",
    ):
        cfo = 1000.0
        ppe = 200.0
        intangible = 50.0
        if not ttm_cf_positive and period == "2026-06-30":
            cfo = -2000.0
        observations.extend(
            (
                observation(
                    f"CFO-{period}",
                    "DART_ACCOUNT:"
                    "ifrs-full_CashFlowsFromUsedInOperatingActivities:"
                    "CF:CURRENT_PERIOD",
                    period,
                    cfo,
                ),
                observation(
                    f"PPE-{period}",
                    "DART_ACCOUNT:"
                    "ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities:"
                    "CF:CURRENT_PERIOD",
                    period,
                    ppe,
                ),
                observation(
                    f"INT-{period}",
                    "DART_ACCOUNT:"
                    "ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities:"
                    "CF:CURRENT_PERIOD",
                    period,
                    intangible,
                ),
            )
        )

    for year, equity in (
        (2022, 20000.0),
        (2023, 22000.0),
        (2024, 24000.0),
        (2025, 26000.0),
    ):
        observations.append(
            observation(
                f"EQ-{year}",
                "DART_ACCOUNT:"
                "ifrs-full_EquityAttributableToOwnersOfParent:"
                "BS:CURRENT_PERIOD",
                f"{year}-12-31",
                equity,
            )
        )

    pe = evaluate_semantic_metric_applicability(
        SemanticMetricApplicabilityInput(
            case_id=CASE_ID,
            observations=tuple(observations),
            requirements=PE_REQUIREMENTS,
        )
    )
    dcf = evaluate_semantic_metric_applicability(
        SemanticMetricApplicabilityInput(
            case_id=CASE_ID,
            observations=tuple(observations),
            requirements=DCF_REQUIREMENTS,
        )
    )
    return pe, dcf


class QTCase004FrozenRulesTests(unittest.TestCase):
    def test_target_and_preregistration_are_frozen(self):
        self.assertEqual("005380", SYMBOL)
        self.assertEqual(
            "5c7f5696479c3787843abca8799e937950f2daff",
            PREREGISTRATION_COMMIT,
        )

    def test_eps_semantics_allow_is_or_cis_before_result(self):
        annual = next(
            item
            for item in PE_REQUIREMENTS
            if item.requirement_id == "EPS_ANNUAL"
        )
        self.assertEqual(
            ("IS", "CIS"),
            annual.allowed_statement_divisions,
        )

    def test_positive_semantics_make_both_methods_ready(self):
        pe, dcf = build_semantics()
        result = method_gate(
            pe_semantic=pe,
            dcf_semantic=dcf,
        )
        self.assertEqual("READY", result["pe_method"].status)
        self.assertEqual("READY", result["dcf_method"].status)

    def test_nonpositive_annual_eps_blocks_pe_without_substitution(self):
        pe, dcf = build_semantics(fy2025_eps=-10.0)
        result = method_gate(
            pe_semantic=pe,
            dcf_semantic=dcf,
        )
        self.assertEqual(
            "NOT_APPLICABLE",
            result["pe_method"].status,
        )
        self.assertIn(
            "NON_POSITIVE_ANNUAL_EPS",
            result["pe_method"].reasons,
        )
        self.assertFalse(
            result["pe_method"].authority[
                "substitute_method_selected"
            ]
        )

    def test_nonpositive_ttm_owner_cash_flow_blocks_dcf(self):
        pe, dcf = build_semantics(ttm_cf_positive=False)
        result = method_gate(
            pe_semantic=pe,
            dcf_semantic=dcf,
        )
        self.assertEqual(
            "NOT_APPLICABLE",
            result["dcf_method"].status,
        )
        self.assertIn(
            "NON_POSITIVE_TTM_OWNER_CASH_FLOW",
            result["dcf_method"].reasons,
        )
        self.assertFalse(
            result["dcf_method"].authority[
                "substitute_method_selected"
            ]
        )


if __name__ == "__main__":
    unittest.main()
