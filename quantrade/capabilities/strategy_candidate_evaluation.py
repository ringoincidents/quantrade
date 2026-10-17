"""End-to-end sandbox harness for safe candidate generation → evaluation."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from quantrade.capabilities.strategy_candidates import (
    CandidateGenerationContext,
    StaticCandidateProvider,
    compile_position_signals,
    validate_formula,
)
from quantrade.capabilities.strategy_research import (
    CandidateStrategy,
    DatasetMetadata,
    PriceBar,
    ScreeningPolicy,
    evaluate_strategy,
)


def _bars(count: int = 60) -> list[PriceBar]:
    start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    values = []
    price = 100.0
    for index in range(count):
        if index < 20:
            drift = 0.003
        elif index < 40:
            drift = -0.002
        else:
            drift = 0.001
        cycle = 0.004 if index % 5 in (0, 1) else -0.002
        price *= 1.0 + drift + cycle
        values.append(
            PriceBar(
                observed_at=(start + timedelta(days=index)).isoformat(),
                close=round(price, 8),
            )
        )
    return values


def _dataset(bars: list[PriceBar]) -> DatasetMetadata:
    return DatasetMetadata(
        dataset_id="SYNTHETIC-CANDIDATE-PIT-001",
        source="fixture://strategy-candidates/synthetic",
        provider="quantrade-test-fixture",
        version_or_revision="v1",
        as_of_start=bars[0].observed_at,
        as_of_end=bars[-1].observed_at,
        point_in_time=True,
        point_in_time_evidence_ref=(
            "fixture://strategy-candidates/pit-manifest-v1"
        ),
    )


def _candidates() -> tuple[CandidateStrategy, ...]:
    return (
        CandidateStrategy(
            candidate_id="DSL-SMA-TREND-001",
            name="Safe DSL SMA trend reference",
            source_type="STATIC_FIXTURE",
            source_ref="fixture://strategy-candidates/sma-trend",
            market_scope="SYNTHETIC",
            rebalance_horizon="DAILY",
            description="Reference only; not validated alpha.",
            formula_ast={
                "op": "GT",
                "left": {"op": "SMA", "window": 5},
                "right": {"op": "SMA", "window": 15},
            },
            parameter_set={"short_window": 5, "long_window": 15},
        ),
        CandidateStrategy(
            candidate_id="DSL-ZSCORE-MR-001",
            name="Safe DSL z-score mean reversion reference",
            source_type="STATIC_FIXTURE",
            source_ref="fixture://strategy-candidates/zscore-mr",
            market_scope="SYNTHETIC",
            rebalance_horizon="DAILY",
            description="Reference only; not validated alpha.",
            formula_ast={
                "op": "LT",
                "left": {"op": "ZSCORE", "window": 10},
                "right": {"op": "CONST", "value": -1.0},
            },
            parameter_set={"zscore_window": 10, "entry_threshold": -1.0},
        ),
    )


def candidate_generation_experiment() -> dict:
    """Run the entire safe static-provider → compiler → evaluator seam."""
    bars = _bars()
    dataset = _dataset(bars)
    provider = StaticCandidateProvider(_candidates())
    generated = provider.generate(
        CandidateGenerationContext(
            market_scope="SYNTHETIC",
            rebalance_horizon="DAILY",
        )
    )
    policy = ScreeningPolicy(
        min_return_periods=20,
        max_drawdown_pct=-50.0,
        min_benchmark_excess_return_pct=-100.0,
        max_turnover_per_period=0.8,
    )

    results = []
    for candidate in generated:
        validation = validate_formula(candidate.formula_ast)
        signals = compile_position_signals(candidate, bars)
        evaluation = evaluate_strategy(
            candidate,
            bars,
            signals,
            dataset,
            transaction_cost_bps=20.0,
            periods_per_year=252,
            screening_policy=policy,
        )
        results.append(
            {
                "candidate": asdict(candidate),
                "formula_validation": validation,
                "signal_summary": {
                    "count": len(signals),
                    "long_periods": sum(
                        1 for signal in signals
                        if signal.target_position == 1.0
                    ),
                    "flat_periods": sum(
                        1 for signal in signals
                        if signal.target_position == 0.0
                    ),
                    "future_information_required": False,
                },
                "evaluation": asdict(evaluation),
            }
        )

    return {
        "schema": "quantrade_strategy_candidate_experiment_v1",
        "provider": asdict(provider.metadata),
        "candidate_count": len(results),
        "results": results,
        "pipeline": [
            "STATIC_CANDIDATE_PROVIDER",
            "SAFE_AST_VALIDATION",
            "PAST_ONLY_SIGNAL_COMPILER",
            "DETERMINISTIC_STRATEGY_EVALUATOR",
        ],
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "strategy_approved": False,
            "investment_decision_created": False,
            "execution_authorized": False,
        },
    }
