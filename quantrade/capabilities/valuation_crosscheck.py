"""Cross-method valuation robustness for QuanTrade Investment Cases.

This capability compares independently produced valuation methods without
granting any method capital authority.

It enforces:
- same Case price / required-return hurdle;
- same scenario IDs and probabilities;
- per-scenario conservative lower-of-methods aggregation;
- explicit CONFIRMED / MIXED / REJECTED classification.

It is designed for future methods such as P/E, DCF, DDM, residual income, or
sum-of-parts. It does not create a Portfolio Proposal or investment decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math


class ValuationCrossCheckError(ValueError):
    """Raised when valuation methods cannot be compared safely."""


@dataclass(frozen=True)
class ValuationScenarioSnapshot:
    scenario_id: str
    probability: float
    fair_value: float


@dataclass(frozen=True)
class ValuationMethodSnapshot:
    method_id: str
    method_type: str
    source_schema: str
    current_price: float
    required_return_pct: float
    scenarios: tuple[ValuationScenarioSnapshot, ...]
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValuationCrossCheckInput:
    case_id: str
    methods: tuple[ValuationMethodSnapshot, ...]


@dataclass(frozen=True)
class ValuationCrossCheckArtifact:
    schema: str
    case_id: str
    classification: str
    method_summaries: tuple[dict, ...]
    robust_scenarios: tuple[dict, ...]
    robust_metrics: dict
    validation: dict
    authority: dict


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValuationCrossCheckError(f"{field_name} is required")
    return value.strip()


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValuationCrossCheckError(
            f"{field_name} must be numeric"
        )
    number = float(value)
    if not math.isfinite(number):
        raise ValuationCrossCheckError(
            f"{field_name} must be finite"
        )
    return number


def evaluate_valuation_crosscheck(
    request: ValuationCrossCheckInput,
    *,
    probability_tolerance: float = 1e-6,
    numeric_tolerance: float = 1e-6,
) -> ValuationCrossCheckArtifact:
    _text(request.case_id, "case_id")
    if len(request.methods) < 2:
        raise ValuationCrossCheckError(
            "at least two valuation methods are required"
        )

    method_ids: set[str] = set()
    method_maps: list[dict[str, ValuationScenarioSnapshot]] = []
    method_summaries: list[dict] = []

    first_price: float | None = None
    first_hurdle: float | None = None
    first_ids: tuple[str, ...] | None = None
    first_probabilities: dict[str, float] | None = None

    for method in request.methods:
        method_id = _text(method.method_id, "method_id")
        if method_id in method_ids:
            raise ValuationCrossCheckError(
                f"duplicate method_id: {method_id}"
            )
        method_ids.add(method_id)
        _text(method.method_type, "method_type")
        _text(method.source_schema, "source_schema")
        price = _finite(method.current_price, "current_price")
        if price <= 0.0:
            raise ValuationCrossCheckError(
                "current_price must be positive"
            )
        hurdle = _finite(
            method.required_return_pct,
            "required_return_pct",
        )

        if first_price is None:
            first_price = price
            first_hurdle = hurdle
        else:
            assert first_hurdle is not None
            if abs(price - first_price) > numeric_tolerance:
                raise ValuationCrossCheckError(
                    "valuation methods must share current_price"
                )
            if abs(hurdle - first_hurdle) > numeric_tolerance:
                raise ValuationCrossCheckError(
                    "valuation methods must share required_return_pct"
                )

        if not method.scenarios:
            raise ValuationCrossCheckError(
                f"{method_id} requires scenarios"
            )

        scenario_map: dict[str, ValuationScenarioSnapshot] = {}
        probability_sum = 0.0
        for scenario in method.scenarios:
            scenario_id = _text(
                scenario.scenario_id,
                "scenario_id",
            )
            if scenario_id in scenario_map:
                raise ValuationCrossCheckError(
                    f"{method_id} duplicate scenario_id: {scenario_id}"
                )
            probability = _finite(
                scenario.probability,
                "scenario probability",
            )
            if probability < 0.0 or probability > 1.0:
                raise ValuationCrossCheckError(
                    "scenario probability must be in [0,1]"
                )
            fair_value = _finite(
                scenario.fair_value,
                "scenario fair_value",
            )
            if fair_value <= 0.0:
                raise ValuationCrossCheckError(
                    "scenario fair_value must be positive"
                )
            scenario_map[scenario_id] = scenario
            probability_sum += probability

        if abs(probability_sum - 1.0) > probability_tolerance:
            raise ValuationCrossCheckError(
                f"{method_id} scenario probabilities must sum to 1"
            )

        ids = tuple(sorted(scenario_map))
        probabilities = {
            scenario_id: float(
                scenario_map[scenario_id].probability
            )
            for scenario_id in ids
        }
        if first_ids is None:
            first_ids = ids
            first_probabilities = probabilities
        else:
            assert first_probabilities is not None
            if ids != first_ids:
                raise ValuationCrossCheckError(
                    "valuation methods must share scenario IDs"
                )
            for scenario_id in ids:
                if abs(
                    probabilities[scenario_id]
                    - first_probabilities[scenario_id]
                ) > probability_tolerance:
                    raise ValuationCrossCheckError(
                        "valuation methods must share scenario probabilities"
                    )

        weighted_value = sum(
            float(item.probability) * float(item.fair_value)
            for item in method.scenarios
        )
        expected_return = (
            weighted_value / price - 1.0
        ) * 100.0
        method_summaries.append(
            {
                "method_id": method_id,
                "method_type": method.method_type,
                "source_schema": method.source_schema,
                "weighted_fair_value": round(
                    weighted_value,
                    6,
                ),
                "expected_return_pct": round(
                    expected_return,
                    6,
                ),
                "required_return_pct": round(
                    hurdle,
                    6,
                ),
                "hurdle_met": expected_return >= hurdle,
                "source_refs": method.source_refs,
                "investment_authority": False,
            }
        )
        method_maps.append(scenario_map)

    assert first_price is not None
    assert first_hurdle is not None
    assert first_ids is not None
    assert first_probabilities is not None

    hurdles = [row["hurdle_met"] for row in method_summaries]
    if all(hurdles):
        classification = "CROSS_METHOD_CONFIRMED"
    elif any(hurdles):
        classification = "CROSS_METHOD_MIXED"
    else:
        classification = "CROSS_METHOD_REJECTED"

    robust_rows: list[dict] = []
    for scenario_id in first_ids:
        values = {
            method.method_id: float(
                scenario_map[scenario_id].fair_value
            )
            for method, scenario_map in zip(
                request.methods,
                method_maps,
            )
        }
        binding_method = min(
            values,
            key=lambda method_id: (
                values[method_id],
                method_id,
            ),
        )
        robust_value = values[binding_method]
        robust_rows.append(
            {
                "scenario_id": scenario_id,
                "probability": round(
                    first_probabilities[scenario_id],
                    12,
                ),
                "method_fair_values": values,
                "binding_method_id": binding_method,
                "robust_lower_of_methods_fair_value": round(
                    robust_value,
                    6,
                ),
            }
        )

    robust_weighted_value = sum(
        float(row["probability"])
        * float(row["robust_lower_of_methods_fair_value"])
        for row in robust_rows
    )
    robust_expected_return = (
        robust_weighted_value / first_price - 1.0
    ) * 100.0
    weighted_values = [
        float(row["weighted_fair_value"])
        for row in method_summaries
    ]

    return ValuationCrossCheckArtifact(
        schema="quantrade_valuation_crosscheck_v1",
        case_id=request.case_id,
        classification=classification,
        method_summaries=tuple(method_summaries),
        robust_scenarios=tuple(robust_rows),
        robust_metrics={
            "current_price": round(first_price, 6),
            "required_return_pct": round(
                first_hurdle,
                6,
            ),
            "weighted_fair_value": round(
                robust_weighted_value,
                6,
            ),
            "expected_return_pct": round(
                robust_expected_return,
                6,
            ),
            "hurdle_met": (
                robust_expected_return >= first_hurdle
            ),
            "all_methods_clear_hurdle": all(hurdles),
            "valuation_gate_passed": (
                all(hurdles)
                and robust_expected_return >= first_hurdle
            ),
            "method_weighted_value_spread_pct_of_current": round(
                (
                    max(weighted_values)
                    - min(weighted_values)
                )
                / first_price
                * 100.0,
                6,
            ),
            "aggregation_rule": "LOWER_OF_ALL_METHODS_BY_SCENARIO",
        },
        validation={
            "method_count": len(request.methods),
            "scenario_ids_aligned": True,
            "scenario_probabilities_aligned": True,
            "case_price_aligned": True,
            "required_return_aligned": True,
            "automatic_method_weighting_used": False,
            "arithmetic_only": True,
        },
        authority={
            "model_called": False,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "target_weight_set": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )
