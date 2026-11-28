"""Deterministic per-share cash-flow DCF for QuanTrade Investment Cases.

This capability converts an explicitly supplied owner-cash-flow-per-share
anchor and frozen scenario assumptions into arithmetic.

It does not decide whether the cash-flow proxy is economically correct and it
does not create Evidence, a Thesis, Portfolio Proposal, Risk Opinion, Committee
Decision, PAPER authority, or execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math


class CashFlowValuationError(ValueError):
    """Raised when a cash-flow valuation input violates the contract."""


@dataclass(frozen=True)
class CashFlowDCFScenario:
    scenario_id: str
    label: str
    probability: float
    starting_cash_flow_factor: float
    explicit_growth_pct: float
    terminal_growth_pct: float
    discount_rate_pct: float
    explicit_years: int = 5
    assumption_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CashFlowDCFInput:
    case_id: str
    asset_id: str
    as_of: str
    current_price: float
    currency: str
    owner_cash_flow_per_share: float
    required_return_pct: float
    scenarios: tuple[CashFlowDCFScenario, ...]


@dataclass(frozen=True)
class CashFlowDCFArtifact:
    schema: str
    case: dict
    scenarios: tuple[dict, ...]
    metrics: dict
    validation: dict
    authority: dict


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CashFlowValuationError(f"{field_name} is required")
    return value.strip()


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CashFlowValuationError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise CashFlowValuationError(f"{field_name} must be finite")
    return number


def _scenario_value(
    base_cash_flow_per_share: float,
    scenario: CashFlowDCFScenario,
) -> dict:
    _text(scenario.scenario_id, "scenario_id")
    _text(scenario.label, "scenario label")

    probability = _finite(
        scenario.probability,
        f"{scenario.scenario_id}.probability",
    )
    if probability < 0.0 or probability > 1.0:
        raise CashFlowValuationError(
            "scenario probability must be between 0 and 1"
        )

    starting_factor = _finite(
        scenario.starting_cash_flow_factor,
        f"{scenario.scenario_id}.starting_cash_flow_factor",
    )
    if starting_factor <= 0.0:
        raise CashFlowValuationError(
            "starting_cash_flow_factor must be positive"
        )

    explicit_growth = _finite(
        scenario.explicit_growth_pct,
        f"{scenario.scenario_id}.explicit_growth_pct",
    ) / 100.0
    terminal_growth = _finite(
        scenario.terminal_growth_pct,
        f"{scenario.scenario_id}.terminal_growth_pct",
    ) / 100.0
    discount_rate = _finite(
        scenario.discount_rate_pct,
        f"{scenario.scenario_id}.discount_rate_pct",
    ) / 100.0

    if scenario.explicit_years < 1:
        raise CashFlowValuationError(
            "explicit_years must be positive"
        )
    if discount_rate <= terminal_growth:
        raise CashFlowValuationError(
            "discount_rate must exceed terminal_growth"
        )
    if discount_rate <= -1.0:
        raise CashFlowValuationError(
            "discount_rate must be greater than -100%"
        )
    if explicit_growth <= -1.0 or terminal_growth <= -1.0:
        raise CashFlowValuationError(
            "growth rates must be greater than -100%"
        )

    starting_cash_flow = (
        base_cash_flow_per_share * starting_factor
    )
    if starting_cash_flow <= 0.0:
        raise CashFlowValuationError(
            "scenario starting cash flow must be positive"
        )

    cash_flows: list[float] = []
    present_values: list[float] = []
    current = starting_cash_flow
    for year in range(1, scenario.explicit_years + 1):
        current = current * (1.0 + explicit_growth)
        cash_flows.append(current)
        present_values.append(
            current / ((1.0 + discount_rate) ** year)
        )

    terminal_value = (
        cash_flows[-1]
        * (1.0 + terminal_growth)
        / (discount_rate - terminal_growth)
    )
    terminal_present_value = (
        terminal_value
        / ((1.0 + discount_rate) ** scenario.explicit_years)
    )
    fair_value = sum(present_values) + terminal_present_value

    return {
        **asdict(scenario),
        "starting_cash_flow_per_share": round(
            starting_cash_flow,
            8,
        ),
        "explicit_cash_flows_per_share": tuple(
            round(value, 8) for value in cash_flows
        ),
        "explicit_present_values_per_share": tuple(
            round(value, 8) for value in present_values
        ),
        "terminal_value_per_share": round(
            terminal_value,
            8,
        ),
        "terminal_present_value_per_share": round(
            terminal_present_value,
            8,
        ),
        "fair_value": round(fair_value, 8),
        "input_kind": "ASSUMPTION",
        "investment_authority": False,
    }


def evaluate_cash_flow_dcf(
    request: CashFlowDCFInput,
    *,
    probability_tolerance: float = 1e-6,
) -> CashFlowDCFArtifact:
    """Calculate frozen scenario DCF arithmetic."""
    _text(request.case_id, "case_id")
    _text(request.asset_id, "asset_id")
    _text(request.as_of, "as_of")
    _text(request.currency, "currency")

    current_price = _finite(
        request.current_price,
        "current_price",
    )
    if current_price <= 0.0:
        raise CashFlowValuationError(
            "current_price must be positive"
        )

    base_cash_flow = _finite(
        request.owner_cash_flow_per_share,
        "owner_cash_flow_per_share",
    )
    if base_cash_flow <= 0.0:
        raise CashFlowValuationError(
            "owner_cash_flow_per_share must be positive"
        )

    required_return = _finite(
        request.required_return_pct,
        "required_return_pct",
    )
    if required_return <= -100.0:
        raise CashFlowValuationError(
            "required_return_pct must be greater than -100%"
        )

    if not request.scenarios:
        raise CashFlowValuationError(
            "at least one DCF scenario is required"
        )

    ids: set[str] = set()
    rows: list[dict] = []
    probability_sum = 0.0
    for scenario in request.scenarios:
        if scenario.scenario_id in ids:
            raise CashFlowValuationError(
                f"duplicate scenario_id: {scenario.scenario_id}"
            )
        ids.add(scenario.scenario_id)
        row = _scenario_value(base_cash_flow, scenario)
        probability_sum += float(scenario.probability)
        row["scenario_return_pct"] = round(
            (
                float(row["fair_value"]) / current_price - 1.0
            ) * 100.0,
            6,
        )
        rows.append(row)

    if abs(probability_sum - 1.0) > probability_tolerance:
        raise CashFlowValuationError(
            "scenario probabilities must sum to 1"
        )

    weighted_value = sum(
        scenario.probability * float(row["fair_value"])
        for scenario, row in zip(request.scenarios, rows)
    )
    expected_return = (
        weighted_value / current_price - 1.0
    ) * 100.0
    loss_probability = sum(
        scenario.probability
        for scenario, row in zip(request.scenarios, rows)
        if float(row["fair_value"]) < current_price
    )
    hurdle_probability = sum(
        scenario.probability
        for scenario, row in zip(request.scenarios, rows)
        if float(row["scenario_return_pct"]) >= required_return
    )

    values = [float(row["fair_value"]) for row in rows]
    variance = sum(
        scenario.probability
        * (float(row["fair_value"]) - weighted_value) ** 2
        for scenario, row in zip(request.scenarios, rows)
    )

    return CashFlowDCFArtifact(
        schema="quantrade_cash_flow_dcf_v1",
        case={
            "case_id": request.case_id,
            "asset_id": request.asset_id,
            "as_of": request.as_of,
            "current_price": current_price,
            "currency": request.currency,
            "owner_cash_flow_per_share": base_cash_flow,
            "required_return_pct": required_return,
            "scenario_count": len(rows),
        },
        scenarios=tuple(rows),
        metrics={
            "weighted_fair_value": round(
                weighted_value,
                6,
            ),
            "expected_return_pct": round(
                expected_return,
                6,
            ),
            "required_return_pct": round(
                required_return,
                6,
            ),
            "expected_excess_over_hurdle_pct": round(
                expected_return - required_return,
                6,
            ),
            "expected_return_hurdle_met": (
                expected_return >= required_return
            ),
            "lowest_scenario_fair_value": round(
                min(values),
                6,
            ),
            "highest_scenario_fair_value": round(
                max(values),
                6,
            ),
            "lowest_scenario_return_pct": round(
                (min(values) / current_price - 1.0) * 100.0,
                6,
            ),
            "highest_scenario_return_pct": round(
                (max(values) / current_price - 1.0) * 100.0,
                6,
            ),
            "probability_of_price_loss": round(
                loss_probability,
                6,
            ),
            "probability_of_meeting_return_hurdle": round(
                hurdle_probability,
                6,
            ),
            "fair_value_std": round(
                math.sqrt(variance),
                6,
            ),
        },
        validation={
            "probability_sum": round(
                probability_sum,
                12,
            ),
            "probability_tolerance": probability_tolerance,
            "scenario_ids_unique": True,
            "cash_flow_positive": True,
            "discount_rate_exceeds_terminal_growth": True,
            "arithmetic_only": True,
            "assumptions_validated_as_true": False,
        },
        authority={
            "model_called": False,
            "canonical_evidence_created": False,
            "thesis_validated": False,
            "portfolio_proposal_created": False,
            "position_size_set": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )
