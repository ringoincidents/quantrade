"""Adapt Investment Office Case learning into existing performance work triggers.

The Investment Office learning capability is currently developed on a separate
main-based branch. This schema-level adapter keeps the institutional runtime
independent while allowing completed Case learning to feed the existing
PerformanceCapitalLoop / AutonomousWorkEngine.

No new trading or policy authority is introduced.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping


class InvestmentOfficeLearningBridgeError(ValueError):
    """Raised when a Case learning artifact is unsafe or malformed."""


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def case_learning_to_strategy_performance_state(
    artifact: object,
) -> dict:
    """Compile Case learning into an existing deterministic work trigger state.

    Review is required when a non-arbitrary structural signal exists:
    - the frozen Thesis was falsified or remains unresolved;
    - forecast hurdle classification disagreed with the realized outcome;
    - realized price escaped the entire frozen scenario-value interval.

    No magnitude threshold is invented here.
    """
    data = _plain(artifact)
    if not isinstance(data, dict):
        raise InvestmentOfficeLearningBridgeError(
            "Case learning artifact must be an object"
        )
    if data.get("schema") != "quantrade_case_learning_v1":
        raise InvestmentOfficeLearningBridgeError(
            "unsupported Case learning schema"
        )

    authority = data.get("authority")
    if not isinstance(authority, dict):
        raise InvestmentOfficeLearningBridgeError(
            "Case learning authority block is required"
        )
    if authority.get("execution_authorized") is not False:
        raise InvestmentOfficeLearningBridgeError(
            "Case learning must remain non-execution-authoritative"
        )
    if authority.get("committee_decision_created") is not False:
        raise InvestmentOfficeLearningBridgeError(
            "Case learning cannot create a Committee decision"
        )
    if authority.get("performance_record_created") is not False:
        raise InvestmentOfficeLearningBridgeError(
            "Case learning must not masquerade as actual performance"
        )

    case_id = str(data.get("case_id") or "").strip()
    if not case_id:
        raise InvestmentOfficeLearningBridgeError(
            "Case learning case_id is required"
        )

    thesis = data.get("thesis_learning")
    calibration = data.get("calibration")
    outcome = data.get("outcome")
    if not isinstance(thesis, dict):
        raise InvestmentOfficeLearningBridgeError(
            "thesis_learning object is required"
        )
    if not isinstance(calibration, dict):
        raise InvestmentOfficeLearningBridgeError(
            "calibration object is required"
        )
    if not isinstance(outcome, dict):
        raise InvestmentOfficeLearningBridgeError(
            "outcome object is required"
        )

    thesis_status = str(thesis.get("status") or "").strip()
    if thesis_status not in {
        "FALSIFIED",
        "UNRESOLVED",
        "NOT_FALSIFIED",
    }:
        raise InvestmentOfficeLearningBridgeError(
            f"unsupported thesis learning status: {thesis_status}"
        )

    forecast_hurdle = calibration.get("forecast_hurdle_met")
    outcome_hurdle = calibration.get("outcome_hurdle_met")
    if not isinstance(forecast_hurdle, bool):
        raise InvestmentOfficeLearningBridgeError(
            "forecast_hurdle_met must be boolean"
        )
    if not isinstance(outcome_hurdle, bool):
        raise InvestmentOfficeLearningBridgeError(
            "outcome_hurdle_met must be boolean"
        )

    interval_contains = outcome.get(
        "scenario_value_interval_contains_realized_price"
    )
    if not isinstance(interval_contains, bool):
        raise InvestmentOfficeLearningBridgeError(
            "scenario interval coverage flag must be boolean"
        )

    reasons: list[str] = []
    if thesis_status == "FALSIFIED":
        reasons.append("THESIS_FALSIFIED")
    elif thesis_status == "UNRESOLVED":
        reasons.append("THESIS_UNRESOLVED")

    if forecast_hurdle != outcome_hurdle:
        reasons.append("RETURN_HURDLE_CLASSIFICATION_MISS")

    if not interval_contains:
        reasons.append("REALIZED_PRICE_OUTSIDE_SCENARIO_VALUE_INTERVAL")

    review_required = bool(reasons)

    return {
        "schema": "quantrade_case_learning_work_trigger_v1",
        "review_required": review_required,
        "strategy_id": case_id,
        "reason": (
            ";".join(reasons)
            if reasons
            else "NO_STRUCTURAL_CASE_LEARNING_TRIGGER"
        ),
        "trigger_reasons": tuple(reasons),
        "thesis_status": thesis_status,
        "return_forecast_error_pct_points": calibration.get(
            "return_forecast_error_pct_points"
        ),
        "return_forecast_absolute_error_pct_points": calibration.get(
            "return_forecast_absolute_error_pct_points"
        ),
        "loss_event_brier_component": calibration.get(
            "loss_event_brier_component"
        ),
        "hurdle_event_brier_component": calibration.get(
            "hurdle_event_brier_component"
        ),
        "counterfactual_excess_vs_benchmark_pct": outcome.get(
            "counterfactual_excess_vs_benchmark_pct"
        ),
        "actual_portfolio_value_added_measured": False,
        "investment_decision_authority": False,
        "execution_authority": False,
    }
