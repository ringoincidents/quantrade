from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Iterable


class ValidationState(str, Enum):
    EXPERIMENT_ONLY = "EXPERIMENT_ONLY"
    PAPER_VALIDATED = "PAPER_VALIDATED"
    MICRO_LIVE_VALIDATED = "MICRO_LIVE_VALIDATED"
    REJECTED = "REJECTED"


class TransferClass(str, Enum):
    SAME_SCOPE_REVALIDATE = "SAME_SCOPE_REVALIDATE"
    SAME_ASSET_CLASS_NEW_VENUE = "SAME_ASSET_CLASS_NEW_VENUE"
    NEW_ASSET_CLASS_FULL_VALIDATION = "NEW_ASSET_CLASS_FULL_VALIDATION"


@dataclass(frozen=True)
class MarketScope:
    asset_class: str
    venue: str
    universe: tuple[str, ...]
    quote_currency: str
    timeframe: str

    def key(self) -> str:
        return "|".join(
            [
                self.asset_class.upper(),
                self.venue.upper(),
                ",".join(symbol.upper() for symbol in self.universe),
                self.quote_currency.upper(),
                self.timeframe.lower(),
            ]
        )


@dataclass
class StrategyPassport:
    strategy_id: str
    name: str
    hypothesis: str
    validations: dict[str, ValidationState] = field(default_factory=dict)

    def state_for(self, scope: MarketScope) -> ValidationState:
        return self.validations.get(scope.key(), ValidationState.EXPERIMENT_ONLY)

    def record(self, scope: MarketScope, state: ValidationState) -> None:
        self.validations[scope.key()] = state

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "hypothesis": self.hypothesis,
            "validations": {
                key: value.value for key, value in sorted(self.validations.items())
            },
        }


@dataclass(frozen=True)
class TransferDecision:
    classification: TransferClass
    requires_revalidation: bool
    portable: tuple[str, ...]
    must_revalidate: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["classification"] = self.classification.value
        return payload


class MarketTransferGate:
    """Prevents one market's validation from being silently promoted elsewhere."""

    PORTABLE = (
        "hypothesis",
        "research_method",
        "logging_schema",
        "risk_methodology",
        "failure_history",
    )

    @classmethod
    def evaluate(cls, source: MarketScope, target: MarketScope) -> TransferDecision:
        same_scope = source.key() == target.key()
        same_asset_class = source.asset_class.upper() == target.asset_class.upper()

        if same_scope:
            return TransferDecision(
                classification=TransferClass.SAME_SCOPE_REVALIDATE,
                requires_revalidation=True,
                portable=cls.PORTABLE,
                must_revalidate=(
                    "new_sample_period",
                    "fees",
                    "slippage",
                    "execution_quality",
                ),
            )

        if same_asset_class:
            return TransferDecision(
                classification=TransferClass.SAME_ASSET_CLASS_NEW_VENUE,
                requires_revalidation=True,
                portable=cls.PORTABLE,
                must_revalidate=(
                    "signal_performance",
                    "fees",
                    "slippage",
                    "quote_currency",
                    "liquidity",
                    "microstructure",
                    "tick_and_minimum_order_rules",
                    "execution_timing",
                ),
            )

        return TransferDecision(
            classification=TransferClass.NEW_ASSET_CLASS_FULL_VALIDATION,
            requires_revalidation=True,
            portable=cls.PORTABLE,
            must_revalidate=(
                "signal_performance",
                "market_sessions",
                "fees",
                "slippage",
                "liquidity",
                "microstructure",
                "corporate_actions",
                "gaps",
                "fundamentals",
                "fx",
                "taxes",
                "execution_timing",
            ),
        )


@dataclass(frozen=True)
class MarketObservation:
    venue: str
    symbol: str
    price: float
    observed_at: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Candle:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


GetJson = Callable[[str], Any]


def _urlopen_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


class BinanceSpotPublicMarketData:
    """Read-only Binance Spot public market-data adapter.

    This class deliberately contains no authenticated account or order methods.
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.binance.com",
        get_json: GetJson | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.get_json = get_json or _urlopen_json

    def _url(self, path: str, params: dict[str, Any]) -> str:
        return f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"

    def ticker_price(self, symbol: str) -> MarketObservation:
        normalized = symbol.upper()
        url = self._url("/api/v3/ticker/price", {"symbol": normalized})
        payload = self.get_json(url)
        if not isinstance(payload, dict) or "price" not in payload:
            raise ValueError("unexpected Binance ticker payload")
        price = float(payload["price"])
        if price <= 0:
            raise ValueError("Binance ticker price must be positive")
        return MarketObservation(
            venue="BINANCE_SPOT",
            symbol=normalized,
            price=price,
            observed_at=datetime.now(timezone.utc).isoformat(),
            source=url,
        )

    def klines(self, symbol: str, *, interval: str, limit: int = 61) -> list[Candle]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        normalized = symbol.upper()
        url = self._url(
            "/api/v3/klines",
            {"symbol": normalized, "interval": interval, "limit": limit},
        )
        payload = self.get_json(url)
        if not isinstance(payload, list):
            raise ValueError("unexpected Binance kline payload")

        candles: list[Candle] = []
        for row in payload:
            if not isinstance(row, list) or len(row) < 6:
                raise ValueError("malformed Binance kline row")
            candles.append(
                Candle(
                    open_time_ms=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        return candles


@dataclass(frozen=True)
class TradeEpisode:
    episode_id: str
    strategy_id: str
    mode: str
    venue: str
    symbol: str
    side: str
    decision_at: str
    decision_price: float
    requested_notional: float
    quantity: float
    simulated_fill_price: float
    fee: float
    slippage: float
    provenance: dict[str, Any]
    exit_reason: str | None = None
    gross_pnl: float | None = None
    net_pnl: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def seed_buy_and_hold_benchmark(
    observation: MarketObservation,
    *,
    capital_usd: float,
    fee_rate: float,
) -> dict[str, Any]:
    if capital_usd <= 0:
        raise ValueError("capital_usd must be positive")
    if not 0 <= fee_rate < 1:
        raise ValueError("fee_rate must be in [0, 1)")

    entry_fee = capital_usd * fee_rate
    investable = capital_usd - entry_fee
    quantity = investable / observation.price
    return {
        "type": "BUY_AND_HOLD_BENCHMARK",
        "symbol": observation.symbol,
        "seed_price": observation.price,
        "seed_observed_at": observation.observed_at,
        "capital_usd": capital_usd,
        "fee_rate_assumption": fee_rate,
        "entry_fee_assumption_usd": entry_fee,
        "quantity": quantity,
        "initial_mark_value_usd": quantity * observation.price,
        "source": observation.source,
    }


def sma_trend_control(
    closes: Iterable[float],
    *,
    short_window: int = 20,
    long_window: int = 60,
) -> dict[str, Any]:
    values = [float(value) for value in closes]
    if short_window <= 0 or long_window <= short_window:
        raise ValueError("windows must satisfy 0 < short_window < long_window")
    if len(values) < long_window:
        return {
            "state": "WARMING_UP",
            "signal": "NO_TRADE",
            "bars_available": len(values),
            "bars_required": long_window,
        }

    short_sma = sum(values[-short_window:]) / short_window
    long_sma = sum(values[-long_window:]) / long_window
    latest = values[-1]
    signal = "LONG" if short_sma > long_sma and latest > short_sma else "CASH"
    return {
        "state": "READY",
        "signal": signal,
        "bars_available": len(values),
        "bars_required": long_window,
        "latest_close": latest,
        "short_sma": short_sma,
        "long_sma": long_sma,
        "strategy_role": "INFRASTRUCTURE_BASELINE_NOT_VALIDATED_ALPHA",
    }


def build_trading_floor_snapshot(
    *,
    observation: MarketObservation,
    capital_usd: float = 30.0,
    fee_rate: float = 0.001,
    strategy: StrategyPassport,
    scope: MarketScope,
    trend_control: dict[str, Any] | None = None,
    episodes: list[TradeEpisode] | None = None,
) -> dict[str, Any]:
    benchmark = seed_buy_and_hold_benchmark(
        observation,
        capital_usd=capital_usd,
        fee_rate=fee_rate,
    )
    current_validation = strategy.state_for(scope)
    return {
        "schema": "quantrade_trading_floor_v1",
        "experiment_id": "QT-LIVE-001",
        "mode": "PAPER",
        "live_execution_authorized": False,
        "starting_capital_usd": capital_usd,
        "cash_account_usd": capital_usd,
        "market_observation": observation.as_dict(),
        "market_scope": asdict(scope),
        "strategy_passport": strategy.as_dict(),
        "current_validation": current_validation.value,
        "trend_control": trend_control
        or {
            "state": "WARMING_UP",
            "signal": "NO_TRADE",
            "bars_available": 0,
            "bars_required": 60,
            "strategy_role": "INFRASTRUCTURE_BASELINE_NOT_VALIDATED_ALPHA",
        },
        "benchmark": benchmark,
        "trade_episodes": [episode.as_dict() for episode in (episodes or [])],
        "transfer_rule": "Knowledge may transfer across markets. Validation does not.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
