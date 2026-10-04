# Reason Translation Observability Decision

Status: **APPROVED / SHADOW OBSERVABILITY ONLY**  
Date: **2026-10-04**  
Parent: `2026-10-04_REVIEW_GATE_EVALUATION_MISSION.md`

## Problem

The live shadow binding previously translated only known reason strings. An
unknown future reason could therefore disappear before ReviewGate evaluation.
That creates a dangerous ambiguity: `NO_REVIEW` could mean either "nothing
material exists" or "the translator did not understand the input."

## Organizational review

- **Research:** preserve novel reasons so emerging concepts remain inspectable.
- **Risk & Compliance:** silent loss is unacceptable, but unknown does not by
  itself justify inventing a risk severity.
- **Strategy / Client Intelligence:** retain source provenance while continuing
  to consume only the sanitized precheck, never private Client values.
- **Performance & Learning:** measure translation coverage before claiming the
  routing system is reliable.
- **Committee / Execution:** translation evidence receives no investment or
  execution authority.

## Decision

Introduce explicit translation records with `MAPPED | UNMAPPED`, source,
original reason, mapped event type/role when known, coverage counts, and
`requires_translation_review`.

Do **not** assign an invented materiality to an unknown reason. Do **not**
auto-escalate it in production. The current shadow may still produce
`NO_REVIEW`; when that occurs beside an unmapped reason, the artifact makes
the translation gap explicit and blocks automatic promotion.

## Why this is safer

It separates two questions:

1. Did ReviewGate classify the structured events correctly?
2. Did the translation boundary successfully structure all source reasons?

A failure in question 2 can no longer masquerade as evidence for question 1.

## Next evidence

Accumulate live `unmapped_count`, inspect every unique unmapped reason, then
let Research + Risk propose a fail-safe policy. Candidate policies may include
bounded review for unknowns, mandatory review for authority-bearing source
classes, or registry expansion. No candidate is approved by this decision.
