from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Materiality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EventTriageAction(str, Enum):
    INTERNAL_LOG = "INTERNAL_LOG"
    OPEN_CASE = "OPEN_CASE"


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
class EventTriageResult:
    action: EventTriageAction
    reason: str


class FixtureEventTriagePolicy:
    """Deterministic P1 fixture policy.

    Event triage answers only whether an Event can be handled internally or needs
    institutional judgment as a Case. LOW/MEDIUM/HIGH is deliberately assigned
    later, after institutional review. These event types are synthetic fixtures,
    not production investment thresholds.
    """

    def evaluate(self, event_type: str, payload: dict) -> EventTriageResult:
        if event_type in {"DIVIDEND_RECEIVED", "ROUTINE_OBSERVATION"}:
            return EventTriageResult(
                EventTriageAction.INTERNAL_LOG, "routine deterministic event"
            )
        if event_type in {
            "PORTFOLIO_POLICY_LIMIT_APPROACH",
            "MATERIAL_REVIEW_REQUIRED",
        }:
            return EventTriageResult(
                EventTriageAction.OPEN_CASE,
                "synthetic fixture requires institutional investment judgment",
            )
        return EventTriageResult(
            EventTriageAction.INTERNAL_LOG, "no fixture case-opening rule"
        )
