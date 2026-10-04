# ReviewGate Shadow Evaluation Mission

Status: **SANDBOX EVALUATION HARNESS IMPLEMENTED**  
Date: **2026-10-04**  
Parent: `2026-10-04_REVIEW_GATE_LIVE_BINDING_DECISION.md`

## Mission

Determine whether ReviewGate behaves coherently across materially different
organizational situations before any production-routing authority is proposed.

## Organizational questions

- **Performance & Learning (Mission Owner):** Are the scenarios reproducible and are disagreements measurable?
- **Research:** Does unresolved disagreement remain reviewable, and can novel material events surface?
- **Risk & Compliance:** Are risk-policy breaches mandatory regardless of cost optimization?
- **Client Intelligence / Strategy:** Are mandate and liquidity conflicts mandatory without exposing private values?
- **Committee / Execution:** Does the harness remain evidence-only with zero decision/execution authority?

## Canonical evaluation matrix

1. routine low-materiality observation → NO_REVIEW
2. material research change → BOUNDED_REVIEW
3. unresolved research disagreement → BOUNDED_REVIEW
4. Client mandate conflict → MANDATORY_REVIEW
5. liquidity constraint breach → MANDATORY_REVIEW
6. Risk policy breach → MANDATORY_REVIEW
7. novel high-materiality event → MANDATORY_REVIEW

The matrix deliberately spans all three ReviewLevels. It is not a claim of
predictive performance and does not simulate investment returns.

## Disagreement policy

A mismatch is evidence. The harness records it; it does not automatically
change the ReviewGate, legacy gate, risk policy, or production routing.

## Unknown-event boundary

This harness proves only that a *novel event with explicit high materiality*
is caught by the existing materiality rule. It does **not** prove that an
unknown reason lost during reason→event translation is safe. That separate
translation-gap risk remains open and must be addressed before production
promotion.

## Promotion rule

Passing fixtures is necessary but insufficient. Production promotion still
requires live samples, translation-coverage analysis, actual model-call
telemetry, disagreement review, and an explicit Proposal → Decision.
