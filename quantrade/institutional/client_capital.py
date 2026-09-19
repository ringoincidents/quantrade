from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from .organization import OrganizationRuntime
from .service import InstitutionalKernel


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + end.month - start.month)


def _monthly_rate_for_target_schedule(
    principal: float,
    monthly_contributions: list[float],
    target: float,
) -> float | None:
    """Solve a deterministic rate over a time-indexed contribution schedule.

    Contributions are applied at each month end, matching the ordinary-annuity
    convention used by the earlier constant-contribution implementation.
    """
    if not monthly_contributions:
        return 0.0 if principal >= target else None

    def fv(rate: float) -> float:
        value = float(principal)
        for contribution in monthly_contributions:
            value = value * (1.0 + rate) + float(contribution)
        return value

    if fv(0.0) >= target:
        return 0.0

    lo, hi = 0.0, (3.0 ** (1.0 / 12.0)) - 1.0
    if fv(hi) < target:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if fv(mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi


def _annualize(monthly_rate: float | None) -> float | None:
    if monthly_rate is None:
        return None
    return ((1.0 + monthly_rate) ** 12 - 1.0) * 100.0


@dataclass(frozen=True)
class CapitalPlanningPolicy:
    version: str = "client_capital_policy_epoch_a_time_indexed_v2"
    liquidity_horizon_months: int = 12


class ClientCapitalRuntime:
    """Client Intelligence -> deterministic Capital Plan -> Investment Mandate.

    The runtime does not infer psychological risk tolerance and does not choose
    securities. It converts explicit Client facts/constraints into planning
    facts that downstream offices can work from.
    """

    def __init__(
        self,
        kernel: InstitutionalKernel,
        organization: OrganizationRuntime,
        policy: CapitalPlanningPolicy | None = None,
    ):
        self.kernel = kernel
        self.org = organization
        self.conn = kernel.conn
        self.policy = policy or CapitalPlanningPolicy()

    def create_client(
        self,
        client_id: str,
        *,
        base_currency: str = "KRW",
        profile: dict | None = None,
        effective_at: str | None = None,
    ) -> str:
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO clients(client_id,base_currency,status,created_at)
                VALUES (?,?,?,?)""",
                (client_id, base_currency, "ACTIVE", now),
            )
        self.update_profile(client_id, profile or {}, effective_at=effective_at)
        self.kernel.record_activity(
            "Client", client_id, "CLIENT_CREATED",
            {"base_currency": base_currency},
        )
        return client_id

    def update_profile(
        self,
        client_id: str,
        profile: dict,
        *,
        effective_at: str | None = None,
    ) -> str:
        if not self.conn.execute(
            "SELECT 1 FROM clients WHERE client_id=?", (client_id,)
        ).fetchone():
            raise KeyError(client_id)
        version = self.conn.execute(
            """SELECT COALESCE(MAX(version),0)+1 v FROM client_profile_versions
            WHERE client_id=?""",
            (client_id,),
        ).fetchone()["v"]
        pvid = _id("CPV")
        with self.conn:
            self.conn.execute(
                """INSERT INTO client_profile_versions
                (profile_version_id,client_id,version,profile_json,effective_at,created_at)
                VALUES (?,?,?,?,?,?)""",
                (pvid, client_id, version, _json(profile), effective_at or _now(), _now()),
            )
        self.kernel.record_activity(
            "Client", client_id, "CLIENT_PROFILE_UPDATED",
            {"profile_version_id": pvid, "version": version},
        )
        return pvid

    def add_goal(
        self,
        client_id: str,
        name: str,
        target_amount: float,
        target_date: str,
        *,
        priority: str = "MEDIUM",
        required: bool = True,
        metadata: dict | None = None,
    ) -> str:
        gid = _id("GOAL")
        with self.conn:
            self.conn.execute(
                """INSERT INTO client_goals
                (goal_id,client_id,name,target_amount,target_date,priority,required,
                 metadata_json,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    gid, client_id, name, float(target_amount), target_date, priority,
                    int(required), _json(metadata or {}), "ACTIVE", _now(),
                ),
            )
        self.kernel.record_activity(
            "Client", client_id, "CLIENT_GOAL_ADDED",
            {"goal_id": gid, "name": name, "target_date": target_date},
        )
        return gid

    def add_cashflow(
        self,
        client_id: str,
        *,
        flow_type: str,
        amount: float,
        cadence: str,
        start_date: str,
        label: str,
        end_date: str | None = None,
        reserved: bool = False,
        metadata: dict | None = None,
    ) -> str:
        if flow_type not in {"INCOME", "EXPENSE"}:
            raise ValueError("flow_type must be INCOME or EXPENSE")
        if cadence not in {"ONE_TIME", "MONTHLY"}:
            raise ValueError("cadence must be ONE_TIME or MONTHLY")
        cid = _id("CF")
        with self.conn:
            self.conn.execute(
                """INSERT INTO client_cashflows
                (cashflow_id,client_id,flow_type,amount,cadence,start_date,end_date,
                 reserved,label,metadata_json,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid, client_id, flow_type, float(amount), cadence, start_date,
                    end_date, int(reserved), label, _json(metadata or {}), "ACTIVE", _now(),
                ),
            )
        self.kernel.record_activity(
            "Client", client_id, "CLIENT_CASHFLOW_ADDED",
            {"cashflow_id": cid, "flow_type": flow_type, "label": label},
        )
        return cid

    def _latest_profile(self, client_id: str) -> dict:
        row = self.conn.execute(
            """SELECT version,profile_json,effective_at FROM client_profile_versions
            WHERE client_id=? ORDER BY version DESC LIMIT 1""",
            (client_id,),
        ).fetchone()
        if not row:
            raise ValueError("client has no profile")
        return {
            "version": row["version"],
            "effective_at": row["effective_at"],
            "profile": json.loads(row["profile_json"]),
        }

    def _active_goals(self, client_id: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM client_goals
            WHERE client_id=? AND status='ACTIVE' ORDER BY target_date""",
            (client_id,),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            out.append(item)
        return out

    def _active_cashflows(self, client_id: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM client_cashflows
            WHERE client_id=? AND status='ACTIVE' ORDER BY start_date""",
            (client_id,),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            out.append(item)
        return out

    @staticmethod
    def _month_index(value: date) -> int:
        return value.year * 12 + value.month - 1

    @classmethod
    def _occurs_within(cls, flow: dict, as_of: date, horizon_months: int) -> int:
        """Count occurrences in [as_of month, as_of month + horizon_months).

        A 12-month planning horizon therefore contains exactly 12 monthly slots,
        not 13. Monthly cashflows use month-level planning granularity.
        """
        if horizon_months <= 0:
            return 0
        start = date.fromisoformat(flow["start_date"])
        as_index = cls._month_index(as_of)
        horizon_end_exclusive = as_index + horizon_months
        start_index = cls._month_index(start)

        if flow["cadence"] == "ONE_TIME":
            return int(start >= as_of and start_index < horizon_end_exclusive)

        first = max(as_index, start_index)
        last = horizon_end_exclusive - 1
        if flow.get("end_date"):
            end = date.fromisoformat(flow["end_date"])
            if end < as_of:
                return 0
            last = min(last, cls._month_index(end))
        return max(0, last - first + 1)

    @staticmethod
    def _monthly_flow_active_on(flow: dict, as_of: date) -> bool:
        if flow["cadence"] != "MONTHLY":
            return False
        start = date.fromisoformat(flow["start_date"])
        if start > as_of:
            return False
        if flow.get("end_date") and date.fromisoformat(flow["end_date"]) < as_of:
            return False
        return True

    @classmethod
    def _monthly_contribution_schedule(
        cls, cashflows: list[dict], as_of: date, months: int
    ) -> list[float]:
        """Return investable monthly surplus using each flow's actual active window."""
        schedule: list[float] = []
        base_index = cls._month_index(as_of)
        for offset in range(max(0, months)):
            month_index = base_index + offset
            income = 0.0
            expense = 0.0
            for flow in cashflows:
                if flow["cadence"] != "MONTHLY":
                    continue
                start_index = cls._month_index(date.fromisoformat(flow["start_date"]))
                if month_index < start_index:
                    continue
                if flow.get("end_date"):
                    end_index = cls._month_index(date.fromisoformat(flow["end_date"]))
                    if month_index > end_index:
                        continue
                if flow["flow_type"] == "INCOME":
                    income += float(flow["amount"])
                else:
                    expense += float(flow["amount"])
            schedule.append(max(0.0, income - expense))
        return schedule

    def build_capital_plan(
        self,
        client_id: str,
        *,
        liquid_assets: float,
        as_of: str,
        portfolio_value: float = 0.0,
    ) -> str:
        as_of_date = date.fromisoformat(as_of)
        latest = self._latest_profile(client_id)
        profile = latest["profile"]
        goals = self._active_goals(client_id)
        cashflows = self._active_cashflows(client_id)

        essential_monthly = float(profile.get("essential_monthly_spend", 0.0))
        reserve_months = int(profile.get("emergency_reserve_months", 0))
        emergency_reserve = essential_monthly * reserve_months

        horizon = self.policy.liquidity_horizon_months
        scheduled_reserved_outflows = 0.0
        recurring_monthly_income = 0.0
        recurring_monthly_expense = 0.0
        for flow in cashflows:
            count = self._occurs_within(flow, as_of_date, horizon)
            if flow["flow_type"] == "EXPENSE" and flow["reserved"]:
                scheduled_reserved_outflows += float(flow["amount"]) * count
            if self._monthly_flow_active_on(flow, as_of_date):
                if flow["flow_type"] == "INCOME":
                    recurring_monthly_income += float(flow["amount"])
                elif flow["flow_type"] == "EXPENSE":
                    recurring_monthly_expense += float(flow["amount"])

        liquidity_reserve = emergency_reserve + scheduled_reserved_outflows
        investable_now = max(0.0, float(liquid_assets) - liquidity_reserve)
        monthly_surplus = recurring_monthly_income - recurring_monthly_expense
        monthly_contribution = max(0.0, monthly_surplus)

        goal_analysis = []
        required_returns = []
        for goal in goals:
            funding_bucket = goal["metadata"].get("funding_bucket", "investment")
            if funding_bucket != "investment":
                goal_analysis.append({
                    "goal_id": goal["goal_id"],
                    "name": goal["name"],
                    "funding_bucket": funding_bucket,
                    "required_return_pct": None,
                    "note": "goal excluded from investment-return requirement",
                })
                continue
            months = _months_between(as_of_date, date.fromisoformat(goal["target_date"]))
            contribution_schedule = self._monthly_contribution_schedule(
                cashflows, as_of_date, months
            )
            monthly_rate = _monthly_rate_for_target_schedule(
                investable_now + float(portfolio_value),
                contribution_schedule,
                float(goal["target_amount"]),
            )
            annual = _annualize(monthly_rate)
            if annual is not None and goal["required"]:
                required_returns.append(annual)
            goal_analysis.append({
                "goal_id": goal["goal_id"],
                "name": goal["name"],
                "months": months,
                "target_amount": float(goal["target_amount"]),
                "required_return_pct": annual,
                "reachable_in_planning_search": annual is not None,
                "funding_bucket": funding_bucket,
            })

        required_return = max(required_returns) if required_returns else 0.0
        ceiling = profile.get("max_planning_return_pct")
        conflicts = []
        for item in goal_analysis:
            if (
                item.get("funding_bucket") == "investment"
                and item.get("reachable_in_planning_search") is False
            ):
                conflicts.append({
                    "type": "GOAL_UNREACHABLE_WITHIN_PLANNING_SEARCH",
                    "goal_id": item["goal_id"],
                    "name": item["name"],
                    "action": "review goal/timeline/contribution; do not manufacture an extreme return assumption",
                })
        if ceiling is not None and required_return > float(ceiling):
            conflicts.append({
                "type": "REQUIRED_RETURN_ABOVE_CLIENT_PLANNING_CEILING",
                "required_return_pct": required_return,
                "ceiling_pct": float(ceiling),
                "action": "review goal/timeline/contribution/risk policy; do not silently raise risk",
            })
        if float(liquid_assets) < liquidity_reserve:
            conflicts.append({
                "type": "LIQUIDITY_RESERVE_SHORTFALL",
                "shortfall": liquidity_reserve - float(liquid_assets),
                "action": "protect liquidity before new deployment",
            })

        result = {
            "schema": "client_capital_plan_v1",
            "client_id": client_id,
            "as_of": as_of,
            "profile_version": latest["version"],
            "liquid_assets": float(liquid_assets),
            "portfolio_value": float(portfolio_value),
            "emergency_reserve": emergency_reserve,
            "scheduled_reserved_outflows": scheduled_reserved_outflows,
            "liquidity_reserve": liquidity_reserve,
            "investable_now": investable_now,
            "recurring_monthly_income": recurring_monthly_income,
            "recurring_monthly_expense": recurring_monthly_expense,
            "monthly_investable_surplus": monthly_contribution,
            "required_return_pct": required_return,
            "explicit_max_drawdown_pct": profile.get("max_drawdown_pct"),
            "goal_analysis": goal_analysis,
            "conflicts": conflicts,
            "limitations": [
                "required return is a deterministic planning rate, not a forecast",
                "risk tolerance is never inferred from LLM behavior",
                "taxes/inflation are included only if supplied as explicit cashflows or goal assumptions",
                "monthly contribution assumptions are time-indexed to recorded cashflow start/end months",
            ],
        }
        cpid = _id("CAP")
        inputs = {
            "liquid_assets": float(liquid_assets),
            "portfolio_value": float(portfolio_value),
            "profile_version": latest["version"],
            "goal_ids": [g["goal_id"] for g in goals],
            "cashflow_ids": [c["cashflow_id"] for c in cashflows],
        }
        with self.conn:
            self.conn.execute(
                """INSERT INTO capital_plans
                (capital_plan_id,client_id,as_of,input_json,result_json,policy_version,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    cpid, client_id, as_of, _json(inputs), _json(result),
                    self.policy.version, _now(),
                ),
            )
        self.kernel.record_activity(
            "Client", client_id, "CAPITAL_PLAN_CREATED",
            {
                "capital_plan_id": cpid,
                "investable_now": investable_now,
                "required_return_pct": required_return,
                "conflict_count": len(conflicts),
            },
        )
        return cpid

    def create_mandate(self, capital_plan_id: str) -> str:
        row = self.conn.execute(
            "SELECT client_id,result_json FROM capital_plans WHERE capital_plan_id=?",
            (capital_plan_id,),
        ).fetchone()
        if not row:
            raise KeyError(capital_plan_id)
        plan = json.loads(row["result_json"])
        profile = self._latest_profile(row["client_id"])["profile"]
        mandate = {
            "schema": "investment_mandate_v1",
            "client_id": row["client_id"],
            "capital_plan_id": capital_plan_id,
            "investable_capital": plan["investable_now"],
            "monthly_investable_surplus": plan["monthly_investable_surplus"],
            "required_return_pct": plan["required_return_pct"],
            "max_drawdown_pct": plan["explicit_max_drawdown_pct"],
            "liquidity_reserve": plan["liquidity_reserve"],
            "research_universe": profile.get("research_universe", []),
            "prohibited_actions": profile.get(
                "prohibited_actions",
                ["LIVE_ORDER_WITHOUT_HUMAN_APPROVAL", "SILENT_POLICY_CHANGE"],
            ),
            "human_approval_required_for_live_execution": True,
            "planning_conflicts": plan["conflicts"],
            "authority": {
                "research": True,
                "backtest": True,
                "internal_work_generation": True,
                "live_execution": False,
                "policy_change": False,
            },
        }
        mid = _id("MANDATE")
        status = "REVIEW_REQUIRED" if plan["conflicts"] else "ACTIVE"
        with self.conn:
            self.conn.execute(
                """INSERT INTO investment_mandates
                (mandate_id,client_id,capital_plan_id,mandate_json,status,created_at)
                VALUES (?,?,?,?,?,?)""",
                (mid, row["client_id"], capital_plan_id, _json(mandate), status, _now()),
            )
        self.kernel.record_activity(
            "Client", row["client_id"], "INVESTMENT_MANDATE_CREATED",
            {"mandate_id": mid, "status": status},
        )
        return mid

    def get_capital_plan(self, capital_plan_id: str) -> dict:
        row = self.conn.execute(
            "SELECT result_json FROM capital_plans WHERE capital_plan_id=?",
            (capital_plan_id,),
        ).fetchone()
        if not row:
            raise KeyError(capital_plan_id)
        return json.loads(row["result_json"])

    def get_mandate(self, mandate_id: str) -> dict:
        row = self.conn.execute(
            "SELECT mandate_json,status FROM investment_mandates WHERE mandate_id=?",
            (mandate_id,),
        ).fetchone()
        if not row:
            raise KeyError(mandate_id)
        result = json.loads(row["mandate_json"])
        result["status"] = row["status"]
        return result


class AutonomousWorkEngine:
    """Deterministically turns mandate/state gaps into internal WorkOrders.

    This engine discovers *work to be done*. It never chooses a security or
    creates a trade. Employees receive the generated objectives and perform the
    flexible reasoning/research.
    """

    def __init__(self, capital: ClientCapitalRuntime):
        self.capital = capital
        self.org = capital.org
        self.kernel = capital.kernel
        self.conn = capital.conn

    @staticmethod
    def _fingerprint(mandate_id: str, trigger_type: str, payload: dict) -> str:
        raw = _json({
            "mandate_id": mandate_id,
            "trigger_type": trigger_type,
            "payload": payload,
        })
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _emit(
        self,
        mandate_id: str,
        *,
        trigger_type: str,
        payload: dict,
        recipient_office: str,
        objective: str,
        urgency: str = "NORMAL",
    ) -> str | None:
        fingerprint = self._fingerprint(mandate_id, trigger_type, payload)
        if self.conn.execute(
            "SELECT 1 FROM autonomous_work_triggers WHERE fingerprint=?",
            (fingerprint,),
        ).fetchone():
            return None

        mandate = self.capital.get_mandate(mandate_id)
        wid = self.org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="AUTONOMOUS_WORK_ENGINE",
            recipient_office=recipient_office,
            objective=objective,
            constraints={
                "mandate_id": mandate_id,
                "client_id": mandate["client_id"],
                "human_approval_required_for_live_execution": True,
            },
            urgency=urgency,
            authority_scope={
                "research": True,
                "backtest": True,
                "trade": False,
                "policy_change": False,
            },
            budget={"max_tool_calls": 40},
        )
        tid = _id("AWT")
        with self.conn:
            self.conn.execute(
                """INSERT INTO autonomous_work_triggers
                (trigger_id,mandate_id,trigger_type,fingerprint,work_order_id,
                 payload_json,status,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    tid, mandate_id, trigger_type, fingerprint, wid,
                    _json(payload), "ISSUED", _now(),
                ),
            )
        self.kernel.record_activity(
            "Mandate", mandate_id, "AUTONOMOUS_WORK_ISSUED",
            {
                "trigger_id": tid,
                "trigger_type": trigger_type,
                "work_order_id": wid,
                "recipient_office": recipient_office,
            },
        )
        return wid

    def evaluate(self, mandate_id: str, institutional_state: dict) -> list[str]:
        mandate = self.capital.get_mandate(mandate_id)
        created: list[str] = []

        if mandate["planning_conflicts"]:
            wid = self._emit(
                mandate_id,
                trigger_type="CAPITAL_PLAN_CONFLICT",
                payload={"conflicts": mandate["planning_conflicts"]},
                recipient_office="CCO",
                objective=(
                    "Review Client capital-plan conflicts. Prepare options that preserve "
                    "liquidity and explicit risk limits; do not raise risk or change policy "
                    "silently. Escalate only the material unresolved choice."
                ),
                urgency="HIGH",
            )
            if wid:
                created.append(wid)

        coverage = institutional_state.get("strategy_coverage", {})
        if coverage.get("status") in {"INSUFFICIENT", "STALE"}:
            wid = self._emit(
                mandate_id,
                trigger_type="STRATEGY_COVERAGE_GAP",
                payload=coverage,
                recipient_office="SPMG",
                objective=(
                    "Research strategy opportunities appropriate to the current Investment "
                    "Mandate and Client constraints. Generate evidence-backed candidates, "
                    "request specialist analysis when useful, and send novel hypotheses to "
                    "ISLL for testing. Do not create live orders."
                ),
            )
            if wid:
                created.append(wid)

        allocation_gap = institutional_state.get("allocation_gap")
        if allocation_gap and allocation_gap.get("material"):
            wid = self._emit(
                mandate_id,
                trigger_type="ALLOCATION_GAP",
                payload=allocation_gap,
                recipient_office="SPMG",
                objective=(
                    "Review the material portfolio allocation gap against the current "
                    "Investment Mandate. Develop alternatives with expected role, evidence, "
                    "risk and implementation constraints; do not execute."
                ),
            )
            if wid:
                created.append(wid)

        risk = institutional_state.get("risk_state", {})
        if risk.get("policy_breach"):
            wid = self._emit(
                mandate_id,
                trigger_type="RISK_POLICY_BREACH",
                payload=risk,
                recipient_office="IPRO",
                objective=(
                    "Independently assess the reported portfolio risk-policy breach, verify "
                    "the deterministic facts, identify immediate constraints and route any "
                    "material exception through formal governance."
                ),
                urgency="HIGH",
            )
            if wid:
                created.append(wid)

        surplus = float(institutional_state.get("new_investable_surplus", 0.0) or 0.0)
        if surplus > 0:
            wid = self._emit(
                mandate_id,
                trigger_type="NEW_INVESTABLE_SURPLUS",
                payload={"amount": surplus},
                recipient_office="SPMG",
                objective=(
                    "Prepare a deployment/reinvestment plan for newly available investable "
                    "surplus under the current Client Mandate. First compare existing "
                    "strategies and allocation gaps; request new research/backtests only "
                    "where coverage is insufficient. Do not execute."
                ),
            )
            if wid:
                created.append(wid)

        performance = institutional_state.get("strategy_performance", {})
        if performance.get("review_required"):
            wid = self._emit(
                mandate_id,
                trigger_type="STRATEGY_REVIEW_REQUIRED",
                payload=performance,
                recipient_office="ISLL",
                objective=(
                    "Review strategy performance and attribution, test whether the original "
                    "hypothesis still holds, search for failure modes, and propose bounded "
                    "experiments or retirement criteria. Do not change production policy."
                ),
            )
            if wid:
                created.append(wid)

        return created
