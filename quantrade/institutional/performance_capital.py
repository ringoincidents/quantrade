from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .client_capital import AutonomousWorkEngine, ClientCapitalRuntime


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PerformanceCapitalLoop:
    """Performance -> Client Capital reconciliation -> new Mandate -> internal work.

    Performance facts are recorded separately from the capital decision. Profit
    is never assumed to be fully reinvestable: current Client cash needs are
    re-applied through ClientCapitalRuntime before any deployment WorkOrder is
    generated.
    """

    def __init__(self, capital: ClientCapitalRuntime):
        self.capital = capital
        self.kernel = capital.kernel
        self.org = capital.org
        self.conn = capital.conn

    def record_performance(
        self,
        client_id: str,
        *,
        period_start: str,
        period_end: str,
        start_value: float,
        end_value: float,
        net_external_flows: float = 0.0,
        realized_pnl: float = 0.0,
        investment_income: float = 0.0,
        fees: float = 0.0,
        taxes: float = 0.0,
        attribution: dict | None = None,
    ) -> str:
        pid = _id("PERF")
        economic_pnl = float(end_value) - float(start_value) - float(net_external_flows)
        payload = dict(attribution or {})
        payload["economic_pnl"] = economic_pnl
        payload["reported_realized_pnl"] = float(realized_pnl)
        payload["reported_investment_income"] = float(investment_income)
        payload["unexplained_vs_realized_income"] = (
            economic_pnl
            - float(realized_pnl)
            - float(investment_income)
            + float(fees)
            + float(taxes)
        )
        with self.conn:
            self.conn.execute(
                """INSERT INTO performance_records
                (performance_id,client_id,period_start,period_end,start_value,end_value,
                 net_external_flows,realized_pnl,investment_income,fees,taxes,
                 attribution_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pid, client_id, period_start, period_end, float(start_value),
                    float(end_value), float(net_external_flows), float(realized_pnl),
                    float(investment_income), float(fees), float(taxes),
                    _json(payload), _now(),
                ),
            )
        self.kernel.record_activity(
            "Client", client_id, "PERFORMANCE_RECORDED",
            {
                "performance_id": pid,
                "period_start": period_start,
                "period_end": period_end,
                "economic_pnl": economic_pnl,
            },
        )
        return pid

    def reconcile(
        self,
        client_id: str,
        *,
        as_of: str,
        client_liquid_cash: float,
        brokerage_cash: float,
        invested_market_value: float,
        performance_id: str | None = None,
        previous_mandate_id: str | None = None,
        strategy_performance_state: dict | None = None,
        institutional_state: dict | None = None,
    ) -> dict:
        if performance_id:
            perf = self.conn.execute(
                """SELECT * FROM performance_records
                WHERE performance_id=? AND client_id=?""",
                (performance_id, client_id),
            ).fetchone()
            if not perf:
                raise KeyError(performance_id)

        # Both cash buckets are liquid facts. Existing invested market value is
        # tracked separately so reserve money is protected before deployment.
        total_liquid_cash = float(client_liquid_cash) + float(brokerage_cash)
        capital_plan_id = self.capital.build_capital_plan(
            client_id,
            liquid_assets=total_liquid_cash,
            portfolio_value=float(invested_market_value),
            as_of=as_of,
        )
        plan = self.capital.get_capital_plan(capital_plan_id)
        new_mandate_id = self.capital.create_mandate(capital_plan_id)
        mandate = self.capital.get_mandate(new_mandate_id)

        deployable_cash = float(plan["investable_now"])
        previous_deployable = 0.0
        if previous_mandate_id:
            previous = self.capital.get_mandate(previous_mandate_id)
            if previous["client_id"] != client_id:
                raise ValueError("previous mandate belongs to a different Client")
            previous_deployable = float(previous.get("investable_capital", 0.0) or 0.0)
        incremental_surplus = max(0.0, deployable_cash - previous_deployable)
        result = {
            "schema": "performance_capital_reconciliation_v1",
            "client_id": client_id,
            "as_of": as_of,
            "performance_id": performance_id,
            "previous_mandate_id": previous_mandate_id,
            "new_capital_plan_id": capital_plan_id,
            "new_mandate_id": new_mandate_id,
            "client_liquid_cash": float(client_liquid_cash),
            "brokerage_cash": float(brokerage_cash),
            "invested_market_value": float(invested_market_value),
            "protected_liquidity_reserve": float(plan["liquidity_reserve"]),
            "deployable_cash_after_client_needs": deployable_cash,
            "previous_deployable_cash": previous_deployable,
            "incremental_investable_surplus": incremental_surplus,
            "planning_conflicts": plan["conflicts"],
            "live_execution_authorized": False,
        }

        rid = _id("RECON")
        with self.conn:
            self.conn.execute(
                """INSERT INTO capital_reconciliations
                (reconciliation_id,client_id,performance_id,previous_mandate_id,
                 new_capital_plan_id,new_mandate_id,result_json,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    rid, client_id, performance_id, previous_mandate_id,
                    capital_plan_id, new_mandate_id, _json(result), _now(),
                ),
            )
        self.kernel.record_activity(
            "Client", client_id, "CAPITAL_RECONCILED",
            {
                "reconciliation_id": rid,
                "performance_id": performance_id,
                "new_mandate_id": new_mandate_id,
                "deployable_cash_after_client_needs": deployable_cash,
            },
        )

        state = dict(institutional_state or {})
        # A deployable balance becomes planning work, never an automatic order.
        state["new_investable_surplus"] = incremental_surplus
        if strategy_performance_state is not None:
            state["strategy_performance"] = strategy_performance_state

        work_orders = AutonomousWorkEngine(self.capital).evaluate(
            new_mandate_id, state
        )
        result["generated_work_orders"] = work_orders
        result["reconciliation_id"] = rid
        result["mandate_status"] = mandate["status"]
        return result

    def performance_record(self, performance_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM performance_records WHERE performance_id=?",
            (performance_id,),
        ).fetchone()
        if not row:
            raise KeyError(performance_id)
        out = dict(row)
        out["attribution"] = json.loads(out.pop("attribution_json"))
        return out
