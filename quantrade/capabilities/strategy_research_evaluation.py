"""Synthetic, deterministic evaluation harness for Strategy Research Sandbox."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from quantrade.capabilities.strategy_research import (
    CandidateStrategy,
    DatasetMetadata,
    LookaheadDetected,
    PositionSignal,
    PriceBar,
    ScreeningPolicy,
    evaluate_strategy,
)


def _bars(count: int = 40) -> list[PriceBar]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    prices = []
    price = 100.0
    for i in range(count):
        drift = 0.004 if i < 20 else -0.001
        noise = 0.002 if i % 2 == 0 else -0.001
        price *= 1.0 + drift + noise
        prices.append(
            PriceBar(
                observed_at=(start + timedelta(days=i)).isoformat(),
                close=round(price, 8),
            )
        )
    return prices


def _dataset(bars: list[PriceBar]) -> DatasetMetadata:
    return DatasetMetadata(
        dataset_id="SYNTHETIC-PIT-001",
        source="fixture://strategy-research/synthetic",
        provider="quantrade-test-fixture",
        version_or_revision="v1",
        as_of_start=bars[0].observed_at,
        as_of_end=bars[-1].observed_at,
        point_in_time=True,
        point_in_time_evidence_ref=(
            "fixture://strategy-research/pit-manifest-v1"
        ),
    )


def _signals(
    bars: list[PriceBar],
    positions: list[float],
    *,
    lookahead_index: int | None = None,
) -> list[PositionSignal]:
    out = []
    for i, position in enumerate(positions):
        cutoff = bars[i].observed_at
        if lookahead_index is not None and i == lookahead_index:
            cutoff = bars[i + 1].observed_at
        out.append(
            PositionSignal(
                effective_at=bars[i].observed_at,
                information_cutoff=cutoff,
                target_position=position,
            )
        )
    return out


def _sma_positions(
    bars: list[PriceBar],
    short: int = 3,
    long: int = 8,
) -> list[float]:
    closes = [bar.close for bar in bars]
    positions = []
    for i in range(len(bars) - 1):
        if i + 1 < long:
            positions.append(0.0)
            continue
        short_avg = sum(closes[i - short + 1 : i + 1]) / short
        long_avg = sum(closes[i - long + 1 : i + 1]) / long
        positions.append(1.0 if short_avg > long_avg else 0.0)
    return positions


def canonical_experiment() -> dict:
    bars = _bars()
    dataset = _dataset(bars)
    policy = ScreeningPolicy(
        min_return_periods=20,
        max_drawdown_pct=-20.0,
        min_benchmark_excess_return_pct=-100.0,
        max_turnover_per_period=0.5,
    )
    candidates = {
        "buy_and_hold": (
            CandidateStrategy(
                "REF-BUY-HOLD",
                "Buy and Hold Reference",
                "REFERENCE_FIXTURE",
                "fixture://buy-and-hold",
                "SYNTHETIC",
                "DAILY",
            ),
            [1.0] * (len(bars) - 1),
        ),
        "sma_crossover": (
            CandidateStrategy(
                "REF-SMA",
                "SMA Crossover Reference",
                "REFERENCE_FIXTURE",
                "fixture://sma-crossover",
                "SYNTHETIC",
                "DAILY",
            ),
            _sma_positions(bars),
        ),
        "high_turnover": (
            CandidateStrategy(
                "REF-HIGH-TURNOVER",
                "High Turnover Reference",
                "REFERENCE_FIXTURE",
                "fixture://high-turnover",
                "SYNTHETIC",
                "DAILY",
            ),
            [
                1.0 if i % 2 == 0 else 0.0
                for i in range(len(bars) - 1)
            ],
        ),
    }

    results = {}
    for key, (candidate, positions) in candidates.items():
        evaluation = evaluate_strategy(
            candidate,
            bars,
            _signals(bars, positions),
            dataset,
            transaction_cost_bps=50.0,
            periods_per_year=252,
            screening_policy=policy,
        )
        results[key] = asdict(evaluation)

    high_turnover_zero_cost = evaluate_strategy(
        candidates["high_turnover"][0],
        bars,
        _signals(bars, candidates["high_turnover"][1]),
        dataset,
        transaction_cost_bps=0.0,
        periods_per_year=252,
        screening_policy=policy,
    )
    results["high_turnover_cost_comparison"] = {
        "zero_cost_net_total_return_pct": (
            high_turnover_zero_cost.metrics["net_total_return_pct"]
        ),
        "cost_adjusted_net_total_return_pct": (
            results["high_turnover"]["metrics"]["net_total_return_pct"]
        ),
        "cost_hurts_or_equal": (
            results["high_turnover"]["metrics"]["net_total_return_pct"]
            <= high_turnover_zero_cost.metrics["net_total_return_pct"]
        ),
    }

    leaky_candidate = CandidateStrategy(
        "REF-LEAKY",
        "Intentionally Leaky Future Return Fixture",
        "NEGATIVE_CONTROL",
        "fixture://lookahead",
        "SYNTHETIC",
        "DAILY",
    )
    try:
        evaluate_strategy(
            leaky_candidate,
            bars,
            _signals(
                bars,
                [1.0] * (len(bars) - 1),
                lookahead_index=5,
            ),
            dataset,
            transaction_cost_bps=0.0,
            screening_policy=policy,
        )
        leakage = {"detected": False, "error": None}
    except LookaheadDetected as exc:
        leakage = {"detected": True, "error": str(exc)}

    return {
        "schema": "quantrade_strategy_research_reference_experiment_v1",
        "dataset": asdict(dataset),
        "results": results,
        "negative_controls": {"lookahead": leakage},
        "historical_lessons_encoded": [
            "POINT_IN_TIME_REQUIRED",
            "TRANSACTION_COSTS_EXPLICIT",
            "BENCHMARK_EXPLICIT",
            "MISSING_DATA_FAIL_CLOSED",
            "DETERMINISTIC_MEASUREMENT_BEFORE_REASONING",
            "NO_STRATEGY_OR_EXECUTION_AUTHORITY",
        ],
        "authority": {
            "canonical_evidence_created": False,
            "strategy_approved": False,
            "investment_decision_created": False,
            "execution_authorized": False,
        },
    }
