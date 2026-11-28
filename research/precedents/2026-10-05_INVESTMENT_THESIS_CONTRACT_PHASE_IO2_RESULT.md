# Phase IO-2 Result — Investment Thesis Contract

Status: **IMPLEMENTED IN SANDBOX / VERIFIED / NON-AUTHORITATIVE**  
Date: **2026-10-05**  
Parent direction: `2026-10-05_INVESTMENT_OFFICE_DECISION_ECONOMICS_DIRECTION.md`

## 1. Purpose

Phase IO-1 proved that QuanTrade can calculate Investment Case economics
deterministically from explicit scenario assumptions.

Phase IO-2 adds the missing research structure that prevents the system from
mixing together:

- observations;
- assumptions;
- inferences;
- thesis claims;
- counter-claims;
- falsification conditions.

The objective is not to decide whether a thesis is true.

The objective is to make it difficult for QuanTrade to hide weak reasoning
inside one free-text recommendation.

## 2. Implemented capability

New module:

`quantrade/capabilities/thesis_contract.py`

Reference harness:

`quantrade/capabilities/thesis_contract_evaluation.py`

Tests:

`tests/capabilities/test_thesis_contract.py`

## 3. Domain objects

### Observation

Carries:

- observation ID;
- statement;
- source reference;
- source kind;
- observed timestamp.

Supported source kinds:

- `EXTERNAL_EVIDENCE`
- `RUNTIME_VERIFIED`
- `CLIENT_FACT`
- `MODEL_ARTIFACT`
- `HUMAN_ANALYSIS`

Only:

- `EXTERNAL_EVIDENCE`
- `RUNTIME_VERIFIED`

count as evidence-bearing support for a market Investment Thesis.

This means:

- model output is not Evidence;
- human analysis is not automatically Evidence;
- a true Client Fact is valid Client context but does not prove market edge.

### Assumption

Carries:

- assumption ID;
- statement;
- rationale;
- optional provenance references.

Assumptions may support a thesis, but are never counted as evidence.

### Inference

Carries:

- inference ID;
- statement;
- explicit input references.

Inference inputs may point only to:

- Observation;
- Assumption;
- prior Inference.

The compiler rejects inference dependency cycles.

### ThesisClaim

Carries:

- thesis ID;
- statement;
- explicit support references.

Every Thesis Claim must eventually resolve to its leaf Observation/Assumption
support so the system can see whether it is actually evidence-backed.

### CounterClaim

Carries:

- counter ID;
- target thesis ID;
- statement;
- explicit basis references.

Counter-Research is preserved separately from supporting research.

The compiler does **not** fabricate a CounterClaim when none exists. Missing
counter-research remains visible as a gap.

### FalsificationCondition

Carries:

- condition ID;
- target thesis ID;
- falsification statement;
- observable;
- evaluation horizon.

Every Thesis Claim is required to define at least one falsification condition.

A thesis that cannot state how it could be wrong is rejected structurally.

## 4. Deterministic provenance graph

The compiler builds a typed dependency structure.

Example:

```text
External Observation
        ┐
        ├→ Inference → Thesis Claim
Assumption
        ┘

Runtime-Verified Observation
        → CounterClaim
        → same Thesis

Thesis
        → Falsification Condition
```

For every thesis it calculates:

- leaf support references;
- eligible Evidence-bearing observation refs;
- non-Evidence observation refs;
- assumption refs;
- whether any eligible evidence exists;
- CounterClaim IDs;
- whether Counter-Research is present;
- FalsificationCondition IDs.

It does **not** calculate whether the thesis is correct.

## 5. Fail-closed rules

The compiler rejects:

- duplicate IDs across any node type;
- missing statements or identifiers;
- unsupported source kinds;
- timezone-naive timestamps;
- observations dated after the Case as-of time;
- unknown references;
- illegal reference types;
- inference self-reference;
- inference dependency cycles;
- Thesis Claims without support;
- CounterClaims targeting nonexistent Thesis Claims;
- CounterClaims without basis refs;
- FalsificationConditions targeting nonexistent Thesis Claims;
- Thesis Claims without any falsification condition.

## 6. Evidence boundary

Reference harness CASE 1 contains:

- external filing observation;
- runtime-verified observation;
- model-generated observation;
- explicit forecast assumption;
- inference;
- thesis;
- counter-thesis;
- falsification condition.

The compiler correctly counts the external/runtime-verified inputs as
evidence-bearing while preserving the model artifact as non-Evidence.

Reference harness CASE 2 deliberately contains only:

- model-generated narrative;
- assumption;
- thesis.

Result:

`all_theses_evidence_backed = false`

The thesis remains representable as a draft, but cannot acquire Evidence status
by being well-written.

## 7. Client Fact separation

A dedicated regression test verifies:

> a valid Client Fact does not become market-thesis Evidence.

Client facts remain important to:

- Client Intelligence;
- Strategy / Mandate;
- Portfolio;
- Risk.

But they cannot establish that a security is undervalued.

This preserves organizational separation of duties.

## 8. Completeness metrics

The compiled artifact reports:

- observation count;
- assumption count;
- inference count;
- thesis count;
- counter-claim count;
- falsification-condition count;
- theses with eligible evidence backing;
- theses with Counter-Research;
- theses without eligible evidence;
- whether all theses are falsifiable;
- whether all theses are evidence-backed;
- whether all theses have Counter-Research.

These are structural/completeness measurements only.

They are not Investment Committee scoring.

## 9. Authority invariant

Every Thesis Contract Artifact reports:

```text
model_called = false
canonical_evidence_created = false
thesis_truth_validated = false
portfolio_proposal_created = false
position_size_set = false
risk_opinion_created = false
committee_decision_created = false
decision_plan_created = false
paper_authorized = false
execution_authorized = false
live_order_possible = false
```

## 10. Verification

Latest GitHub Actions run:

`37265361211`

Result: **SUCCESS**

Observed test runs:

- Investment Case Economics tests: **10 passed**
- Thesis Contract tests: **12 passed**
- full current capability regression suite: **49 passed**
- both synthetic reference harnesses: success

## 11. What this enables

QuanTrade can now represent the beginning of a real buy-side Case as:

```text
Observation
→ Assumption
→ Inference
→ Investment Thesis
↘ Counter-Research
↘ Falsification Condition

+ deterministic Scenario / Valuation Economics
```

This is materially different from:

```text
news + indicators + LLM
→ BUY / SELL
```

## 12. What is still missing

Phase IO-2 does not yet implement:

- real DART/company filing ingestion;
- analyst consensus ingestion;
- point-in-time fundamentals;
- deterministic DCF/PER/EV-EBITDA valuation engines;
- automatic thesis generation;
- actual independent Counter-Research AI;
- Portfolio opportunity-cost comparison;
- Risk Opinion;
- Committee Decision;
- Performance / thesis calibration.

## 13. Next bounded step

The next high-value step is **IO-3A — Point-in-Time Evidence Provider
Contract**, before any specific DART or commercial provider is wired in.

The contract should force every external fundamental observation to preserve:

- source/provider;
- source document/report ID;
- published/observed timestamp;
- effective fiscal period;
- retrieval timestamp;
- restatement/revision metadata where available;
- unit/currency;
- raw value;
- normalization rule;
- Evidence reference.

That provider boundary should be implemented first, then DART can become one
replaceable provider rather than being hard-wired into QuanTrade domain logic.
