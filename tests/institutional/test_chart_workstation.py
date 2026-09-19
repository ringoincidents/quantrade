from __future__ import annotations

import os
import tempfile
import unittest

from quantrade.institutional.chart_workstation import (
    MarketDataPlane,
    install_chart_workstation,
    synthetic_chart_bars,
)
from quantrade.institutional.employee_agent import EmployeeAgent, ModelAction, ScriptedModelProvider
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.service import InstitutionalKernel
from quantrade.institutional.tools import ToolRegistry


class ChartWorkstationTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.org = OrganizationRuntime(self.kernel)
        self.tools = ToolRegistry(self.kernel)
        self.employee = self.org.create_employee(
            "IID-CHART",
            "Chart Analyst",
            "Investigate technical structure and event patterns with deterministic market tools.",
            authority={"read_only_research": True, "live_orders": False},
            employee_id="EMP-CHART-P13E",
        )
        self.market = MarketDataPlane(synthetic_chart_bars())
        install_chart_workstation(self.tools, self.employee, self.market)
        self.order = self.org.create_work_order(
            issuer_type="EMPLOYEE",
            issuer_id="EMP-STRATEGY-01",
            recipient_office="IID-CHART",
            recipient_employee_id=self.employee,
            objective=(
                "Collect recent sharp-rising charts and investigate volume, moving averages, "
                "Ichimoku position and forward returns for reusable hypotheses."
            ),
            authority_scope={"research": True, "trade": False},
            budget={"max_tool_calls": 20},
        )

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_chart_employee_discovers_composable_tools_not_breakout_command(self):
        names = [t["name"] for t in self.tools.discover(self.employee)]
        self.assertEqual(
            [
                "chart.candlestick_spec", "market.catalog", "market.event_scan",
                "market.ohlcv", "technical.event_study", "technical.indicators",
            ],
            names,
        )
        self.assertFalse(any("breakout_strategy" in n for n in names))

    def test_market_catalog_exposes_real_available_timeframes_only(self):
        catalog = self.tools.invoke(
            employee_id=self.employee, work_order_id=self.order,
            tool_name="market.catalog", arguments={},
        )
        self.assertEqual(["60m", "D"], catalog["KRX001"]["timeframes"])
        self.assertEqual(["D"], catalog["KRX003"]["timeframes"])
        with self.assertRaises(KeyError):
            self.tools.invoke(
                employee_id=self.employee, work_order_id=self.order,
                tool_name="market.ohlcv",
                arguments={"symbol": "KRX001", "timeframe": "5m"},
            )

    def test_indicator_engine_calculates_requested_series(self):
        data = self.market.ohlcv({"symbol": "KRX001", "timeframe": "D"})
        result = self.tools.invoke(
            employee_id=self.employee, work_order_id=self.order,
            tool_name="technical.indicators",
            arguments={
                "bars": data["bars"],
                "indicators": [
                    {"name": "SMA", "period": 20},
                    {"name": "EMA", "period": 20},
                    {"name": "RSI", "period": 14},
                    {"name": "BOLLINGER", "period": 20, "stddev": 2},
                    {"name": "ATR", "period": 14},
                    {"name": "ICHIMOKU"},
                ],
            },
        )
        series = result["series"]
        for key in (
            "SMA_20", "EMA_20", "RSI_14", "BB_MID_20", "BB_UPPER_20",
            "BB_LOWER_20", "ATR_14", "ICHIMOKU_TENKAN",
            "ICHIMOKU_KIJUN", "ICHIMOKU_SPAN_A_RAW", "ICHIMOKU_SPAN_B_RAW",
        ):
            self.assertIn(key, series)
            self.assertEqual(len(data["bars"]), len(series[key]))

    def test_generic_event_scan_can_collect_volume_backed_sharp_moves(self):
        events = self.tools.invoke(
            employee_id=self.employee, work_order_id=self.order,
            tool_name="market.event_scan",
            arguments={
                "timeframe": "D",
                "lookback_bars": 5,
                "min_return_pct": 5.0,
                "min_volume_multiple": 2.0,
            },
        )
        symbols = [e["symbol"] for e in events]
        self.assertIn("KRX001", symbols)
        self.assertIn("KRX003", symbols)
        self.assertNotIn("KRX002", symbols)

    def test_chart_spec_and_event_study_are_separate_primitives(self):
        data = self.market.ohlcv({"symbol": "KRX001", "timeframe": "D"})
        indicators = self.tools.invoke(
            employee_id=self.employee, work_order_id=self.order,
            tool_name="technical.indicators",
            arguments={"bars": data["bars"], "indicators": [{"name": "SMA", "period": 20}]},
        )
        spec = self.tools.invoke(
            employee_id=self.employee, work_order_id=self.order,
            tool_name="chart.candlestick_spec",
            arguments={
                "symbol": "KRX001",
                "timeframe": "D",
                "bars": data["bars"],
                "overlays": indicators["series"],
                "annotations": [{"bar_index": -1, "label": "synthetic event"}],
            },
        )
        self.assertEqual("quantrade_chart_v1", spec["renderer_contract"])
        self.assertIn("SMA_20", spec["overlays"])

        study = self.tools.invoke(
            employee_id=self.employee, work_order_id=self.order,
            tool_name="technical.event_study",
            arguments={
                "bars": data["bars"],
                "event_index": -3,
                "forward_horizons": [1, 2, 5],
            },
        )
        self.assertIsNotNone(study["forward_return_pct"]["1"])
        self.assertIsNotNone(study["forward_return_pct"]["2"])
        self.assertIsNone(study["forward_return_pct"]["5"])

    def test_employee_can_initiate_pattern_collection_from_broad_request(self):
        provider = ScriptedModelProvider([
            ModelAction("UPDATE_PLAN", {"plan": {
                "steps": [
                    "discover coverage", "scan sharp moves with volume",
                    "retrieve event windows", "calculate indicators",
                    "build chart collection", "test hypotheses",
                ]
            }}),
            ModelAction("TOOL", {
                "tool_name": "market.catalog", "arguments": {}, "label": "coverage"
            }),
            ModelAction("TOOL", {
                "tool_name": "market.event_scan",
                "arguments": {
                    "timeframe": "D", "lookback_bars": 5,
                    "min_return_pct": 5.0, "min_volume_multiple": 2.0,
                },
                "label": "sharp_move_events",
            }),
            ModelAction("SAVE_WORKSPACE", {"state": {
                "research_question": (
                    "Do volume-backed sharp moves share reusable pre-event technical structure?"
                ),
                "next_checks": ["MA location", "Ichimoku cloud", "forward returns", "failed cases"],
            }}),
            ModelAction("FINISH", {
                "summary": "Event collection created; deeper indicator comparison remains research work."
            }),
        ])
        result = EmployeeAgent(
            self.kernel, self.org, self.tools, provider, max_iterations=8
        ).run(employee_id=self.employee, work_order_id=self.order)
        self.assertEqual("COMPLETED", result["status"])
        invocations = self.kernel.conn.execute(
            "SELECT tool_name FROM tool_invocations WHERE work_order_id=? ORDER BY started_at",
            (self.order,),
        ).fetchall()
        self.assertEqual(
            ["market.catalog", "market.event_scan"],
            [r["tool_name"] for r in invocations],
        )

    def test_no_execution_capability(self):
        names = [t["name"] for t in self.tools.discover(self.employee)]
        self.assertTrue(all("broker" not in n and "submit_order" not in n for n in names))


if __name__ == "__main__":
    unittest.main()
