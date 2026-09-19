from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Materiality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EscalationAction(str, Enum):
    INTERNAL_LOG = "INTERNAL_LOG"
    OPEN_CASE_LOW = "OPEN_CASE_LOW"
    OPEN_CASE_MEDIUM = "OPEN_CASE_MEDIUM"
    OPEN_CASE_HIGH = "OPEN_CASE_HIGH"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    RESEARCH = "RESEARCH"
    PORTFOLIO_REVIEW = "PORTFOLIO_REVIEW"
    RISK_REVIEW = "RISK_REVIEW"
    ADVERSARIAL_REVIEW = "ADVERSARIAL_REVIEW"
    COMMITTEE = "COMMITTEE"
    FOUNDER_PENDING = "FOUNDER_PENDING"
    DECIDED = "DECIDED"
    DECISION_MANAGEMENT = "DECISION_MANAGEMENT"
    EXECUTION_PENDING = "EXECUTION_PENDING"
    OUTCOME_TRACKING = "OUTCOME_TRACKING"
    CLOSED = "CLOSED"


class DecisionAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    HOLD = "HOLD"
    RESEARCH = "RESEARCH"


class TimingMode(str, Enum):
    NOW = "NOW"
    AFTER_EVENT = "AFTER_EVENT"
    CONDITIONAL = "CONDITIONAL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class EscalationResult:
    action: EscalationAction
    materiality: Materiality | None
    reason: str


class FixtureEscalationPolicy:
    """Deterministic P1 fixture policy.

    These event types are test/demo fixtures, not production investment thresholds.
    """

    def evaluate(self, event_type: str, payload: dict) -> EscalationResult:
        if event_type in {"DIVIDEND_RECEIVED", "ROUTINE_OBSERVATION"}:
            return EscalationResult(
                EscalationAction.INTERNAL_LOG, None, "routine deterministic event"
            )
        if event_type == "PORTFOLIO_POLICY_LIMIT_APPROACH":
            return EscalationResult(
                EscalationAction.OPEN_CASE_HIGH,
                Materiality.HIGH,
                "synthetic policy-limit fixture requires material judgment",
            )
        if event_type == "MATERIAL_REVIEW_MEDIUM":
            return EscalationResult(
                EscalationAction.OPEN_CASE_MEDIUM, Materiality.MEDIUM, "fixture"
            )
        if event_type == "MATERIAL_REVIEW_LOW":
            return EscalationResult(
                EscalationAction.OPEN_CASE_LOW, Materiality.LOW, "fixture"
            )
        return EscalationResult(
            EscalationAction.INTERNAL_LOG, None, "no fixture escalation rule"
        )
