from __future__ import annotations

from typing import Any


def compile_company_strategy(
    *,
    mandate: dict[str, Any],
    client_state: dict[str, Any] | None = None,
    portfolio_state: dict[str, Any] | None = None,
    research_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an internal review directive from explicit client constraints.

    This function does not choose securities, place orders, or increase the
    client's authorized risk. It only describes what internal work should occur.
    """

    client_state = client_state or {}
    portfolio_state = portfolio_state or {}
    research_state = research_state or {}

    liquid_assets = float(client_state.get("liquid_assets") or 0.0)
    reserve = float(
        client_state.get("liquidity_reserve")
        if client_state.get("liquidity_reserve") is not None
        else mandate.get("liquidity_reserve") or 0.0
    )
    urgent_cash_need = float(client_state.get("urgent_cash_need_amount") or 0.0)
    liquidity_shortfall = max(0.0, reserve + urgent_cash_need - liquid_assets)

    planning_conflicts = list(mandate.get("planning_conflicts") or [])
    risk_breach = bool(portfolio_state.get("risk_policy_breach"))
    allocation_gap = bool(portfolio_state.get("material_allocation_gap"))
    material_research = bool(research_state.get("material_update"))
    regime_change = bool(research_state.get("regime_change"))
    new_surplus = float(client_state.get("new_investable_surplus") or 0.0)

    if liquidity_shortfall > 0:
        posture = "LIQUIDITY_FIRST"
        objective = (
            "Protect required liquidity and near-term cash needs before "
            "considering additional market exposure."
        )
        actions = ["PAUSE_NEW_EXPOSURE_REVIEW", "RAISE_CASH_PLAN", "REBALANCE_REVIEW"]
        offices = ["CCO", "SPMG", "IPRO"]
        reasons = ["LIQUIDITY_SHORTFALL"]
    elif planning_conflicts:
        posture = "CLIENT_REVIEW_REQUIRED"
        objective = (
            "Resolve client goal, timeline, contribution, liquidity or risk "
            "conflicts without changing policy silently."
        )
        actions = ["CLIENT_PLAN_REVIEW", "PAUSE_POLICY_CHANGE"]
        offices = ["CCO", "SPMG"]
        reasons = ["CLIENT_PLAN_CONFLICT"]
    elif risk_breach:
        posture = "DEFENSIVE_REVIEW"
        objective = "Restore compliance with the current client mandate."
        actions = ["RISK_REVIEW", "REBALANCE_REVIEW", "PAUSE_NEW_EXPOSURE_REVIEW"]
        offices = ["IPRO", "SPMG"]
        reasons = ["RISK_POLICY_BREACH"]
    elif allocation_gap or material_research or regime_change:
        posture = "REBALANCE_REVIEW"
        objective = (
            "Reassess portfolio allocation against the current mandate using "
            "new research and market evidence."
        )
        actions = ["RESEARCH", "REBALANCE_REVIEW"]
        offices = ["SPMG", "IPRO"]
        reasons = []
        if allocation_gap:
            reasons.append("MATERIAL_ALLOCATION_GAP")
        if material_research:
            reasons.append("MATERIAL_RESEARCH_UPDATE")
        if regime_change:
            reasons.append("RESEARCH_REGIME_CHANGE")
    elif new_surplus > 0:
        posture = "DEPLOYMENT_REVIEW"
        objective = (
            "Evaluate how new investable capital should be allocated under the "
            "existing liquidity and drawdown constraints."
        )
        actions = ["RESEARCH", "CAPITAL_DEPLOYMENT_PLAN"]
        offices = ["SPMG"]
        reasons = ["NEW_INVESTABLE_SURPLUS"]
    else:
        posture = "MAINTAIN"
        objective = "Maintain the current mandate and monitor material changes."
        actions = ["MAINTAIN_AND_MONITOR"]
        offices = ["SPMG"]
        reasons = ["MANDATE_STABLE"]

    return {
        "schema": "quantrade_strategy_directive_v1",
        "posture": posture,
        "objective": objective,
        "actions": actions,
        "reasons": reasons,
        "required_offices": offices,
        "liquidity_shortfall": liquidity_shortfall,
        "investable_capital": mandate.get("investable_capital"),
        "required_return_pct": mandate.get("required_return_pct"),
        "max_drawdown_pct": mandate.get("max_drawdown_pct"),
        "human_approval_required_for_live_execution": True,
        "execution_authority": False,
        "policy_note": (
            "Difficult client goals never authorize automatic risk escalation. "
            "Conflicts are routed to review."
        ),
    }
