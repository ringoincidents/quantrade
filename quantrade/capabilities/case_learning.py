"""Deterministic Investment Case learning and calibration.

This module evaluates whether a previously frozen Investment Case forecast was
well calibrated after a later, source-backed outcome becomes observable.

It is deliberately separate from actual portfolio P&L accounting. Existing
institutional PerformanceCapitalLoop owns realized Client capital performance.

This capability evaluates:
- forecast return error;
- loss-event calibration;
- return-hurdle calibration;
- counterfactual benchmark-relative return;
- Thesis falsification outcomes.

It does not create a new investment decision, Portfolio proposal, Risk Opinion,
PAPER authority, or execution side effect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import math
from statistics import mean
from typing import Iterable

from quantrade.capabilities.investment_case import InvestmentCaseEconomics


class CaseLearningError(ValueError):
    """Raised when learning inputs violate the frozen-outcome contract."""


class FalsificationStatus(str, Enum):
    TRIGGERED = "TRIGGERED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class FalsificationResult:
    condition_id: str
    status: str
    observed_at: str
    source_refs: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class OutcomeSnapshot:
    case_id: str
    evaluated_at: str
    realized_price: float
    benchmark_return_pct: float
    outcome_refs: tuple[str, ...]


@dataclass(frozen=True)
class CaseLearningInput:
    case_economics: InvestmentCaseEconomics
    thesis_contract: dict
    outcome: OutcomeSnapshot
    falsification_results: tuple[FalsificationResult, ...]


@dataclass(frozen=True)
class CaseLearningArtifact:
    schema: str
    case_id: str
    forecast: dict
    outcome: dict
    calibration: dict
    thesis_learning: dict
    authority: dict


@dataclass(frozen=True)
class CaseCalibrationAggregate:
    schema: str
    sample_count: int
    metrics: dict
    authority: dict


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CaseLearningError(f"{field_name} is required")
    return value.strip()


def _parse_time(value: str, field_name: str) -> datetime:
    raw = _required_text(value, field_name).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CaseLearningError(
            f"{field_name} must be valid ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise CaseLearningError(
            f"{field_name} must include timezone information"
        )
    return parsed.astimezone(timezone.utc)


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CaseLearningError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise CaseLearningError(f"{field_name} must be finite")
    return number


def _refs(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    items = tuple(values)
    for item in items:
        _required_text(item, field_name)
    return items


def _thesis_condition_ids(thesis_contract: dict) -> tuple[str, ...]:
    if thesis_contract.get("schema") != "quantrade_thesis_contract_v1":
        raise CaseLearningError(
            "thesis_contract schema must be quantrade_thesis_contract_v1"
        )
    authority = thesis_contract.get("authority")
    if not isinstance(authority, dict):
        raise CaseLearningError("thesis_contract authority is required")
    if authority.get("thesis_truth_validated") is not False:
        raise CaseLearningError(
            "thesis_contract must remain non-truth-authoritative"
        )
    if authority.get("execution_authorized") is not False:
        raise CaseLearningError(
            "thesis_contract must remain non-execution-authoritative"
        )

    nodes = thesis_contract.get("nodes")
    if not isinstance(nodes, dict):
        raise CaseLearningError("thesis_contract nodes are required")
    rows = nodes.get("falsification_conditions")
    if not isinstance(rows, (list, tuple)):
        raise CaseLearningError(
            "thesis_contract falsification_conditions must be a list"
        )
    ids = tuple(
        _required_text(row.get("condition_id"), "condition_id")
        for row in rows
        if isinstance(row, dict)
    )
    if len(ids) != len(rows):
        raise CaseLearningError(
            "every falsification condition must be an object"
        )
    if len(ids) != len(set(ids)):
        raise CaseLearningError(
            "falsification condition IDs must be unique"
        )
    return ids


def _validate_economics(
    economics: InvestmentCaseEconomics,
) -> tuple[datetime, float]:
    if economics.schema != "quantrade_investment_case_economics_v1":
        raise CaseLearningError(
            "unsupported Investment Case economics schema"
        )
    if economics.authority.get("execution_authorized") is not False:
        raise CaseLearningError(
            "case economics must remain non-execution-authoritative"
        )
    case_id = _required_text(
        economics.case.get("case_id"),
        "case economics case_id",
    )
    _ = case_id
    case_as_of = _parse_time(
        economics.case.get("as_of"),
        "case economics as_of",
    )
    entry_price = _finite(
        economics.case.get("current_price"),
        "case current_price",
    )
    if entry_price <= 0.0:
        raise CaseLearningError("case current_price must be positive")
    return case_as_of, entry_price


def evaluate_case_learning(
    request: CaseLearningInput,
) -> CaseLearningArtifact:
    """Evaluate one frozen Case forecast against a later realized outcome."""
    economics = request.case_economics
    case_as_of, entry_price = _validate_economics(economics)
    case_id = str(economics.case["case_id"])

    if request.thesis_contract.get("case_id") != case_id:
        raise CaseLearningError(
            "thesis_contract case_id must match case economics"
        )
    if request.outcome.case_id != case_id:
        raise CaseLearningError(
            "outcome case_id must match case economics"
        )

    outcome_time = _parse_time(
        request.outcome.evaluated_at,
        "outcome evaluated_at",
    )
    if outcome_time <= case_as_of:
        raise CaseLearningError(
            "outcome evaluated_at must be after case as_of"
        )

    realized_price = _finite(
        request.outcome.realized_price,
        "realized_price",
    )
    if realized_price <= 0.0:
        raise CaseLearningError("realized_price must be positive")
    benchmark_return_pct = _finite(
        request.outcome.benchmark_return_pct,
        "benchmark_return_pct",
    )
    if benchmark_return_pct <= -100.0:
        raise CaseLearningError(
            "benchmark_return_pct must be greater than -100"
        )
    outcome_refs = _refs(
        request.outcome.outcome_refs,
        "outcome_ref",
    )
    if not outcome_refs:
        raise CaseLearningError(
            "outcome requires at least one source reference"
        )

    condition_ids = _thesis_condition_ids(
        request.thesis_contract
    )
    result_map: dict[str, FalsificationResult] = {}
    for result in request.falsification_results:
        condition_id = _required_text(
            result.condition_id,
            "falsification result condition_id",
        )
        if condition_id in result_map:
            raise CaseLearningError(
                f"duplicate falsification result: {condition_id}"
            )
        try:
            FalsificationStatus(result.status)
        except ValueError as exc:
            raise CaseLearningError(
                f"unsupported falsification status: {result.status}"
            ) from exc
        observed = _parse_time(
            result.observed_at,
            "falsification observed_at",
        )
        if observed > outcome_time:
            raise CaseLearningError(
                "falsification observation cannot be after outcome "
                f"evaluation: {condition_id}"
            )
        refs = _refs(
            result.source_refs,
            "falsification source_ref",
        )
        if (
            result.status != FalsificationStatus.UNRESOLVED.value
            and not refs
        ):
            raise CaseLearningError(
                "resolved falsification result requires source_refs"
            )
        result_map[condition_id] = result

    missing = [
        condition_id
        for condition_id in condition_ids
        if condition_id not in result_map
    ]
    extras = [
        condition_id
        for condition_id in result_map
        if condition_id not in set(condition_ids)
    ]
    if missing:
        raise CaseLearningError(
            "missing falsification results: " + ", ".join(missing)
        )
    if extras:
        raise CaseLearningError(
            "unknown falsification results: " + ", ".join(extras)
        )

    expected_return = _finite(
        economics.metrics.get("expected_return_pct"),
        "expected_return_pct",
    )
    required_return = _finite(
        economics.metrics.get("required_return_pct"),
        "required_return_pct",
    )
    predicted_loss_probability = _finite(
        economics.metrics.get("probability_of_price_loss"),
        "probability_of_price_loss",
    )
    predicted_hurdle_probability = _finite(
        economics.metrics.get("probability_of_meeting_return_hurdle"),
        "probability_of_meeting_return_hurdle",
    )
    for field_name, value in (
        ("probability_of_price_loss", predicted_loss_probability),
        (
            "probability_of_meeting_return_hurdle",
            predicted_hurdle_probability,
        ),
    ):
        if value < 0.0 or value > 1.0:
            raise CaseLearningError(
                f"{field_name} must be between 0 and 1"
            )

    weighted_fair_value = _finite(
        economics.metrics.get("weighted_fair_value"),
        "weighted_fair_value",
    )
    lowest_fair_value = _finite(
        economics.metrics.get("lowest_scenario_fair_value"),
        "lowest_scenario_fair_value",
    )
    highest_fair_value = _finite(
        economics.metrics.get("highest_scenario_fair_value"),
        "highest_scenario_fair_value",
    )

    realized_return = (
        realized_price / entry_price - 1.0
    ) * 100.0
    forecast_error = realized_return - expected_return
    fair_value_error_pct_of_entry = (
        realized_price - weighted_fair_value
    ) / entry_price * 100.0
    counterfactual_excess = (
        realized_return - benchmark_return_pct
    )

    actual_loss = 1.0 if realized_price < entry_price else 0.0
    actual_hurdle = (
        1.0 if realized_return >= required_return else 0.0
    )
    loss_brier = (
        predicted_loss_probability - actual_loss
    ) ** 2
    hurdle_brier = (
        predicted_hurdle_probability - actual_hurdle
    ) ** 2

    triggered = [
        condition_id
        for condition_id, result in result_map.items()
        if result.status == FalsificationStatus.TRIGGERED.value
    ]
    unresolved = [
        condition_id
        for condition_id, result in result_map.items()
        if result.status == FalsificationStatus.UNRESOLVED.value
    ]
    if triggered:
        thesis_status = "FALSIFIED"
    elif unresolved:
        thesis_status = "UNRESOLVED"
    else:
        thesis_status = "NOT_FALSIFIED"

    falsification_rows = tuple(
        asdict(result_map[condition_id])
        for condition_id in condition_ids
    )

    return CaseLearningArtifact(
        schema="quantrade_case_learning_v1",
        case_id=case_id,
        forecast={
            "case_as_of": economics.case["as_of"],
            "entry_price": entry_price,
            "weighted_fair_value": weighted_fair_value,
            "expected_return_pct": expected_return,
            "required_return_pct": required_return,
            "predicted_loss_probability": predicted_loss_probability,
            "predicted_hurdle_probability": predicted_hurdle_probability,
            "lowest_scenario_fair_value": lowest_fair_value,
            "highest_scenario_fair_value": highest_fair_value,
        },
        outcome={
            "evaluated_at": request.outcome.evaluated_at,
            "realized_price": realized_price,
            "realized_return_pct": round(realized_return, 6),
            "benchmark_return_pct": round(
                benchmark_return_pct,
                6,
            ),
            "counterfactual_excess_vs_benchmark_pct": round(
                counterfactual_excess,
                6,
            ),
            "outcome_refs": outcome_refs,
            "scenario_value_interval_contains_realized_price": (
                lowest_fair_value
                <= realized_price
                <= highest_fair_value
            ),
        },
        calibration={
            "return_forecast_error_pct_points": round(
                forecast_error,
                6,
            ),
            "return_forecast_absolute_error_pct_points": round(
                abs(forecast_error),
                6,
            ),
            "weighted_fair_value_error_pct_of_entry": round(
                fair_value_error_pct_of_entry,
                6,
            ),
            "actual_loss_indicator": int(actual_loss),
            "loss_event_brier_component": round(
                loss_brier,
                8,
            ),
            "actual_hurdle_indicator": int(actual_hurdle),
            "hurdle_event_brier_component": round(
                hurdle_brier,
                8,
            ),
            "forecast_hurdle_met": bool(
                economics.metrics.get(
                    "expected_return_hurdle_met"
                )
            ),
            "outcome_hurdle_met": bool(actual_hurdle),
            "single_case_proves_alpha": False,
        },
        thesis_learning={
            "status": thesis_status,
            "triggered_condition_ids": tuple(triggered),
            "unresolved_condition_ids": tuple(unresolved),
            "falsification_results": falsification_rows,
            "thesis_truth_proven": False,
        },
        authority={
            "model_called": False,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "performance_record_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )


def aggregate_case_calibration(
    artifacts: Iterable[CaseLearningArtifact],
) -> CaseCalibrationAggregate:
    """Aggregate calibration across multiple already-completed Cases.

    This is not portfolio performance attribution and not a statistical
    significance claim. It creates descriptive learning metrics only.
    """
    rows = tuple(artifacts)
    if not rows:
        raise CaseLearningError(
            "at least one CaseLearningArtifact is required"
        )
    for row in rows:
        if row.schema != "quantrade_case_learning_v1":
            raise CaseLearningError(
                "unsupported CaseLearningArtifact schema"
            )
        if row.authority.get("execution_authorized") is not False:
            raise CaseLearningError(
                "learning artifact must be non-execution-authoritative"
            )

    errors = [
        float(
            row.calibration[
                "return_forecast_error_pct_points"
            ]
        )
        for row in rows
    ]
    abs_errors = [
        float(
            row.calibration[
                "return_forecast_absolute_error_pct_points"
            ]
        )
        for row in rows
    ]
    loss_briers = [
        float(
            row.calibration["loss_event_brier_component"]
        )
        for row in rows
    ]
    hurdle_briers = [
        float(
            row.calibration["hurdle_event_brier_component"]
        )
        for row in rows
    ]
    counterfactual_excess = [
        float(
            row.outcome[
                "counterfactual_excess_vs_benchmark_pct"
            ]
        )
        for row in rows
    ]
    falsified_count = sum(
        1
        for row in rows
        if row.thesis_learning["status"] == "FALSIFIED"
    )
    unresolved_count = sum(
        1
        for row in rows
        if row.thesis_learning["status"] == "UNRESOLVED"
    )

    return CaseCalibrationAggregate(
        schema="quantrade_case_calibration_aggregate_v1",
        sample_count=len(rows),
        metrics={
            "mean_return_forecast_error_pct_points": round(
                mean(errors),
                6,
            ),
            "mean_absolute_return_forecast_error_pct_points": round(
                mean(abs_errors),
                6,
            ),
            "mean_loss_event_brier_score": round(
                mean(loss_briers),
                8,
            ),
            "mean_hurdle_event_brier_score": round(
                mean(hurdle_briers),
                8,
            ),
            "mean_counterfactual_excess_vs_benchmark_pct": round(
                mean(counterfactual_excess),
                6,
            ),
            "falsified_case_count": falsified_count,
            "unresolved_case_count": unresolved_count,
            "statistical_significance_established": False,
            "actual_portfolio_value_added_measured": False,
        },
        authority={
            "model_called": False,
            "investment_decision_created": False,
            "portfolio_proposal_created": False,
            "risk_limit_changed": False,
            "execution_authorized": False,
        },
    )
