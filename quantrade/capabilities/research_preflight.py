"""Deterministic preflight gate for QuanTrade research missions.

The gate classifies dependency state before a mission starts expensive or
authoritative work. It distinguishes absent material, unregistered identifiers,
access denial, search failure, external outage, maintenance, rate limiting, and
invalid responses instead of collapsing all of them into a generic retry.

It has no authority to approve capital, grant permissions, or reinterpret a
Founder approval as tool access.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


class ResearchPreflightError(ValueError):
    """Raised when preflight inputs violate the contract."""


GOOD_STATUSES = {
    "AVAILABLE",
    "VERIFIED",
    "VERIFIED_CACHE",
}

KNOWN_STATUSES = GOOD_STATUSES | {
    "MISSING",
    "UNREGISTERED",
    "ACCESS_DENIED",
    "SEARCH_FAILED",
    "NETWORK_UNAVAILABLE",
    "MAINTENANCE",
    "RATE_LIMITED",
    "INVALID_RESPONSE",
    "UNKNOWN",
}

FAILURE_CLASS = {
    "MISSING": "MATERIAL_ABSENT",
    "UNREGISTERED": "UNREGISTERED",
    "ACCESS_DENIED": "ACCESS_DENIED",
    "SEARCH_FAILED": "SEARCH_FAILED",
    "NETWORK_UNAVAILABLE": "EXTERNAL_UNAVAILABLE",
    "MAINTENANCE": "EXTERNAL_UNAVAILABLE",
    "RATE_LIMITED": "EXTERNAL_UNAVAILABLE",
    "INVALID_RESPONSE": "SEARCH_FAILED",
    "UNKNOWN": "UNKNOWN",
}


@dataclass(frozen=True)
class DependencyCheck:
    dependency_id: str
    dependency_kind: str
    required: bool
    status: str
    detail: str
    source_ref: str
    checked_at: str


@dataclass(frozen=True)
class ResearchPreflightInput:
    mission_id: str
    checks: tuple[DependencyCheck, ...]


@dataclass(frozen=True)
class ResearchPreflightArtifact:
    schema: str
    mission_id: str
    status: str
    execute_allowed: bool
    checks: tuple[dict, ...]
    blockers: tuple[dict, ...]
    warnings: tuple[dict, ...]
    failure_classes: tuple[str, ...]
    validation: dict
    authority: dict


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchPreflightError(f"{field_name} is required")
    return value.strip()


def evaluate_research_preflight(
    request: ResearchPreflightInput,
) -> ResearchPreflightArtifact:
    mission_id = _text(request.mission_id, "mission_id")
    if not request.checks:
        raise ResearchPreflightError(
            "at least one dependency check is required"
        )

    ids: set[str] = set()
    normalized: list[dict] = []
    blockers: list[dict] = []
    warnings: list[dict] = []
    failure_classes: set[str] = set()

    for check in request.checks:
        dependency_id = _text(
            check.dependency_id,
            "dependency_id",
        )
        if dependency_id in ids:
            raise ResearchPreflightError(
                f"duplicate dependency_id: {dependency_id}"
            )
        ids.add(dependency_id)

        dependency_kind = _text(
            check.dependency_kind,
            "dependency_kind",
        )
        if not isinstance(check.required, bool):
            raise ResearchPreflightError(
                "required must be boolean"
            )
        status = _text(check.status, "status")
        if status not in KNOWN_STATUSES:
            raise ResearchPreflightError(
                f"unsupported dependency status: {status}"
            )
        detail = _text(check.detail, "detail")
        source_ref = _text(check.source_ref, "source_ref")
        checked_at = _text(check.checked_at, "checked_at")

        row = {
            "dependency_id": dependency_id,
            "dependency_kind": dependency_kind,
            "required": check.required,
            "status": status,
            "detail": detail,
            "source_ref": source_ref,
            "checked_at": checked_at,
        }
        normalized.append(row)

        if status in GOOD_STATUSES:
            continue

        failure_class = FAILURE_CLASS[status]
        row_with_class = {
            **row,
            "failure_class": failure_class,
        }
        if check.required:
            blockers.append(row_with_class)
            failure_classes.add(failure_class)
        else:
            warnings.append(row_with_class)

    if blockers:
        status = "BLOCKED"
        execute_allowed = False
    elif warnings:
        status = "READY_WITH_WARNINGS"
        execute_allowed = True
    else:
        status = "READY"
        execute_allowed = True

    return ResearchPreflightArtifact(
        schema="quantrade_research_preflight_v1",
        mission_id=mission_id,
        status=status,
        execute_allowed=execute_allowed,
        checks=tuple(normalized),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        failure_classes=tuple(sorted(failure_classes)),
        validation={
            "required_dependency_count": sum(
                1 for row in normalized if row["required"]
            ),
            "blocking_dependency_count": len(blockers),
            "warning_dependency_count": len(warnings),
            "generic_retry_authorized": False,
            "founder_approval_interpreted_as_tool_permission": False,
            "failure_taxonomy_preserved": True,
        },
        authority={
            "model_called": False,
            "tool_permission_granted": False,
            "secret_access_granted": False,
            "canonical_evidence_created": False,
            "valuation_created": False,
            "portfolio_proposal_created": False,
            "committee_decision_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )
