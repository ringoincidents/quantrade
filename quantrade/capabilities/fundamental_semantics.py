"""Semantic fundamental metric applicability for QuanTrade.

A real issuer may report the same IFRS semantic account under different DART
statement divisions (for example IS vs CIS). This module resolves an explicitly
allowed semantic family without falling back to account-name guessing.

It is a deterministic applicability layer. It does not create Evidence,
valuation, Portfolio authority, or execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re


class SemanticMetricError(ValueError):
    """Raised when semantic metric requirements are invalid."""


@dataclass(frozen=True)
class SemanticMetricRequirement:
    requirement_id: str
    account_id: str
    allowed_statement_divisions: tuple[str, ...]
    amount_suffix: str
    fiscal_period_ends: tuple[str, ...]


@dataclass(frozen=True)
class SemanticMetricApplicabilityInput:
    case_id: str
    observations: tuple[dict, ...]
    requirements: tuple[SemanticMetricRequirement, ...]


@dataclass(frozen=True)
class SemanticMetricApplicabilityArtifact:
    schema: str
    case_id: str
    status: str
    resolved: tuple[dict, ...]
    missing: tuple[dict, ...]
    ambiguous: tuple[dict, ...]
    requested_metric_keys: tuple[str, ...]
    validation: dict
    authority: dict


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticMetricError(f"{field_name} is required")
    return value.strip()


def requirement_metric_keys(
    requirement: SemanticMetricRequirement,
) -> tuple[str, ...]:
    account_id = _text(requirement.account_id, "account_id")
    suffix = _text(requirement.amount_suffix, "amount_suffix")
    divisions = tuple(
        _text(value, "statement division")
        for value in requirement.allowed_statement_divisions
    )
    if not divisions:
        raise SemanticMetricError(
            "allowed_statement_divisions must not be empty"
        )
    if len(divisions) != len(set(divisions)):
        raise SemanticMetricError(
            "allowed_statement_divisions must be unique"
        )
    return tuple(
        f"DART_ACCOUNT:{account_id}:{division}:{suffix}"
        for division in divisions
    )


def collect_requested_metric_keys(
    requirements: tuple[SemanticMetricRequirement, ...],
) -> tuple[str, ...]:
    keys: list[str] = []
    seen: set[str] = set()
    for requirement in requirements:
        for key in requirement_metric_keys(requirement):
            if key not in seen:
                keys.append(key)
                seen.add(key)
    return tuple(keys)


def evaluate_semantic_metric_applicability(
    request: SemanticMetricApplicabilityInput,
) -> SemanticMetricApplicabilityArtifact:
    case_id = _text(request.case_id, "case_id")
    if not request.requirements:
        raise SemanticMetricError(
            "at least one semantic metric requirement is required"
        )

    requirement_ids: set[str] = set()
    normalized_requirements: list[tuple[SemanticMetricRequirement, tuple[str, ...]]] = []
    for requirement in request.requirements:
        rid = _text(requirement.requirement_id, "requirement_id")
        if rid in requirement_ids:
            raise SemanticMetricError(
                f"duplicate requirement_id: {rid}"
            )
        requirement_ids.add(rid)
        periods = tuple(
            _text(value, "fiscal_period_end")
            for value in requirement.fiscal_period_ends
        )
        if not periods:
            raise SemanticMetricError(
                f"{rid} requires fiscal_period_ends"
            )
        if len(periods) != len(set(periods)):
            raise SemanticMetricError(
                f"{rid} fiscal_period_ends must be unique"
            )
        keys = requirement_metric_keys(requirement)
        normalized_requirements.append((requirement, keys))

    observations: list[dict] = []
    for item in request.observations:
        if not isinstance(item, dict):
            raise SemanticMetricError(
                "observations must be mapping artifacts"
            )
        metric_key = _text(item.get("metric_key"), "observation metric_key")
        period = _text(
            item.get("fiscal_period_end"),
            "observation fiscal_period_end",
        )
        observation_id = _text(
            item.get("observation_id"),
            "observation_id",
        )
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SemanticMetricError(
                f"observation {observation_id} value must be numeric"
            )
        if not math.isfinite(float(value)):
            raise SemanticMetricError(
                f"observation {observation_id} value must be finite"
            )
        observations.append(
            {
                **item,
                "metric_key": metric_key,
                "fiscal_period_end": period,
                "observation_id": observation_id,
            }
        )

    resolved: list[dict] = []
    missing: list[dict] = []
    ambiguous: list[dict] = []

    for requirement, candidate_keys in normalized_requirements:
        for period in requirement.fiscal_period_ends:
            matches = [
                item
                for item in observations
                if item["fiscal_period_end"] == period
                and item["metric_key"] in candidate_keys
            ]
            if len(matches) == 1:
                selected = matches[0]
                statement_division = selected["metric_key"].split(":")[-2]
                resolved.append(
                    {
                        "requirement_id": requirement.requirement_id,
                        "account_id": requirement.account_id,
                        "fiscal_period_end": period,
                        "actual_metric_key": selected["metric_key"],
                        "actual_statement_division": statement_division,
                        "observation_id": selected["observation_id"],
                        "value": float(selected["value"]),
                        "unit": selected.get("unit"),
                        "published_at": selected.get("published_at"),
                        "evidence_ref": selected.get("evidence_ref"),
                        "semantic_match_kind": "EXACT_ACCOUNT_ID_ALLOWED_DIVISION",
                    }
                )
            elif not matches:
                missing.append(
                    {
                        "requirement_id": requirement.requirement_id,
                        "account_id": requirement.account_id,
                        "fiscal_period_end": period,
                        "accepted_metric_keys": candidate_keys,
                    }
                )
            else:
                ambiguous.append(
                    {
                        "requirement_id": requirement.requirement_id,
                        "account_id": requirement.account_id,
                        "fiscal_period_end": period,
                        "matching_observation_ids": tuple(
                            item["observation_id"] for item in matches
                        ),
                        "matching_metric_keys": tuple(
                            item["metric_key"] for item in matches
                        ),
                    }
                )

    if ambiguous:
        status = "AMBIGUOUS"
    elif missing:
        status = "MISSING"
    else:
        status = "READY"

    return SemanticMetricApplicabilityArtifact(
        schema="quantrade_semantic_metric_applicability_v1",
        case_id=case_id,
        status=status,
        resolved=tuple(resolved),
        missing=tuple(missing),
        ambiguous=tuple(ambiguous),
        requested_metric_keys=collect_requested_metric_keys(
            request.requirements
        ),
        validation={
            "requirement_count": len(request.requirements),
            "resolved_count": len(resolved),
            "missing_count": len(missing),
            "ambiguous_count": len(ambiguous),
            "account_name_fallback_used": False,
            "issuer_specific_alias_inference_used": False,
            "statement_division_variants_must_be_predeclared": True,
            "arithmetic_only": True,
        },
        authority={
            "model_called": False,
            "canonical_evidence_created": False,
            "valuation_created": False,
            "portfolio_proposal_created": False,
            "target_weight_set": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )


# Reusable accounting-semantic requirements for non-financial operating
# companies. These are semantic families, not issuer-specific aliases.
BASIC_EPS_ACCOUNT_ID = "ifrs-full_BasicEarningsLossPerShare"
OWNER_PROFIT_ACCOUNT_ID = "ifrs-full_ProfitLossAttributableToOwnersOfParent"
OPERATING_CASH_FLOW_ACCOUNT_ID = (
    "ifrs-full_CashFlowsFromUsedInOperatingActivities"
)
PPE_PURCHASE_ACCOUNT_ID = (
    "ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
)
INTANGIBLE_PURCHASE_ACCOUNT_ID = (
    "ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"
)
PARENT_EQUITY_ACCOUNT_ID = "ifrs-full_EquityAttributableToOwnersOfParent"
