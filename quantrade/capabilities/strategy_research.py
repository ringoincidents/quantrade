"""Deterministic strategy-research evaluation for QuanTrade.

This capability measures research candidates. It does not create canonical
Evidence, portfolio proposals, risk-limit changes, investment decisions, or
execution authority.

The module intentionally avoids model calls and third-party dependencies.
Candidate generation/DSL parsing is a later capability; this file only
evaluates already-bounded target-position series against point-in-time market
data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import sqrt
from typing import Sequence


class StrategyResearchError(ValueError):
    """Base error for invalid research inputs."""


class LookaheadDetected(StrategyResearchError):
    """Raised when a signal claims information from after its effective time."""


@dataclass(frozen=True)
class EvaluationProviderMetadata:
    provider_id: str = "quantrade.native.strategy_evaluator.v1"
    capability: str = "StrategyEvaluator"
    implementation: str = "quantrade-native-deterministic"
    version_or_revision: str = "v1"
    license: str = "repository-license"
    deterministic: bool = True
    network_access: bool = False
    capital_effect: bool = False
    evidence_effect: str = "NON_CANONICAL"
    status: str = "SANDBOX"


@dataclass(frozen=True)
class CandidateStrategy:
    candidate_id: str
    name: str
    source_type: str
    source_ref: str
    market_scope: str
    rebalance_horizon: str
    description: str = ""


@dataclass(frozen=True)
class PriceBar:
    observed_at: str
    close: float


@dataclass(frozen=True)
class PositionSignal:
    effective_at: str
    information_cutoff: str
    target_position: float


@dataclass(frozen=True)
class DatasetMetadata:
    dataset_id: str
    source: str
    provider: str
    version_or_revision: str
    as_of_start: str
    as_of_end: str
    point_in_time: bool = True
    point_in_time_evidence_ref: str = ""


@dataclass(frozen=True)
class ScreeningPolicy:
    min_return_periods: int = 20
    max_drawdown_pct: float = -20.0
    min_benchmark_excess_return_pct: float = 0.0
    max_turnover_per_period: float | None = None


@dataclass(frozen=True)
class StrategyEvaluation:
    schema: str
    candidate: dict
    dataset: dict
    evaluator: dict
    assumptions: dict
    metrics: dict
    validation: dict
    screening: dict
    authority: dict


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise StrategyResearchError("timestamps must be non-empty ISO-8601 strings")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise StrategyResearchError(f"invalid ISO-8601 timestamp: {value}") from exc
    if dt.tzinfo is None:
        raise StrategyResearchError("timestamps must include timezone information")
    return dt.astimezone(timezone.utc)


def _validate_inputs(
    bars: Sequence[PriceBar],
    signals: Sequence[PositionSignal],
    dataset: DatasetMetadata,
) -> tuple[list[PriceBar], list[PositionSignal]]:
    bars = list(bars)
    signals = list(signals)
    if len(bars) < 2:
        raise StrategyResearchError("at least two price bars are required")
    if len(signals) != len(bars) - 1:
        raise StrategyResearchError(
            "signals must contain exactly one target position for each return period"
        )

    bar_times = [_parse_time(bar.observed_at) for bar in bars]
    if any(not isinstance(bar.close, (int, float)) or bar.close <= 0 for bar in bars):
        raise StrategyResearchError("all close values must be positive numbers")
    if any(b <= a for a, b in zip(bar_times, bar_times[1:])):
        raise StrategyResearchError("price bars must be strictly increasing by timestamp")

    start = _parse_time(dataset.as_of_start)
    end = _parse_time(dataset.as_of_end)
    if start > end:
        raise StrategyResearchError("dataset as_of_start must not exceed as_of_end")
    if start > bar_times[0] or end < bar_times[-1]:
        raise StrategyResearchError(
            "dataset as-of range must cover the evaluated price-bar window"
        )
    if not dataset.point_in_time:
        raise StrategyResearchError(
            "strategy evaluation requires a point-in-time dataset declaration"
        )
    if not dataset.point_in_time_evidence_ref.strip():
        raise StrategyResearchError(
            "point-in-time dataset declaration requires an evidence reference"
        )
    for field_name, field_value in (
        ("dataset_id", dataset.dataset_id),
        ("source", dataset.source),
        ("provider", dataset.provider),
        ("version_or_revision", dataset.version_or_revision),
    ):
        if not isinstance(field_value, str) or not field_value.strip():
            raise StrategyResearchError(f"{field_name} is required")

    for index, signal in enumerate(signals):
        effective = _parse_time(signal.effective_at)
        cutoff = _parse_time(signal.information_cutoff)
        expected = bar_times[index]
        if effective != expected:
            raise StrategyResearchError(
                "signal effective_at must match the start of its return period"
            )
        if cutoff > effective:
            raise LookaheadDetected(
                "signal information_cutoff is later than effective_at"
            )
        if not isinstance(signal.target_position, (int, float)):
            raise StrategyResearchError("target_position must be numeric")
        if signal.target_position < 0.0 or signal.target_position > 1.0:
            raise StrategyResearchError(
                "target_position must be between 0 and 1 in the v1 long-only sandbox"
            )

    return bars, signals


def _returns(values: Sequence[float]) -> list[float]:
    return [(b / a) - 1.0 for a, b in zip(values, values[1:])]


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _population_std(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _compound(returns: Sequence[float]) -> float:
    equity = 1.0
    for value in returns:
        equity *= 1.0 + value
    return equity - 1.0


def _max_drawdown(returns: Sequence[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, equity / peak - 1.0)
    return worst


def _annualized_return(
    total_return: float,
    periods: int,
    periods_per_year: int,
) -> float | None:
    if periods <= 0 or periods_per_year <= 0:
        return None
    ending = 1.0 + total_return
    if ending <= 0:
        return -1.0
    return ending ** (periods_per_year / periods) - 1.0


def _sharpe(returns: Sequence[float], periods_per_year: int) -> float | None:
    std = _population_std(returns)
    if std == 0:
        return None
    return _mean(returns) / std * sqrt(periods_per_year)


def _sortino(returns: Sequence[float], periods_per_year: int) -> float | None:
    downside = [min(value, 0.0) for value in returns]
    downside_deviation = sqrt(
        sum(value * value for value in downside) / len(downside)
    )
    if downside_deviation == 0:
        return None
    return _mean(returns) / downside_deviation * sqrt(periods_per_year)


def _pct(value: float | None) -> float | None:
    return None if value is None else round(value * 100.0, 6)


def evaluate_strategy(
    candidate: CandidateStrategy,
    bars: Sequence[PriceBar],
    signals: Sequence[PositionSignal],
    dataset: DatasetMetadata,
    *,
    transaction_cost_bps: float = 0.0,
    periods_per_year: int = 252,
    screening_policy: ScreeningPolicy | None = None,
    evaluator: EvaluationProviderMetadata | None = None,
) -> StrategyEvaluation:
    """Evaluate one bounded strategy candidate with deterministic arithmetic.

    Position at bar i is applied only to the return from bar i to bar i+1.
    Transaction cost is charged on absolute position turnover at each period
    start, including the initial change from flat.
    """
    if transaction_cost_bps < 0:
        raise StrategyResearchError("transaction_cost_bps must be non-negative")
    if periods_per_year <= 0:
        raise StrategyResearchError("periods_per_year must be positive")

    bars, signals = _validate_inputs(bars, signals, dataset)
    policy = screening_policy or ScreeningPolicy()
    evaluator = evaluator or EvaluationProviderMetadata()
    if policy.min_return_periods < 1:
        raise StrategyResearchError("min_return_periods must be positive")
    if policy.max_drawdown_pct > 0:
        raise StrategyResearchError("max_drawdown_pct must be zero or negative")
    if (
        policy.max_turnover_per_period is not None
        and policy.max_turnover_per_period < 0
    ):
        raise StrategyResearchError(
            "max_turnover_per_period must be non-negative"
        )

    asset_returns = _returns([float(bar.close) for bar in bars])
    positions = [float(signal.target_position) for signal in signals]
    cost_rate = transaction_cost_bps / 10_000.0

    gross_returns: list[float] = []
    net_returns: list[float] = []
    turnover_series: list[float] = []
    prior_position = 0.0
    total_cost = 0.0

    for position, asset_return in zip(positions, asset_returns):
        turnover = abs(position - prior_position)
        cost = turnover * cost_rate
        gross = position * asset_return
        net = gross - cost
        turnover_series.append(turnover)
        gross_returns.append(gross)
        net_returns.append(net)
        total_cost += cost
        prior_position = position

    total_return = _compound(net_returns)
    gross_total_return = _compound(gross_returns)
    benchmark_total_return = _compound(asset_returns)
    annualized = _annualized_return(
        total_return,
        len(net_returns),
        periods_per_year,
    )
    max_dd = _max_drawdown(net_returns)
    calmar = None
    if annualized is not None and max_dd < 0:
        calmar = annualized / abs(max_dd)

    sharpe = _sharpe(net_returns, periods_per_year)
    sortino = _sortino(net_returns, periods_per_year)
    metrics = {
        "return_periods": len(net_returns),
        "gross_total_return_pct": _pct(gross_total_return),
        "net_total_return_pct": _pct(total_return),
        "annualized_return_pct": _pct(annualized),
        "volatility_annualized_pct": _pct(
            _population_std(net_returns) * sqrt(periods_per_year)
        ),
        "sharpe": None if sharpe is None else round(sharpe, 6),
        "sortino": None if sortino is None else round(sortino, 6),
        "maximum_drawdown_pct": _pct(max_dd),
        "calmar": None if calmar is None else round(calmar, 6),
        "turnover_total": round(sum(turnover_series), 6),
        "turnover_per_period": round(_mean(turnover_series), 6),
        "estimated_transaction_cost_pct_of_initial_equity": round(
            total_cost * 100.0,
            6,
        ),
        "max_single_period_loss_pct": _pct(min(0.0, min(net_returns))),
        "benchmark_total_return_pct": _pct(benchmark_total_return),
        "benchmark_excess_return_pct": _pct(
            total_return - benchmark_total_return
        ),
        "coverage_pct": 100.0,
    }

    reasons: list[str] = []
    if len(net_returns) < policy.min_return_periods:
        reasons.append(
            f"INSUFFICIENT_SAMPLE:{len(net_returns)}"
            f"<{policy.min_return_periods}"
        )
    if metrics["maximum_drawdown_pct"] is not None and (
        metrics["maximum_drawdown_pct"] < policy.max_drawdown_pct
    ):
        reasons.append(
            f"DRAWDOWN_LIMIT:{metrics['maximum_drawdown_pct']}"
            f"<{policy.max_drawdown_pct}"
        )
    if metrics["benchmark_excess_return_pct"] is not None and (
        metrics["benchmark_excess_return_pct"]
        < policy.min_benchmark_excess_return_pct
    ):
        reasons.append(
            "BENCHMARK_UNDERPERFORMANCE:"
            f"{metrics['benchmark_excess_return_pct']}"
            f"<{policy.min_benchmark_excess_return_pct}"
        )
    if (
        policy.max_turnover_per_period is not None
        and metrics["turnover_per_period"] > policy.max_turnover_per_period
    ):
        reasons.append(
            "EXCESSIVE_TURNOVER:"
            f"{metrics['turnover_per_period']}"
            f">{policy.max_turnover_per_period}"
        )

    screening_disposition = (
        "SURVIVES_DETERMINISTIC_SCREEN"
        if not reasons
        else "REJECTED_DETERMINISTIC_SCREEN"
    )

    return StrategyEvaluation(
        schema="quantrade_strategy_evaluation_v1",
        candidate=asdict(candidate),
        dataset=asdict(dataset),
        evaluator=asdict(evaluator),
        assumptions={
            "transaction_cost_bps": transaction_cost_bps,
            "periods_per_year": periods_per_year,
            "position_range": [0.0, 1.0],
            "signal_timing": (
                "target_position at bar i applies only to return i→i+1; "
                "information_cutoff must be <= effective_at"
            ),
            "benchmark": "BUY_AND_HOLD_SAME_PRICE_SERIES_BEFORE_COSTS",
        },
        metrics=metrics,
        validation={
            "point_in_time_declared": dataset.point_in_time,
            "point_in_time_evidence_ref": dataset.point_in_time_evidence_ref,
            "lookahead_detected": False,
            "missing_data_imputed": False,
            "signal_count": len(signals),
            "price_bar_count": len(bars),
        },
        screening={
            "disposition": screening_disposition,
            "reasons": reasons,
            "policy": asdict(policy),
            "strategy_approved": False,
            "automatic_promotion_allowed": False,
        },
        authority={
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "risk_limit_changed": False,
            "investment_decision_created": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )
