"""Replaceable deterministic feature-provider boundary for QuanTrade.

Provider outputs are observations only. They are not canonical Evidence,
investment decisions, risk limits, or execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ProviderMetadata:
    provider_id: str
    capability: str
    implementation: str
    version_or_revision: str
    license: str
    deterministic: bool = True
    network_access: bool = False
    capital_effect: bool = False
    evidence_effect: str = "NON_CANONICAL"
    status: str = "SANDBOX"


@dataclass(frozen=True)
class FeatureObservation:
    schema: str
    provider: dict
    input_count: int
    features: dict[str, float | None]
    authority: dict[str, bool]


class FeatureProvider(Protocol):
    metadata: ProviderMetadata

    def compute(self, closes: Sequence[float]) -> FeatureObservation:
        ...


def _validate(closes: Sequence[float]) -> list[float]:
    values = [float(v) for v in closes]
    if len(values) < 2:
        raise ValueError("at least two close values are required")
    if any(v <= 0 for v in values):
        raise ValueError("close values must be positive")
    return values


def _sma(values: Sequence[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _returns(values: Sequence[float]) -> list[float]:
    return [(b / a) - 1.0 for a, b in zip(values, values[1:])]


class NativeFeatureProvider:
    """Small dependency-free reference implementation.

    It intentionally computes only commodity measurements. Richer OSS adapters
    can replace it without changing QuanTrade-facing semantics.
    """

    metadata = ProviderMetadata(
        provider_id="quantrade.native.features.v1",
        capability="FeatureProvider",
        implementation="quantrade-native-reference",
        version_or_revision="v1",
        license="repository-license",
        status="SANDBOX",
    )

    def compute(self, closes: Sequence[float]) -> FeatureObservation:
        values = _validate(closes)
        returns = _returns(values)
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        features = {
            "return_1": returns[-1],
            "return_total": values[-1] / values[0] - 1.0,
            "sma_5": _sma(values, 5),
            "sma_20": _sma(values, 20),
            "realized_volatility": sqrt(variance),
        }
        return FeatureObservation(
            schema="quantrade_feature_observation_v1",
            provider=asdict(self.metadata),
            input_count=len(values),
            features=features,
            authority={
                "canonical_evidence_created": False,
                "risk_limit_changed": False,
                "investment_decision_created": False,
                "execution_authorized": False,
            },
        )


def compare_providers(
    closes: Sequence[float],
    providers: Sequence[FeatureProvider],
) -> dict:
    """Run identical input through providers and retain provenance.

    This is the benchmark seam future OSS adapters use. It deliberately does
    not choose a winner or promote any output to canonical Evidence.
    """
    if len(providers) < 2:
        raise ValueError("provider comparison requires at least two providers")
    observations = [provider.compute(closes) for provider in providers]
    return {
        "schema": "quantrade_feature_provider_comparison_v1",
        "input_count": len(closes),
        "observations": [asdict(item) for item in observations],
        "authority": {
            "provider_promoted": False,
            "canonical_evidence_created": False,
            "execution_authorized": False,
        },
    }
