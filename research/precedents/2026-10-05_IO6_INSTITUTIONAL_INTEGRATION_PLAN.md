# IO-6 Integration Plan — Investment Office Capabilities → Existing Institutional Kernel

Status: **PLANNED / NOT IMPLEMENTED / CROSS-BRANCH RECONCILIATION REQUIRED**  
Date: **2026-10-05**

## 1. Why this is an integration task, not a new Committee implementation

The current `main`-based Investment Office work (PR #119) now implements:

```text
PIT Evidence
→ Thesis / Counter-Thesis / Falsification
→ Scenario Economics
→ Portfolio Opportunity Cost
→ Independent Risk Opinion
```

Separately, the `architecture/p0-5-gap-audit` line already contains an institutional kernel with:

- Case state;
- durable Evidence;
- Portfolio and Risk positions;
- Adversarial challenges;
- Committee readiness;
- Committee entry;
- Committee package;
- immutable Founder Decision;
- DecisionPlan;
- simulated execution;
- append-only ledger.

Creating another Committee/Decision subsystem under
`quantrade/capabilities` would create conflicting decision authority.

Therefore IO-6 is a reconciliation/integration task.

## 2. Target integration chain

```text
Investment Office capability artifacts
        ↓
bounded adapter / handoff
        ↓
existing InstitutionalKernel
        ↓
Committee package
        ↓
Founder / governed Decision
        ↓
existing DecisionPlan
```

The adapter does not become an alternate source of Decision authority.

## 3. Source artifacts to bind

### Research / Thesis

Inputs:

- `FundamentalQueryResult`
- `ThesisContractArtifact`
- supporting PIT Observation refs;
- CounterClaims;
- FalsificationConditions.

Target institutional objects:

- durable Case Evidence for independently verifiable observations only;
- research Artifact / Case metadata for assumptions and inferences;
- Adversarial Challenge for unresolved CounterClaims.

Assumptions and model/human analysis must never be promoted into canonical Evidence merely because they support a Thesis.

## 4. Portfolio binding

Input:

`PortfolioOpportunityAssessment`

Target:

- SPMG position / bounded Portfolio artifact.

Preserve:

- best capital alternative;
- opportunity-cost spread;
- deterministic capital upper bound;
- explicit statement that upper bound is not target weight;
- Portfolio status;
- source constraint snapshot refs.

The adapter may not turn `ELIGIBLE_FOR_PORTFOLIO_REVIEW` into APPROVE.

## 5. Risk binding

Input:

`RiskOpinion`

Target:

- deterministic RiskAssessment;
- IPRO position.

Required mapping:

- PASS;
- PASS_WITH_LIMITS;
- VETO;
- REQUIRE_MORE_INFORMATION;
- risk position ceiling;
- policy/state refs;
- reasons.

A Risk VETO must remain a veto through Committee package generation unless an explicitly governed override mechanism exists.

No adapter may silently weaken a Risk limit.

## 6. Counter-Research binding

Input:

- Thesis Contract `CounterClaim` records.

Target:

- ARU Challenge records.

If a CounterClaim is unresolved, its unresolved state must survive Committee entry.

Do not collapse supporting and contradicting research into one synthesized "consensus" before Committee.

## 7. Committee readiness

The existing institutional kernel currently requires durable artifacts such as:

- Evidence;
- SPMG position;
- Risk assessment;
- IPRO position;
- ARU challenge.

IO-6 should satisfy that existing gate through adapters rather than bypass it.

If the new Investment Office artifacts reveal that the existing gate needs richer metadata, extend the gate explicitly and test it. Do not create a parallel readiness rule.

## 8. Evidence timestamp blocker

PR #108 currently has a known provenance issue:

> canonical Evidence `observed_at` must preserve the actual market/source observation timestamp rather than the later AI review time.

IO-3A/3B explicitly preserve source publication/observation timestamps.

Therefore canonical Evidence binding must not proceed until the PR #108 timestamp semantics are resolved or the adapter can prove it preserves source `observed_at` exactly.

This is a correctness blocker, not a cosmetic issue.

## 9. Branch reconciliation order

Recommended order:

1. review/merge or reconcile PR #119 Investment Office capability work;
2. resolve PR #108 Evidence `observed_at` issue;
3. rebase/merge the institutional architecture line onto the current integration base;
4. implement one bounded IO → Institutional adapter;
5. run a synthetic institutional handoff test;
6. only then design the first real Investment Case Golden Run.

Do not copy institutional code into PR #119 merely to avoid branch integration.

## 10. Required integration tests

At minimum:

### Evidence

- PIT source timestamp survives handoff;
- model artifact cannot become Evidence;
- Assumption cannot become Evidence;
- future source observation fails closed.

### Portfolio

- attractive Case may still become NOT_COMPETITIVE;
- deterministic upper bound never becomes target weight automatically.

### Risk

- PASS_WITH_LIMITS preserves the tighter ceiling;
- VETO reaches Committee package unchanged;
- missing required risk data cannot become PASS.

### Committee

- missing required departmental artifact blocks Committee entry;
- unresolved CounterClaim survives as unresolved challenge;
- no capability artifact creates Founder Decision directly;
- no DecisionPlan exists before governed approval.

## 11. Golden Run readiness after IO-6

A real buy-side-style Golden Run is ready only when the system can demonstrate:

```text
real PIT filing
→ Observation
→ Thesis
→ Counter-Thesis
→ Scenario valuation
→ Portfolio opportunity cost
→ Risk Opinion
→ institutional Committee package
→ governed Founder Decision
→ no live broker side effect
```

The purpose is to validate the organizational decision process, not to prove alpha from one Case.

## 12. Authority

This plan creates no new authority.

```text
committee_decision_created = false
founder_decision_created = false
decision_plan_created = false
execution_authorized = false
live_order_possible = false
```
