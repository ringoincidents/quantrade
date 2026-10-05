"""Point-in-time fundamental observation provider contract.

This module defines a stable QuanTrade-owned boundary for external fundamental
data before any specific vendor (for example DART) is integrated.

The contract is intentionally read-only, deterministic, and non-authoritative.
It preserves publication/revision provenance so historical research cannot
silently use information that was unavailable at the Case as-of time.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import math
from typing import Protocol, Sequence

from quantrade.capabilities.thesis_contract import Observation, SourceKind


class FundamentalEvidenceError(ValueError):
    """Raised when point-in-time fundamental evidence violates the contract."""


@dataclass(frozen=True)
class FundamentalProviderMetadata:
    provider_id: str
    provider_version: str
    source_license: str
    network_required: bool
    model_required: bool
    point_in_time_capable: bool
    capital_authority: bool = False


@dataclass(frozen=True)
class FundamentalObservation:
    observation_id: str
    asset_id: str
    metric_key: str
    value: float
    unit: str
    currency: str | None
    fiscal_period_end: str
    published_at: str
    retrieved_at: str
    source_provider: str
    source_document_id: str
    source_ref: str
    evidence_ref: str
    revision_id: str | None = None
    revision_of: str | None = None
    restated: bool = False
    normalization_method: str = "RAW_REPORTED"
    published_at_precision: str = "TIMESTAMP"


@dataclass(frozen=True)
class FundamentalQuery:
    asset_id: str
    as_of: str
    metric_keys: tuple[str, ...] = ()
    fiscal_period_end_from: str | None = None
    fiscal_period_end_to: str | None = None


@dataclass(frozen=True)
class FundamentalQueryResult:
    schema: str
    query: dict
    provider: dict
    observations: tuple[dict, ...]
    excluded_future_observation_ids: tuple[str, ...]
    revision_resolution: tuple[dict, ...]
    authority: dict


class FundamentalObservationProvider(Protocol):
    @property
    def metadata(self) -> FundamentalProviderMetadata:
        ...

    def query(self, request: FundamentalQuery) -> FundamentalQueryResult:
        ...


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FundamentalEvidenceError(f"{field_name} is required")
    return value.strip()


def _parse_time(value: str, field_name: str) -> datetime:
    raw = _required_text(value, field_name).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise FundamentalEvidenceError(
            f"{field_name} must be valid ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise FundamentalEvidenceError(
            f"{field_name} must include timezone information"
        )
    return parsed.astimezone(timezone.utc)


def _parse_date(value: str, field_name: str) -> date:
    raw = _required_text(value, field_name)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise FundamentalEvidenceError(
            f"{field_name} must be YYYY-MM-DD"
        ) from exc


def _validate_observation(item: FundamentalObservation) -> None:
    for field_name, value in (
        ("observation_id", item.observation_id),
        ("asset_id", item.asset_id),
        ("metric_key", item.metric_key),
        ("unit", item.unit),
        ("source_provider", item.source_provider),
        ("source_document_id", item.source_document_id),
        ("source_ref", item.source_ref),
        ("evidence_ref", item.evidence_ref),
        ("normalization_method", item.normalization_method),
        ("published_at_precision", item.published_at_precision),
    ):
        _required_text(value, field_name)

    if isinstance(item.value, bool) or not isinstance(item.value, (int, float)):
        raise FundamentalEvidenceError("value must be numeric")
    if not math.isfinite(float(item.value)):
        raise FundamentalEvidenceError("value must be finite")

    if item.currency is not None:
        _required_text(item.currency, "currency")

    _parse_date(item.fiscal_period_end, "fiscal_period_end")
    published = _parse_time(item.published_at, "published_at")
    retrieved = _parse_time(item.retrieved_at, "retrieved_at")
    if published > retrieved:
        raise FundamentalEvidenceError(
            f"observation {item.observation_id} published_at cannot be "
            "after retrieved_at"
        )

    if item.revision_id is not None:
        _required_text(item.revision_id, "revision_id")
    if item.revision_of is not None:
        _required_text(item.revision_of, "revision_of")
        if item.revision_of == item.observation_id:
            raise FundamentalEvidenceError(
                "revision_of cannot reference the same observation_id"
            )


def _validate_metadata(metadata: FundamentalProviderMetadata) -> None:
    _required_text(metadata.provider_id, "provider_id")
    _required_text(metadata.provider_version, "provider_version")
    _required_text(metadata.source_license, "source_license")
    if metadata.model_required:
        raise FundamentalEvidenceError(
            "fundamental observation provider must not require a model"
        )
    if metadata.capital_authority:
        raise FundamentalEvidenceError(
            "fundamental observation provider cannot have capital authority"
        )


def _period_in_range(
    period_end: str,
    lower: str | None,
    upper: str | None,
) -> bool:
    target = _parse_date(period_end, "fiscal_period_end")
    if lower is not None and target < _parse_date(
        lower,
        "fiscal_period_end_from",
    ):
        return False
    if upper is not None and target > _parse_date(
        upper,
        "fiscal_period_end_to",
    ):
        return False
    return True


def _revision_key(item: FundamentalObservation) -> tuple[str, str, str]:
    return (item.asset_id, item.metric_key, item.fiscal_period_end)


class StaticFundamentalObservationProvider:
    """In-memory provider used for deterministic contract tests and replay.

    It intentionally implements the same point-in-time revision selection a
    future DART/provider adapter must satisfy.
    """

    def __init__(
        self,
        observations: Sequence[FundamentalObservation],
        *,
        metadata: FundamentalProviderMetadata | None = None,
    ) -> None:
        self._metadata = metadata or FundamentalProviderMetadata(
            provider_id="STATIC_FUNDAMENTAL_FIXTURE",
            provider_version="1",
            source_license="TEST_FIXTURE",
            network_required=False,
            model_required=False,
            point_in_time_capable=True,
            capital_authority=False,
        )
        _validate_metadata(self._metadata)

        ids: set[str] = set()
        items = tuple(observations)
        for item in items:
            _validate_observation(item)
            if item.observation_id in ids:
                raise FundamentalEvidenceError(
                    f"duplicate observation_id: {item.observation_id}"
                )
            ids.add(item.observation_id)
            if item.source_provider != self._metadata.provider_id:
                raise FundamentalEvidenceError(
                    "observation source_provider must match provider metadata"
                )
        self._observations = items

    @property
    def metadata(self) -> FundamentalProviderMetadata:
        return self._metadata

    def query(self, request: FundamentalQuery) -> FundamentalQueryResult:
        asset_id = _required_text(request.asset_id, "asset_id")
        as_of = _parse_time(request.as_of, "as_of")

        metric_keys = tuple(
            _required_text(item, "metric_key")
            for item in request.metric_keys
        )
        if len(metric_keys) != len(set(metric_keys)):
            raise FundamentalEvidenceError(
                "metric_keys must be unique"
            )
        if request.fiscal_period_end_from is not None:
            _parse_date(
                request.fiscal_period_end_from,
                "fiscal_period_end_from",
            )
        if request.fiscal_period_end_to is not None:
            _parse_date(
                request.fiscal_period_end_to,
                "fiscal_period_end_to",
            )
        if (
            request.fiscal_period_end_from is not None
            and request.fiscal_period_end_to is not None
            and _parse_date(
                request.fiscal_period_end_from,
                "fiscal_period_end_from",
            )
            > _parse_date(
                request.fiscal_period_end_to,
                "fiscal_period_end_to",
            )
        ):
            raise FundamentalEvidenceError(
                "fiscal period range is reversed"
            )

        candidates = [
            item
            for item in self._observations
            if item.asset_id == asset_id
            and (not metric_keys or item.metric_key in metric_keys)
            and _period_in_range(
                item.fiscal_period_end,
                request.fiscal_period_end_from,
                request.fiscal_period_end_to,
            )
        ]

        eligible = [
            item
            for item in candidates
            if _parse_time(item.published_at, "published_at") <= as_of
        ]
        future = [
            item
            for item in candidates
            if _parse_time(item.published_at, "published_at") > as_of
        ]

        by_key: dict[
            tuple[str, str, str],
            list[FundamentalObservation],
        ] = {}
        for item in eligible:
            by_key.setdefault(_revision_key(item), []).append(item)

        selected: list[FundamentalObservation] = []
        revision_resolution: list[dict] = []
        for key in sorted(by_key):
            versions = sorted(
                by_key[key],
                key=lambda item: (
                    _parse_time(item.published_at, "published_at"),
                    item.observation_id,
                ),
            )
            winner = versions[-1]
            selected.append(winner)
            revision_resolution.append(
                {
                    "asset_id": key[0],
                    "metric_key": key[1],
                    "fiscal_period_end": key[2],
                    "eligible_version_ids": tuple(
                        item.observation_id for item in versions
                    ),
                    "selected_observation_id": winner.observation_id,
                    "future_revision_excluded": any(
                        _revision_key(item) == key
                        for item in future
                    ),
                }
            )

        selected.sort(
            key=lambda item: (
                item.fiscal_period_end,
                item.metric_key,
                item.observation_id,
            )
        )
        future_ids = tuple(
            sorted(item.observation_id for item in future)
        )

        return FundamentalQueryResult(
            schema="quantrade_fundamental_observation_query_v1",
            query={
                "asset_id": request.asset_id,
                "as_of": request.as_of,
                "metric_keys": metric_keys,
                "fiscal_period_end_from": request.fiscal_period_end_from,
                "fiscal_period_end_to": request.fiscal_period_end_to,
            },
            provider=asdict(self._metadata),
            observations=tuple(
                {
                    **asdict(item),
                    "point_in_time_selected": True,
                    "canonical_evidence_created": False,
                    "investment_authority": False,
                }
                for item in selected
            ),
            excluded_future_observation_ids=future_ids,
            revision_resolution=tuple(revision_resolution),
            authority={
                "model_called": False,
                "canonical_evidence_created": False,
                "thesis_created": False,
                "portfolio_proposal_created": False,
                "risk_opinion_created": False,
                "committee_decision_created": False,
                "execution_authorized": False,
                "live_order_possible": False,
            },
        )


def to_thesis_observation(
    observation: FundamentalObservation,
) -> Observation:
    """Adapt one PIT-selected fundamental value into a Thesis Observation ref.

    This adapter references external evidence; it does not create canonical
    Evidence inside QuanTrade.
    """
    _validate_observation(observation)
    statement = (
        f"{observation.metric_key}={observation.value} "
        f"{observation.unit}"
    )
    if observation.currency:
        statement += f" {observation.currency}"

    return Observation(
        observation_id=observation.observation_id,
        statement=statement,
        source_ref=observation.evidence_ref,
        source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
        observed_at=observation.published_at,
    )
