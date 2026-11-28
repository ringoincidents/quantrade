"""Deterministic Investment Case economics for QuanTrade.

This module converts explicit scenario assumptions into arithmetic. It does not
decide whether the assumptions are true and it does not create Evidence,
Portfolio proposals, Risk opinions, Committee decisions, PAPER authority, or
execution authority.

The capability is intentionally dependency-free and model-free.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from typing import Sequence


class InvestmentCaseError(ValueError):
    """Raised when an Investment Case violates deterministic input contracts."""


@dataclass(frozen=True)
class ScenarioAssumption:
    scenario_id: str
    label: str
    probability: float
    fair_value: float
    thesis_note: str = ""
    evidence_refs: tuple[str, ...] = ()
    assumption_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConsensusObservation:
    source_id: str
    observed_at: str
    target_value: float
    currency: str
    horizon_days: int | None = None
    methodology_note: str = ""


@dataclass(frozen=True)
class InvestmentCaseInput:
    case_id: str
    asset_id: str
    as_of: str
    current_price: float
    currency: str
    valuation_horizon_days: int
    required_return_pct: float
    scenarios: tuple[ScenarioAssumption, ...]
    consensus: ConsensusObservation | None = None


@dataclass(frozen=True)
class InvestmentCaseEconomics:
    schema: str
    case: dict
    scenarios: tuple[dict, ...]
    metrics: dict
    consensus_comparison: dict | None
    validation: dict
    authority: dict


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise InvestmentCaseError("timestamp must be a non-empty ISO-8601 string")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InvestmentCaseError(
            f"invalid ISO-8601 timestamp: {value}"
        ) from exc
    if parsed.tzinfo is None:
        raise InvestmentCaseError(
            "timestamp must include timezone information"
        )
    return parsed.astimezone(timezone.utc)


def _finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvestmentCaseError(f"{field_name} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise InvestmentCaseError(f"{field_name} must be finite")
    return numeric


def _validate_consensus(
    consensus: ConsensusObservation,
    case_currency: str,
    case_as_of: datetime,
) -> None:
    if not consensus.source_id.strip():
        raise InvestmentCaseError("consensus source_id is required")
    if not consensus.currency.strip():
        raise InvestmentCaseError("consensus currency is required")
    if consensus.currency != case_currency:
        raise InvestmentCaseError(
            "consensus currency must match Investment Case currency"
        )
    observed_at = _parse_time(consensus.observed_at)
    if observed_at > case_as_of:
        raise InvestmentCaseError(
            "consensus observation cannot be from after case as_of"
        )
    target = _finite_number(
        consensus.target_value,
        "consensus target_value",
    )
    if target <= 0:
        raise InvestmentCaseError(
            "consensus target_value must be positive"
        )
    if consensus.horizon_days is not None and consensus.horizon_days <= 0:
        raise InvestmentCaseError(
            "consensus horizon_days must be positive when provided"
        )


def _validate_case(
    case: InvestmentCaseInput,
    probability_tolerance: float,
) -> tuple[float, datetime]:
    for field_name, value in (
        ("case_id", case.case_id),
        ("asset_id", case.asset_id),
        ("currency", case.currency),
    ):
        if not isinstance(value, str) or not value.strip():
            raise InvestmentCaseError(f"{field_name} is required")

    case_as_of = _parse_time(case.as_of)
    current_price = _finite_number(case.current_price, "current_price")
    if current_price <= 0:
        raise InvestmentCaseError("current_price must be positive")
    if case.valuation_horizon_days <= 0:
        raise InvestmentCaseError(
            "valuation_horizon_days must be positive"
        )
    required_return = _finite_number(
        case.required_return_pct,
        "required_return_pct",
    )
    if required_return <= -100.0:
        raise InvestmentCaseError(
            "required_return_pct must be greater than -100"
        )
    if not case.scenarios:
        raise InvestmentCaseError("at least one scenario is required")

    ids: set[str] = set()
    probability_sum = 0.0
    for scenario in case.scenarios:
        if not scenario.scenario_id.strip():
            raise InvestmentCaseError("scenario_id is required")
        if scenario.scenario_id in ids:
            raise InvestmentCaseError(
                f"duplicate scenario_id: {scenario.scenario_id}"
            )
        ids.add(scenario.scenario_id)
        if not scenario.label.strip():
            raise InvestmentCaseError("scenario label is required")

        probability = _finite_number(
            scenario.probability,
            f"{scenario.scenario_id}.probability",
        )
        if probability < 0.0 or probability > 1.0:
            raise InvestmentCaseError(
                "scenario probability must be between 0 and 1"
            )
        probability_sum += probability

        fair_value = _finite_number(
            scenario.fair_value,
            f"{scenario.scenario_id}.fair_value",
        )
        if fair_value <= 0:
            raise InvestmentCaseError(
                "scenario fair_value must be positive"
            )

        for ref in scenario.evidence_refs + scenario.assumption_refs:
            if not isinstance(ref, str) or not ref.strip():
                raise InvestmentCaseError(
                    "scenario refs must be non-empty strings"
                )

    if abs(probability_sum - 1.0) > probability_tolerance:
        raise InvestmentCaseError(
            "scenario probabilities must sum to 1 within tolerance"
        )

    if case.consensus is not None:
        _validate_consensus(
            case.consensus,
            case.currency,
            case_as_of,
        )

    return current_price, case_as_of


def evaluate_investment_case(
    case: InvestmentCaseInput,
    *,
    probability_tolerance: float = 1e-6,
) -> InvestmentCaseEconomics:
    """Calculate Investment Case economics from explicit assumptions.

    Arithmetic correctness is not evidence that scenario assumptions are true.
    """
    if probability_tolerance <= 0:
        raise InvestmentCaseError(
            "probability_tolerance must be positive"
        )
    current_price, _ = _validate_case(
        case,
        probability_tolerance,
    )

    weighted_fair_value = sum(
        scenario.probability * scenario.fair_value
        for scenario in case.scenarios
    )
    expected_return_pct = (
        weighted_fair_value / current_price - 1.0
    ) * 100.0

    scenario_rows = []
    loss_probability = 0.0
    hurdle_probability = 0.0
    fair_values = []
    for scenario in case.scenarios:
        scenario_return_pct = (
            scenario.fair_value / current_price - 1.0
        ) * 100.0
        if scenario.fair_value < current_price:
            loss_probability += scenario.probability
        if scenario_return_pct >= case.required_return_pct:
            hurdle_probability += scenario.probability
        fair_values.append(float(scenario.fair_value))
        scenario_rows.append(
            {
                **asdict(scenario),
                "scenario_return_pct": round(
                    scenario_return_pct,
                    6,
                ),
                "input_kind": "ASSUMPTION",
                "investment_authority": False,
            }
        )

    variance = sum(
        scenario.probability
        * (scenario.fair_value - weighted_fair_value) ** 2
        for scenario in case.scenarios
    )
    fair_value_std = math.sqrt(variance)
    dispersion_pct_of_current = (
        fair_value_std / current_price * 100.0
    )

    lowest = min(fair_values)
    highest = max(fair_values)
    downside_pct = (lowest / current_price - 1.0) * 100.0
    upside_pct = (highest / current_price - 1.0) * 100.0
    expected_excess_hurdle_pct = (
        expected_return_pct - case.required_return_pct
    )

    metrics = {
        "weighted_fair_value": round(weighted_fair_value, 6),
        "expected_return_pct": round(expected_return_pct, 6),
        "required_return_pct": round(case.required_return_pct, 6),
        "expected_excess_over_hurdle_pct": round(
            expected_excess_hurdle_pct,
            6,
        ),
        "expected_return_hurdle_met": (
            expected_return_pct >= case.required_return_pct
        ),
        "lowest_scenario_fair_value": round(lowest, 6),
        "highest_scenario_fair_value": round(highest, 6),
        "lowest_scenario_return_pct": round(downside_pct, 6),
        "highest_scenario_return_pct": round(upside_pct, 6),
        "probability_of_price_loss": round(loss_probability, 6),
        "probability_of_meeting_return_hurdle": round(
            hurdle_probability,
            6,
        ),
        "fair_value_std": round(fair_value_std, 6),
        "scenario_dispersion_pct_of_current": round(
            dispersion_pct_of_current,
            6,
        ),
    }

    consensus_comparison = None
    if case.consensus is not None:
        consensus_target = float(case.consensus.target_value)
        consensus_comparison = {
            "observation": asdict(case.consensus),
            "observation_kind": "EXTERNAL_OBSERVATION",
            "current_to_consensus_return_pct": round(
                (consensus_target / current_price - 1.0) * 100.0,
                6,
            ),
            "internal_weighted_value_vs_consensus_pct": round(
                (
                    weighted_fair_value / consensus_target - 1.0
                ) * 100.0,
                6,
            ),
            "consensus_used_to_compute_internal_weighted_value": False,
            "investment_authority": False,
        }

    return InvestmentCaseEconomics(
        schema="quantrade_investment_case_economics_v1",
        case={
            "case_id": case.case_id,
            "asset_id": case.asset_id,
            "as_of": case.as_of,
            "current_price": case.current_price,
            "currency": case.currency,
            "valuation_horizon_days": case.valuation_horizon_days,
            "required_return_pct": case.required_return_pct,
            "scenario_count": len(case.scenarios),
        },
        scenarios=tuple(scenario_rows),
        metrics=metrics,
        consensus_comparison=consensus_comparison,
        validation={
            "probability_sum": round(
                sum(s.probability for s in case.scenarios),
                12,
            ),
            "probability_tolerance": probability_tolerance,
            "scenario_ids_unique": True,
            "fair_values_positive": True,
            "current_price_positive": True,
            "currency_explicit": True,
            "valuation_horizon_explicit": True,
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
            "risk_limit_changed": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )
