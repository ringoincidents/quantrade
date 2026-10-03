from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


class InstitutionalAction(str, Enum):
    ENTER_NOW = "ENTER_NOW"
    WAIT = "WAIT"
    HOLD = "HOLD"
    REDUCE_25 = "REDUCE_25"
    REDUCE_50 = "REDUCE_50"
    EXIT = "EXIT"
    CANCEL_PENDING = "CANCEL_PENDING"
    PAUSE_NEW_ENTRY = "PAUSE_NEW_ENTRY"
    ESCALATE = "ESCALATE"


class ShockSeverity(str, Enum):
    NONE = "NONE"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class PricePoint:
    observed_at: str
    price: float


@dataclass(frozen=True)
class ShockObservation:
    severity: ShockSeverity
    return_pct: float
    window_seconds: int
    direction: str
    immediate_actions: tuple[InstitutionalAction, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["severity"] = self.severity.value
        payload["immediate_actions"] = [a.value for a in self.immediate_actions]
        return payload


@dataclass(frozen=True)
class ShockPolicy:
    elevated_pct: float = 1.0
    high_pct: float = 3.0
    critical_pct: float = 5.0
    window_seconds: int = 300

    def __post_init__(self) -> None:
        if not (0 < self.elevated_pct < self.high_pct < self.critical_pct):
            raise ValueError("shock thresholds must increase strictly")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")


class ShockDetector:
    """D0 detector. It may reduce risk, never increase exposure."""

    def __init__(self, policy: ShockPolicy | None = None) -> None:
        self.policy = policy or ShockPolicy()

    def evaluate(self, start_price: float, end_price: float) -> ShockObservation:
        if start_price <= 0 or end_price <= 0:
            raise ValueError("prices must be positive")
        return_pct = (end_price / start_price - 1.0) * 100.0
        magnitude = abs(return_pct)

        severity = ShockSeverity.NONE
        if magnitude >= self.policy.critical_pct:
            severity = ShockSeverity.CRITICAL
        elif magnitude >= self.policy.high_pct:
            severity = ShockSeverity.HIGH
        elif magnitude >= self.policy.elevated_pct:
            severity = ShockSeverity.ELEVATED

        direction = "UP" if return_pct > 0 else "DOWN" if return_pct < 0 else "FLAT"

        if severity == ShockSeverity.NONE:
            actions: tuple[InstitutionalAction, ...] = ()
        elif severity == ShockSeverity.ELEVATED:
            actions = (
                InstitutionalAction.PAUSE_NEW_ENTRY,
                InstitutionalAction.ESCALATE,
            )
        elif severity == ShockSeverity.HIGH:
            actions = (
                InstitutionalAction.PAUSE_NEW_ENTRY,
                InstitutionalAction.REDUCE_25,
                InstitutionalAction.REDUCE_50,
                InstitutionalAction.ESCALATE,
            )
        else:
            actions = (
                InstitutionalAction.PAUSE_NEW_ENTRY,
                InstitutionalAction.CANCEL_PENDING,
                InstitutionalAction.REDUCE_50,
                InstitutionalAction.EXIT,
                InstitutionalAction.ESCALATE,
            )

        return ShockObservation(
            severity=severity,
            return_pct=return_pct,
            window_seconds=self.policy.window_seconds,
            direction=direction,
            immediate_actions=actions,
        )


@dataclass(frozen=True)
class PricingSnapshot:
    pricing_id: str
    provider: str
    model: str
    effective_at: str
    input_usd_per_million: float = 0.0
    cached_input_usd_per_million: float = 0.0
    output_usd_per_million: float = 0.0
    reasoning_usd_per_million: float = 0.0

    def __post_init__(self) -> None:
        for value in (
            self.input_usd_per_million,
            self.cached_input_usd_per_million,
            self.output_usd_per_million,
            self.reasoning_usd_per_million,
        ):
            if value < 0:
                raise ValueError("pricing rates cannot be negative")


@dataclass(frozen=True)
class ModelCallEconomics:
    role: str
    provider: str
    model: str
    latency_ms: float
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    retries: int = 0
    pricing_id: str | None = None

    def __post_init__(self) -> None:
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        for value in (
            self.input_tokens,
            self.cached_input_tokens,
            self.output_tokens,
            self.reasoning_tokens,
            self.retries,
        ):
            if value < 0:
                raise ValueError("usage values cannot be negative")

    def cost_usd(self, pricing: PricingSnapshot) -> float:
        if pricing.provider != self.provider or pricing.model != self.model:
            raise ValueError("pricing snapshot does not match model call")
        noncached_input = max(0, self.input_tokens - self.cached_input_tokens)
        return (
            noncached_input * pricing.input_usd_per_million
            + self.cached_input_tokens * pricing.cached_input_usd_per_million
            + self.output_tokens * pricing.output_usd_per_million
            + self.reasoning_tokens * pricing.reasoning_usd_per_million
        ) / 1_000_000.0


@dataclass(frozen=True)
class PipelineTiming:
    market_data_ms: float = 0.0
    deterministic_features_ms: float = 0.0
    chart_render_ms: float = 0.0
    committee_assembly_ms: float = 0.0
    execution_adapter_ms: float = 0.0
    other_ms: float = 0.0

    def __post_init__(self) -> None:
        for value in asdict(self).values():
            if value < 0:
                raise ValueError("pipeline timing cannot be negative")

    def non_model_total_ms(self) -> float:
        return float(sum(asdict(self).values()))


@dataclass(frozen=True)
class TradingFriction:
    fee_usd: float = 0.0
    fill_slippage_usd: float = 0.0
    infra_usd: float = 0.0
    market_data_usd: float = 0.0

    def total_usd(self) -> float:
        values = asdict(self)
        if any(v < 0 for v in values.values()):
            raise ValueError("friction costs cannot be negative")
        return float(sum(values.values()))


@dataclass(frozen=True)
class DecisionEpisodeInput:
    episode_id: str
    baseline: str
    action: InstitutionalAction
    event_price: float
    executable_price: float
    position_direction: str
    gross_trading_pnl_usd: float
    market_exposure_usd: float
    model_calls: tuple[ModelCallEconomics, ...] = ()
    pipeline_timing: PipelineTiming = field(default_factory=PipelineTiming)
    friction: TradingFriction = field(default_factory=TradingFriction)
    chart_vision_used: bool = False

    def __post_init__(self) -> None:
        if self.event_price <= 0 or self.executable_price <= 0:
            raise ValueError("prices must be positive")
        if self.market_exposure_usd < 0:
            raise ValueError("market exposure cannot be negative")
        if self.position_direction not in {"LONG", "SHORT", "FLAT"}:
            raise ValueError("unsupported position_direction")


def latency_move_bps(
    *,
    event_price: float,
    executable_price: float,
    action: InstitutionalAction,
    position_direction: str,
) -> float:
    raw_bps = (executable_price / event_price - 1.0) * 10_000.0

    if action == InstitutionalAction.ENTER_NOW:
        return raw_bps

    if action in {
        InstitutionalAction.EXIT,
        InstitutionalAction.REDUCE_25,
        InstitutionalAction.REDUCE_50,
    }:
        if position_direction == "LONG":
            return -raw_bps
        if position_direction == "SHORT":
            return raw_bps

    return 0.0


def evaluate_decision_episode(
    episode: DecisionEpisodeInput,
    *,
    pricing: dict[tuple[str, str], PricingSnapshot] | None = None,
) -> dict[str, Any]:
    pricing = pricing or {}
    model_cost = 0.0
    model_latency_ms = 0.0
    priced_calls = 0

    call_rows: list[dict[str, Any]] = []
    for call in episode.model_calls:
        model_latency_ms += call.latency_ms
        snapshot = pricing.get((call.provider, call.model))
        cost = None
        if snapshot is not None:
            cost = call.cost_usd(snapshot)
            model_cost += cost
            priced_calls += 1
        call_rows.append(
            {
                **asdict(call),
                "calculated_cost_usd": cost,
                "pricing_id": snapshot.pricing_id if snapshot else call.pricing_id,
            }
        )

    non_model_latency = episode.pipeline_timing.non_model_total_ms()
    wall_clock_proxy_ms = non_model_latency + model_latency_ms
    delay_bps = latency_move_bps(
        event_price=episode.event_price,
        executable_price=episode.executable_price,
        action=episode.action,
        position_direction=episode.position_direction,
    )
    latency_opportunity_cost_usd = (
        abs(delay_bps) / 10_000.0 * episode.market_exposure_usd
    )
    friction_total = episode.friction.total_usd()
    measured_system_cost = model_cost + friction_total
    economic_net_after_measured_cost = (
        episode.gross_trading_pnl_usd - measured_system_cost
    )
    conservative_net_after_latency = (
        economic_net_after_measured_cost - latency_opportunity_cost_usd
    )

    return {
        "schema": "quantrade_decision_episode_economics_v1",
        "episode_id": episode.episode_id,
        "baseline": episode.baseline,
        "action": episode.action.value,
        "chart_vision_used": episode.chart_vision_used,
        "event_price": episode.event_price,
        "executable_price": episode.executable_price,
        "position_direction": episode.position_direction,
        "market_exposure_usd": episode.market_exposure_usd,
        "gross_trading_pnl_usd": episode.gross_trading_pnl_usd,
        "latency_move_bps": delay_bps,
        "latency_opportunity_cost_usd": latency_opportunity_cost_usd,
        "model_calls": call_rows,
        "model_call_count": len(call_rows),
        "priced_model_call_count": priced_calls,
        "model_cost_usd": model_cost,
        "model_latency_ms": model_latency_ms,
        "pipeline_timing": asdict(episode.pipeline_timing),
        "non_model_latency_ms": non_model_latency,
        "workflow_latency_proxy_ms": wall_clock_proxy_ms,
        "trading_and_infra_friction": asdict(episode.friction),
        "trading_and_infra_friction_usd": friction_total,
        "measured_system_cost_usd": measured_system_cost,
        "economic_net_after_measured_cost_usd": economic_net_after_measured_cost,
        "conservative_net_after_latency_usd": conservative_net_after_latency,
        "pricing_complete": priced_calls == len(call_rows),
    }


def compare_episode_baselines(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(results)
    if not rows:
        raise ValueError("at least one episode result is required")

    ranked = sorted(
        rows,
        key=lambda row: float(row["conservative_net_after_latency_usd"]),
        reverse=True,
    )
    return {
        "schema": "quantrade_decision_baseline_comparison_v1",
        "episode_id": rows[0]["episode_id"],
        "results": rows,
        "best_observed_baseline": ranked[0]["baseline"],
        "net_spread_usd": (
            float(ranked[0]["conservative_net_after_latency_usd"])
            - float(ranked[-1]["conservative_net_after_latency_usd"])
        ),
        "note": (
            "best_observed_baseline is descriptive for this replay episode only; "
            "it does not validate a strategy or architecture."
        ),
    }
