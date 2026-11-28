"""Valuation-method applicability gate for QuanTrade.

A method must be semantically resolvable and economically valid for its
mathematical domain before valuation arithmetic is allowed.

This gate does not choose a substitute method and has no capital authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


class ValuationMethodApplicabilityError(ValueError):
    """Raised when method applicability inputs violate the contract."""


@dataclass(frozen=True)
class DomainCheck:
    check_id: str
    passed: bool
    failure_reason: str
    basis_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValuationMethodApplicabilityInput:
    case_id: str
    method_id: str
    semantic_status: str
    semantic_artifact_ref: str
    domain_checks: tuple[DomainCheck, ...]


@dataclass(frozen=True)
class ValuationMethodApplicabilityArtifact:
    schema: str
    case_id: str
    method_id: str
    status: str
    reasons: tuple[str, ...]
    semantic_status: str
    domain_checks: tuple[dict, ...]
    authority: dict


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValuationMethodApplicabilityError(
            f"{field_name} is required"
        )
    return value.strip()


def evaluate_method_applicability(
    request: ValuationMethodApplicabilityInput,
) -> ValuationMethodApplicabilityArtifact:
    case_id = _text(request.case_id, "case_id")
    method_id = _text(request.method_id, "method_id")
    semantic_status = _text(
        request.semantic_status,
        "semantic_status",
    )
    _text(
        request.semantic_artifact_ref,
        "semantic_artifact_ref",
    )

    if semantic_status not in {"READY", "MISSING", "AMBIGUOUS"}:
        raise ValuationMethodApplicabilityError(
            f"unsupported semantic_status: {semantic_status}"
        )

    reasons: list[str] = []
    if semantic_status == "MISSING":
        reasons.append("SEMANTIC_METRIC_MISSING")
    elif semantic_status == "AMBIGUOUS":
        reasons.append("SEMANTIC_METRIC_AMBIGUOUS")

    ids: set[str] = set()
    checks: list[dict] = []
    for check in request.domain_checks:
        check_id = _text(check.check_id, "check_id")
        if check_id in ids:
            raise ValuationMethodApplicabilityError(
                f"duplicate check_id: {check_id}"
            )
        ids.add(check_id)
        if not isinstance(check.passed, bool):
            raise ValuationMethodApplicabilityError(
                "domain check passed must be boolean"
            )
        failure_reason = _text(
            check.failure_reason,
            "failure_reason",
        )
        for ref in check.basis_refs:
            _text(ref, "basis_ref")
        if not check.passed:
            reasons.append(failure_reason)
        checks.append(asdict(check))

    if semantic_status != "READY":
        status = "NOT_APPLICABLE"
    elif reasons:
        status = "NOT_APPLICABLE"
    else:
        status = "READY"

    return ValuationMethodApplicabilityArtifact(
        schema="quantrade_valuation_method_applicability_v1",
        case_id=case_id,
        method_id=method_id,
        status=status,
        reasons=tuple(reasons),
        semantic_status=semantic_status,
        domain_checks=tuple(checks),
        authority={
            "model_called": False,
            "canonical_evidence_created": False,
            "valuation_created": False,
            "substitute_method_selected": False,
            "portfolio_proposal_created": False,
            "target_weight_set": False,
            "committee_decision_created": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )
