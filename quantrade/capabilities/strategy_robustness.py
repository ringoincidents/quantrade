"""Deterministic robustness gate and bounded specialist-review planner.

This is a research prioritization layer. It cannot approve a strategy, change
risk policy, create an investment decision, call a model, or authorize
execution. Expensive specialist reasoning is planned only after deterministic
screening and duplicate suppression.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from quantrade.capabilities.review_gate import ReviewEvent, evaluate_review_need
from quantrade.capabilities.strategy_research import StrategyEvaluation


class RobustnessGateError(ValueError):
    """Raised when robustness inputs are incomplete or inconsistent."""


@dataclass(frozen=True)
class RobustnessPolicy:
    min_return_periods: int = 20
    max_drawdown_pct: float = -20.0
    min_benchmark_excess_return_pct: float = 0.0
    max_turnover_per_period: float = 0.5
    max_cost_drag_pct: float = 5.0
    signal_similarity_threshold: float = 0.95
    top_k: int = 3
    review_materiality: float = 0.60


@dataclass(frozen=True)
class CandidateReviewInput:
    candidate_id: str
    evaluation: StrategyEvaluation | dict
    positions: tuple[float, ...]


@dataclass(frozen=True)
class SpecialistReviewContext:
    has_portfolio_context: bool = False
    risk_review_required: bool = True
    external_dependency_requires_review: bool = False


@dataclass(frozen=True)
class SpecialistWorkRequest:
    candidate_id: str
    role: str
    question: str
    decision_change: str
    max_model_calls: int = 1
    max_tool_rounds: int = 3


def _evaluation_dict(evaluation: StrategyEvaluation | dict) -> dict:
    if isinstance(evaluation, StrategyEvaluation):
        return asdict(evaluation)
    if isinstance(evaluation, dict):
        return evaluation
    raise RobustnessGateError("evaluation must be StrategyEvaluation or dict")


def _required_metric(metrics: dict, name: str) -> float:
    value = metrics.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RobustnessGateError(f"required metric missing or invalid: {name}")
    return float(value)


def evaluate_candidate_robustness(
    item: CandidateReviewInput,
    policy: RobustnessPolicy | None = None,
) -> dict:
    policy = policy or RobustnessPolicy()
    if not item.candidate_id.strip():
        raise RobustnessGateError("candidate_id is required")
    if policy.min_return_periods < 1 or policy.top_k < 1:
        raise RobustnessGateError("positive sample and top_k bounds are required")
    if not 0.0 <= policy.signal_similarity_threshold <= 1.0:
        raise RobustnessGateError(
            "signal_similarity_threshold must be between 0 and 1"
        )
    if not 0.0 <= policy.review_materiality <= 1.0:
        raise RobustnessGateError("review_materiality must be between 0 and 1")
    if not item.positions:
        raise RobustnessGateError("positions are required for robustness review")
    if any(position not in (0.0, 1.0) for position in item.positions):
        raise RobustnessGateError(
            "v1 robustness gate accepts only long/flat position vectors"
        )

    evaluation = _evaluation_dict(item.evaluation)
    screening = evaluation.get("screening")
    metrics = evaluation.get("metrics")
    if not isinstance(screening, dict) or not isinstance(metrics, dict):
        raise RobustnessGateError(
            "evaluation must contain screening and metrics objects"
        )

    reasons: list[str] = []
    upstream = screening.get("disposition")
    if upstream != "SURVIVES_DETERMINISTIC_SCREEN":
        reasons.append(f"UPSTREAM_SCREEN:{upstream or 'UNKNOWN'}")

    periods = _required_metric(metrics, "return_periods")
    drawdown = _required_metric(metrics, "maximum_drawdown_pct")
    excess = _required_metric(metrics, "benchmark_excess_return_pct")
    turnover = _required_metric(metrics, "turnover_per_period")
    gross_return = _required_metric(metrics, "gross_total_return_pct")
    net_return = _required_metric(metrics, "net_total_return_pct")
    sharpe_raw = metrics.get("sharpe")
    sharpe = (
        float(sharpe_raw)
        if isinstance(sharpe_raw, (int, float)) and not isinstance(sharpe_raw, bool)
        else float("-inf")
    )
    cost_drag = max(0.0, gross_return - net_return)

    if periods < policy.min_return_periods:
        reasons.append(
            f"INSUFFICIENT_SAMPLE:{int(periods)}<{policy.min_return_periods}"
        )
    if drawdown < policy.max_drawdown_pct:
        reasons.append(
            f"DRAWDOWN_LIMIT:{drawdown}<{policy.max_drawdown_pct}"
        )
    if excess < policy.min_benchmark_excess_return_pct:
        reasons.append(
            "BENCHMARK_UNDERPERFORMANCE:"
            f"{excess}<{policy.min_benchmark_excess_return_pct}"
        )
    if turnover > policy.max_turnover_per_period:
        reasons.append(
            f"EXCESSIVE_TURNOVER:{turnover}>{policy.max_turnover_per_period}"
        )
    if cost_drag > policy.max_cost_drag_pct:
        reasons.append(
            f"COST_SENSITIVITY:{round(cost_drag, 6)}>{policy.max_cost_drag_pct}"
        )

    disposition = (
        "ROBUSTNESS_SURVIVOR"
        if not reasons
        else "ROBUSTNESS_REJECTED"
    )
    return {
        "schema": "quantrade_strategy_robustness_result_v1",
        "candidate_id": item.candidate_id,
        "disposition": disposition,
        "reasons": reasons,
        "metrics": {
            "return_periods": int(periods),
            "maximum_drawdown_pct": drawdown,
            "benchmark_excess_return_pct": excess,
            "turnover_per_period": turnover,
            "gross_total_return_pct": gross_return,
            "net_total_return_pct": net_return,
            "cost_drag_pct": round(cost_drag, 6),
            "sharpe": None if sharpe == float("-inf") else sharpe,
        },
        "research_priority": {
            "sort_basis": [
                "higher benchmark_excess_return_pct",
                "higher sharpe",
                "lower cost_drag_pct",
                "lower turnover_per_period",
            ],
            "investment_score_created": False,
        },
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "risk_limit_changed": False,
            "strategy_approved": False,
            "investment_decision_created": False,
            "execution_authorized": False,
        },
    }


def _priority_key(result: dict) -> tuple[float, float, float, float, str]:
    metrics = result["metrics"]
    sharpe = metrics["sharpe"]
    return (
        float(metrics["benchmark_excess_return_pct"]),
        float(sharpe) if sharpe is not None else float("-inf"),
        -float(metrics["cost_drag_pct"]),
        -float(metrics["turnover_per_period"]),
        result["candidate_id"],
    )


def signal_similarity(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    if not left or not right or len(left) != len(right):
        raise RobustnessGateError(
            "signal similarity requires equal non-empty position vectors"
        )
    return sum(
        1 for a, b in zip(left, right) if float(a) == float(b)
    ) / len(left)


def build_specialist_work(
    candidate_id: str,
    context: SpecialistReviewContext,
) -> tuple[SpecialistWorkRequest, ...]:
    requests = [
        SpecialistWorkRequest(
            candidate_id,
            "QUANT_MARKET",
            "Can statistical or market-structure evidence falsify this candidate?",
            "KEEP_OR_REJECT",
        ),
        SpecialistWorkRequest(
            candidate_id,
            "COUNTER_RESEARCH",
            "What strongest evidence or failure mode contradicts this candidate?",
            "KEEP_OR_REJECT_OR_CONFIDENCE",
        ),
    ]
    if context.has_portfolio_context:
        requests.append(
            SpecialistWorkRequest(
                candidate_id,
                "PORTFOLIO_MANAGEMENT",
                "Does this candidate improve the current total portfolio after overlap and concentration?",
                "KEEP_OR_SIZE_OR_REJECT",
            )
        )
    if context.risk_review_required:
        requests.append(
            SpecialistWorkRequest(
                candidate_id,
                "RISK_COMPLIANCE",
                "Do downside, concentration, liquidity, or policy constraints reject this candidate?",
                "RISK_VETO_OR_LIMIT",
            )
        )
    if context.external_dependency_requires_review:
        requests.append(
            SpecialistWorkRequest(
                candidate_id,
                "DEEP_EXTERNAL_RESEARCH",
                "Does the external theory, mechanism, or market dependency survive source verification?",
                "KEEP_OR_REJECT_OR_CONFIDENCE",
            )
        )
    return tuple(requests)


def build_robustness_review_batch(
    items: Sequence[CandidateReviewInput],
    *,
    policy: RobustnessPolicy | None = None,
    review_context: SpecialistReviewContext | None = None,
) -> dict:
    """Screen, deduplicate, bound top-K, then plan review work.

    No specialist is actually invoked here. This function creates auditable
    Work requests and routes review necessity through the existing ReviewGate.
    """
    policy = policy or RobustnessPolicy()
    review_context = review_context or SpecialistReviewContext()
    items = tuple(items)
    seen_ids: set[str] = set()
    by_id: dict[str, CandidateReviewInput] = {}
    results = []

    for item in items:
        if item.candidate_id in seen_ids:
            raise RobustnessGateError(
                f"duplicate candidate_id in robustness batch: {item.candidate_id}"
            )
        seen_ids.add(item.candidate_id)
        by_id[item.candidate_id] = item
        results.append(evaluate_candidate_robustness(item, policy))

    survivors = [
        result for result in results
        if result["disposition"] == "ROBUSTNESS_SURVIVOR"
    ]
    survivors.sort(key=_priority_key, reverse=True)

    kept: list[dict] = []
    suppressed: list[dict] = []
    for result in survivors:
        candidate_id = result["candidate_id"]
        duplicate_of = None
        duplicate_similarity = None
        for prior in kept:
            similarity = signal_similarity(
                by_id[candidate_id].positions,
                by_id[prior["candidate_id"]].positions,
            )
            if similarity >= policy.signal_similarity_threshold:
                duplicate_of = prior["candidate_id"]
                duplicate_similarity = similarity
                break
        if duplicate_of is not None:
            suppressed.append(
                {
                    "candidate_id": candidate_id,
                    "duplicate_of": duplicate_of,
                    "signal_similarity": round(duplicate_similarity, 6),
                    "reason": "NEAR_DUPLICATE_SIGNAL_PATH",
                }
            )
        else:
            kept.append(result)

    selected = kept[: policy.top_k]
    overflow = kept[policy.top_k :]
    for result in overflow:
        suppressed.append(
            {
                "candidate_id": result["candidate_id"],
                "duplicate_of": None,
                "signal_similarity": None,
                "reason": f"TOP_K_BOUND:{policy.top_k}",
            }
        )

    review_events = [
        ReviewEvent(
            "STRATEGY_RESEARCH_SURVIVOR",
            policy.review_materiality,
            "Research",
        )
        for _ in selected
    ]
    review_gate = evaluate_review_need(review_events)

    work_requests = []
    if review_gate.level != "NO_REVIEW":
        for result in selected:
            work_requests.extend(
                asdict(request)
                for request in build_specialist_work(
                    result["candidate_id"],
                    review_context,
                )
            )

    rejected = [
        result for result in results
        if result["disposition"] == "ROBUSTNESS_REJECTED"
    ]
    return {
        "schema": "quantrade_strategy_robustness_review_batch_v1",
        "policy": asdict(policy),
        "input_count": len(items),
        "robustness_survivor_count": len(survivors),
        "selected_count": len(selected),
        "selected": selected,
        "rejected": rejected,
        "suppressed": suppressed,
        "review_gate": {
            "level": review_gate.level,
            "reasons": list(review_gate.reasons),
            "event_count": review_gate.event_count,
        },
        "specialist_work_requests": work_requests,
        "telemetry": {
            "specialists_planned": len(work_requests),
            "specialists_invoked": 0,
            "model_calls": 0,
            "tool_rounds": 0,
        },
        "authority": {
            "research_prioritized": True,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "risk_limit_changed": False,
            "strategy_approved": False,
            "investment_decision_created": False,
            "execution_authorized": False,
            "automatic_promotion_allowed": False,
        },
    }
