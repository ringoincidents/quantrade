"""Reference experiment for deterministic robustness + bounded review planning."""
from __future__ import annotations

from quantrade.capabilities.strategy_robustness import (
    CandidateReviewInput,
    RobustnessPolicy,
    SpecialistReviewContext,
    build_robustness_review_batch,
)


def _evaluation(
    *,
    excess: float,
    sharpe: float,
    turnover: float = 0.10,
    gross: float = 10.0,
    net: float = 9.0,
    drawdown: float = -10.0,
    disposition: str = "SURVIVES_DETERMINISTIC_SCREEN",
) -> dict:
    return {
        "schema": "quantrade_strategy_evaluation_v1",
        "screening": {"disposition": disposition},
        "metrics": {
            "return_periods": 60,
            "maximum_drawdown_pct": drawdown,
            "benchmark_excess_return_pct": excess,
            "turnover_per_period": turnover,
            "gross_total_return_pct": gross,
            "net_total_return_pct": net,
            "sharpe": sharpe,
        },
    }


def robustness_reference_experiment() -> dict:
    items = [
        CandidateReviewInput(
            "SURVIVOR-A",
            _evaluation(excess=8.0, sharpe=1.2),
            (1, 1, 1, 0, 0, 1, 1, 0),
        ),
        CandidateReviewInput(
            "NEAR-DUPLICATE-B",
            _evaluation(excess=7.0, sharpe=1.1),
            (1, 1, 1, 0, 0, 1, 1, 0),
        ),
        CandidateReviewInput(
            "SURVIVOR-C",
            _evaluation(excess=5.0, sharpe=0.9),
            (0, 0, 1, 1, 0, 0, 1, 1),
        ),
        CandidateReviewInput(
            "COST-SENSITIVE-D",
            _evaluation(
                excess=12.0,
                sharpe=1.5,
                turnover=0.2,
                gross=25.0,
                net=5.0,
            ),
            (1, 0, 1, 0, 1, 0, 1, 0),
        ),
    ]
    return build_robustness_review_batch(
        items,
        policy=RobustnessPolicy(
            min_return_periods=20,
            max_drawdown_pct=-20.0,
            min_benchmark_excess_return_pct=0.0,
            max_turnover_per_period=0.5,
            max_cost_drag_pct=5.0,
            signal_similarity_threshold=0.95,
            top_k=2,
            review_materiality=0.60,
        ),
        review_context=SpecialistReviewContext(
            has_portfolio_context=True,
            risk_review_required=True,
            external_dependency_requires_review=False,
        ),
    )
