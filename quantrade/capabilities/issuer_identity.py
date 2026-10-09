"""Verified issuer identity registry for QuanTrade.

Issuer identity is infrastructure, not economic Evidence.

The registry stores stable external identifiers (for example KRX stock code ↔
Open DART corp_code) only when the mapping has provenance and a prior
verification record. A cached mapping still has no capital authority and may be
rejected by a later live filing mismatch.

The design prevents a transient corporation-code endpoint outage from becoming
an unnecessary dependency for every Investment Case while preserving fail-
closed identity checks.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re


class IssuerIdentityError(ValueError):
    """Raised when issuer identity provenance or consistency is invalid."""


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "issuer_identity_registry_v1.json"
)


@dataclass(frozen=True)
class IssuerIdentityRecord:
    asset_id: str
    stock_code: str
    provider_id: str
    external_id: str
    source_kind: str
    source_ref: str
    verified_at: str
    verification_kind: str
    verification_ref: str


@dataclass(frozen=True)
class IssuerIdentityRegistry:
    schema: str
    version: str
    records: tuple[IssuerIdentityRecord, ...]


@dataclass(frozen=True)
class IssuerIdentityResolution:
    schema: str
    asset_id: str
    status: str
    provider_id: str | None
    stock_code: str | None
    external_id: str | None
    provenance: dict | None
    authority: dict


@dataclass(frozen=True)
class IssuerIdentityVerification:
    schema: str
    asset_id: str
    status: str
    expected_stock_code: str
    observed_stock_code: str
    expected_external_id: str
    observed_external_id: str | None
    filing_ref: str
    authority: dict


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IssuerIdentityError(f"{field_name} is required")
    return value.strip()


def _validate_record(record: IssuerIdentityRecord) -> None:
    asset_id = _text(record.asset_id, "asset_id")
    stock_code = _text(record.stock_code, "stock_code")
    provider_id = _text(record.provider_id, "provider_id")
    external_id = _text(record.external_id, "external_id")
    _text(record.source_kind, "source_kind")
    _text(record.source_ref, "source_ref")
    _text(record.verified_at, "verified_at")
    _text(record.verification_kind, "verification_kind")
    _text(record.verification_ref, "verification_ref")

    if not re.fullmatch(r"KRX:\d{6}", asset_id):
        raise IssuerIdentityError(
            "asset_id must use KRX:<6-digit-code>"
        )
    if not re.fullmatch(r"\d{6}", stock_code):
        raise IssuerIdentityError(
            "stock_code must be a six-digit KRX code"
        )
    if asset_id != f"KRX:{stock_code}":
        raise IssuerIdentityError(
            "asset_id and stock_code must agree"
        )
    if provider_id == "OPEN_DART":
        if not re.fullmatch(r"\d{8}", external_id):
            raise IssuerIdentityError(
                "Open DART external_id must be eight digits"
            )


def validate_registry(
    registry: IssuerIdentityRegistry,
) -> IssuerIdentityRegistry:
    if registry.schema != "quantrade_issuer_identity_registry_v1":
        raise IssuerIdentityError(
            "unsupported issuer identity registry schema"
        )
    _text(registry.version, "version")

    by_asset: dict[str, IssuerIdentityRecord] = {}
    by_provider_external: dict[tuple[str, str], IssuerIdentityRecord] = {}
    for record in registry.records:
        _validate_record(record)
        if record.asset_id in by_asset:
            raise IssuerIdentityError(
                f"duplicate asset_id: {record.asset_id}"
            )
        key = (record.provider_id, record.external_id)
        if key in by_provider_external:
            raise IssuerIdentityError(
                "duplicate provider external identity: "
                f"{record.provider_id}:{record.external_id}"
            )
        by_asset[record.asset_id] = record
        by_provider_external[key] = record
    return registry


def load_identity_registry(
    path: str | Path = DEFAULT_REGISTRY_PATH,
) -> IssuerIdentityRegistry:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IssuerIdentityError(
            f"unable to load issuer identity registry: {source}"
        ) from exc

    if not isinstance(payload, dict):
        raise IssuerIdentityError(
            "issuer identity registry root must be an object"
        )
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise IssuerIdentityError(
            "issuer identity registry records must be an array"
        )
    registry = IssuerIdentityRegistry(
        schema=str(payload.get("schema", "")),
        version=str(payload.get("version", "")),
        records=tuple(
            IssuerIdentityRecord(
                asset_id=str(row.get("asset_id", "")),
                stock_code=str(row.get("stock_code", "")),
                provider_id=str(row.get("provider_id", "")),
                external_id=str(row.get("external_id", "")),
                source_kind=str(row.get("source_kind", "")),
                source_ref=str(row.get("source_ref", "")),
                verified_at=str(row.get("verified_at", "")),
                verification_kind=str(
                    row.get("verification_kind", "")
                ),
                verification_ref=str(
                    row.get("verification_ref", "")
                ),
            )
            for row in rows
            if isinstance(row, dict)
        ),
    )
    if len(registry.records) != len(rows):
        raise IssuerIdentityError(
            "issuer identity registry contains non-object record"
        )
    return validate_registry(registry)


def resolve_verified_issuer_identity(
    registry: IssuerIdentityRegistry,
    *,
    asset_id: str,
    provider_id: str = "OPEN_DART",
) -> IssuerIdentityResolution:
    validate_registry(registry)
    wanted_asset = _text(asset_id, "asset_id")
    wanted_provider = _text(provider_id, "provider_id")

    matches = [
        record
        for record in registry.records
        if record.asset_id == wanted_asset
        and record.provider_id == wanted_provider
    ]
    if not matches:
        return IssuerIdentityResolution(
            schema="quantrade_issuer_identity_resolution_v1",
            asset_id=wanted_asset,
            status="NOT_REGISTERED",
            provider_id=None,
            stock_code=None,
            external_id=None,
            provenance=None,
            authority=_authority(),
        )
    if len(matches) != 1:
        raise IssuerIdentityError(
            "verified identity resolution must be unique"
        )
    record = matches[0]
    return IssuerIdentityResolution(
        schema="quantrade_issuer_identity_resolution_v1",
        asset_id=wanted_asset,
        status="VERIFIED_CACHED_IDENTITY",
        provider_id=record.provider_id,
        stock_code=record.stock_code,
        external_id=record.external_id,
        provenance={
            "source_kind": record.source_kind,
            "source_ref": record.source_ref,
            "verified_at": record.verified_at,
            "verification_kind": record.verification_kind,
            "verification_ref": record.verification_ref,
            "registry_version": registry.version,
        },
        authority=_authority(),
    )


def verify_identity_against_filing(
    record: IssuerIdentityRecord,
    *,
    observed_stock_code: str,
    observed_external_id: str | None,
    filing_ref: str,
) -> IssuerIdentityVerification:
    _validate_record(record)
    stock = _text(observed_stock_code, "observed_stock_code")
    ref = _text(filing_ref, "filing_ref")
    if not re.fullmatch(r"\d{6}", stock):
        raise IssuerIdentityError(
            "observed_stock_code must be six digits"
        )

    external = None
    if observed_external_id is not None:
        external = _text(
            observed_external_id,
            "observed_external_id",
        )

    status = "VERIFIED"
    if stock != record.stock_code:
        status = "MISMATCH"
    if external is not None and external != record.external_id:
        status = "MISMATCH"

    return IssuerIdentityVerification(
        schema="quantrade_issuer_identity_verification_v1",
        asset_id=record.asset_id,
        status=status,
        expected_stock_code=record.stock_code,
        observed_stock_code=stock,
        expected_external_id=record.external_id,
        observed_external_id=external,
        filing_ref=ref,
        authority=_authority(),
    )


def dart_override_from_resolution(
    resolution: IssuerIdentityResolution,
) -> dict[str, str]:
    if resolution.status != "VERIFIED_CACHED_IDENTITY":
        raise IssuerIdentityError(
            "DART override requires VERIFIED_CACHED_IDENTITY"
        )
    if resolution.stock_code is None or resolution.external_id is None:
        raise IssuerIdentityError(
            "verified resolution lacks identifier fields"
        )
    return {
        resolution.stock_code: resolution.external_id,
    }


def _authority() -> dict:
    return {
        "model_called": False,
        "canonical_evidence_created": False,
        "economic_observation_created": False,
        "valuation_created": False,
        "portfolio_proposal_created": False,
        "target_weight_set": False,
        "committee_decision_created": False,
        "execution_authorized": False,
        "live_order_possible": False,
    }
