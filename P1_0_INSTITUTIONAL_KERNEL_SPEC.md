# QuanTrade P1.0 — Institutional Kernel Implementation Spec

Date: 2026-09-19  
Status: Ready for implementation  
Depends on: P0_5_VISION_IMPLEMENTATION_GAP_AUDIT.md

## Objective

Build the smallest real runtime in which QuanTrade behaves like an investment institution rather than a dashboard.

The kernel must distinguish routine Events from material Cases, protect Founder attention through escalation, preserve office disagreement, continue Cases after Founder approval into decision management/review, and persist the institutional history transactionally.

## Core doctrine

1. Not every Event is a Case.
2. Not every Case reaches the Founder.
3. Founder approval is not automatically Case closure.
4. InvestmentDecision is an institutional output, not the system's conceptual center.
5. Deterministic calculations/policies must not be replaced by LLM judgment.
6. Institutional disagreement must remain visible and durable.
7. Ledger history is append-only at the application boundary.
8. P1.0 must have zero live broker side effects.
9. Legacy JSON runtime is not the source of truth for P1.
10. Build beside legacy code; do not delete or silently rewrite historical systems.

## Suggested package

```
quantrade/
  institutional/
    __init__.py
    domain.py
    enums.py
    services/
      event_service.py
      case_service.py
      committee_service.py
      decision_service.py
      review_service.py
    repositories/
      interfaces.py
      sqlite.py
    policies/
      escalation.py
    db.py
    demo.py
tests/
  institutional/
```

Names may change if there is a concrete technical reason, but preserve the boundaries.

## Required entities

### Event
Minimum fields:
- event_id
- event_type
- occurred_at
- source
- subject_type / subject_id
- payload or normalized facts
- resolution_status
- created_at

### Case
Minimum fields:
- case_id
- title
- trigger_event_id
- subject
- status
- materiality: LOW / MEDIUM / HIGH
- opened_at
- closed_at nullable
- version

Case IDs should support the institutional form `QT-YYYY-NNNN`.

### Evidence
- evidence_id
- case_id
- source
- observed_at
- claim/fact
- reliability/provenance metadata
- created_at

### PortfolioSnapshot
- snapshot_id
- case_id
- as_of
- source
- immutable serialized holdings/cash snapshot

### RiskAssessment
- assessment_id
- case_id
- snapshot_id
- policy_version
- deterministic result
- created_at

### InstitutionalPosition
- position_id
- case_id
- office
- stance
- rationale
- evidence references
- created_at
- supersedes_id nullable

Never silently overwrite a prior office position.

### Challenge
- challenge_id
- case_id
- office = ARU
- thesis challenged
- counter_thesis
- unresolved flag
- created_at

### CommitteePackage
- package_id
- case_id
- positions
- challenges
- unresolved questions
- proposed action
- generated_at

It must preserve dissent instead of flattening it into consensus.

### FounderOrder
- order_id
- destination
- route: DIRECT / SECRETARY
- instruction
- status
- created_at

### InvestmentDecision
- decision_id
- case_id
- action: APPROVE / REJECT / HOLD / RESEARCH
- founder_note
- decided_at
- immutable after creation

A correction must create a new/superseding record, not mutate history.

### DecisionPlan
Created after an approved investment action.
- plan_id
- decision_id
- timing_mode: NOW / AFTER_EVENT / CONDITIONAL / HOLD
- condition_text nullable
- status
- created_at

### ExecutionRecord
P1.0 is simulation/record only.
- execution_id
- plan_id
- mode = SIMULATED
- status
- details
- executed_at nullable

There must be no broker adapter capable of submitting an order in P1.0.

### ReviewSchedule / OutcomeReview
- review_id
- case_id
- horizon_days (e.g. 30, 90)
- due_at
- status
- outcome fields nullable

### LedgerEvent
- ledger_id
- aggregate_type
- aggregate_id
- event_type
- payload
- occurred_at
- previous_hash nullable
- event_hash

The hash chain is a prototype integrity mechanism, not a claim of tamper-proof storage.

## Event → Case policy

Implement a deterministic interface such as:

`class EscalationPolicy: evaluate(event, context) -> EscalationResult`

Result must distinguish:
- INTERNAL_LOG
- OPEN_CASE_LOW
- OPEN_CASE_MEDIUM
- OPEN_CASE_HIGH

Do not hard-code “price moved X%” as a universal investment policy unless it is explicitly fixture/demo policy. Production thresholds remain future policy decisions.

P1 tests should use synthetic fixtures:
- routine dividend/observation event → INTERNAL_LOG
- synthetic policy-limit approach event → OPEN_CASE_HIGH

## Founder routing

- LOW Case: can resolve internally and be logged.
- MEDIUM Case: appears in periodic Founder Briefing queue, not immediate Founder Desk.
- HIGH Case: enters Founder Desk.
- Policy exception / authority breach may force HIGH later, but P1.0 can expose the extension point without inventing final policy.

## Case state machine

Use explicit allowed transitions. Suggested states:

`OPEN → RESEARCH → PORTFOLIO_REVIEW → RISK_REVIEW → ADVERSARIAL_REVIEW → COMMITTEE → FOUNDER_PENDING → DECIDED → DECISION_MANAGEMENT → EXECUTION_PENDING → OUTCOME_TRACKING → CLOSED`

Also support HOLD / RESEARCH_REQUESTED paths without destroying prior state.

Do not allow arbitrary direct state mutation through repository calls.

## Persistence

Use SQLite for P1.0.

Requirements:
- schema initialized/migrated explicitly
- foreign keys enabled
- transactions around state transition + ledger append
- repository interfaces separate domain/services from SQLite
- no business logic in SQL layer
- UTC timestamps
- stable identifiers
- reload must reconstruct current state and history

Do not introduce PostgreSQL, Redis, queues or web servers merely for future scale.

## Ledger invariants

Tests must prove:
- every Case state transition appends a LedgerEvent
- old ledger rows are not updated by normal application services
- InvestmentDecision cannot be edited in place
- InstitutionalPosition history is preserved
- CommitteePackage contains dissent/challenges
- Case closure cannot erase its history

## Required demonstration scenario

Create a deterministic fixture inspired by the UI's CASE-041, not tied to a live recommendation.

Scenario:
1. routine Event is logged and creates no Case.
2. synthetic `PORTFOLIO_POLICY_LIMIT_APPROACH` Event for a mock holding is ingested.
3. policy opens `QT-2026-0041` as HIGH.
4. Research attaches sourced mock Evidence.
5. Portfolio office records alternatives such as KEEP / REDUCE / EXIT as analytical alternatives, not an autonomous trade instruction.
6. Risk records deterministic exposure/liquidity/correlation facts from fixture data.
7. ARU records counter-thesis.
8. CommitteePackage preserves positions, dissent and unresolved uncertainty.
9. Case reaches Founder Desk.
10. Demo Founder approves a mock REDUCE action.
11. Decision Management creates a conditional DecisionPlan.
12. simulated ExecutionRecord is created; no broker call exists.
13. 30D and 90D ReviewSchedules are created.
14. process reloads from SQLite and verifies complete history.

The fixture must be clearly marked synthetic/mock and must not be presented as current investment advice.

## Tests

At minimum:
- routine Event does not create Case
- material Event creates Case
- LOW/MEDIUM/HIGH routing semantics
- invalid Case state transition rejected
- transition and ledger append atomic
- decision immutable
- superseding office position preserves old record
- dissent survives Committee packaging
- approved decision does not auto-close Case
- DecisionPlan can represent NOW / AFTER_EVENT / CONDITIONAL / HOLD
- simulated execution has no broker side effect
- review schedules created
- reload reproduces current Case + history
- SQLite foreign keys/integrity active

Use standard library `unittest` unless the repository already has a clear test framework dependency. Avoid unnecessary dependencies.

## Legacy boundary

P1.0 must not:
- rewrite `portfolio.json`
- consume `pending_actions.json` as canonical decisions
- change real-account holdings
- activate `autoexec.py`
- change GitHub Actions schedules
- alter root `index.html`
- alter P0.3.1 UI
- submit real orders

## Acceptance gate

The implementation is accepted only when one command can run the institutional tests and prove both:

```
Routine Event
→ internal handling
→ Ledger
→ no Case
→ no Founder interruption
```

and

```
Material Event
→ Case
→ Evidence
→ Portfolio/Risk positions
→ Challenge
→ Committee
→ HIGH escalation
→ Founder Decision
→ DecisionPlan
→ simulated ExecutionRecord
→ 30D/90D ReviewSchedule
→ Ledger
→ reload
```

No live broker side effect is permitted.
