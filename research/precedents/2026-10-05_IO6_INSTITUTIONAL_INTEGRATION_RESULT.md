# IO-6 Result — Investment Office → InstitutionalKernel Integration

Status: **IMPLEMENTED AS STACKED INTEGRATION / VERIFIED / NO DECISION OR EXECUTION AUTHORITY**  
Date: **2026-10-05**  
Stack base: PR #108 (`task-071-verified-research-sources`)  
Integration PR: #120

## 1. Purpose

The Investment Office capability line and the institutional runtime were
developed on separate branches.

The integration goal is to connect them without creating a second source of
Committee/Decision authority.

The resulting architecture is:

```text
Investment Office capability artifacts
        ↓
InvestmentOfficeInstitutionalBridge
        ↓
existing InstitutionalKernel
        ↓
existing Committee gate
        ↓
existing Founder / Decision / DecisionPlan governance
```

The bridge itself cannot create Founder decisions or execution plans.

## 2. Provenance blocker resolved in PR #108

Before implementing IO-6, PR #108's canonical Evidence timestamp issue was
resolved.

Canonical Evidence now preserves:

```text
observed_at = actual source/runtime observation timestamp
created_at  = institutional persistence timestamp
```

For the current Market State evidence, the exact market timestamp survives the
Research promotion step.

PR #108 verification:

`37267613069` — **SUCCESS**

Institutional suite:

**153 tests passed**

## 3. Portfolio snapshot time fixed

The existing institutional `add_snapshot()` method previously always used
persistence time as snapshot `as_of`.

IO-6 extends it with an optional source `as_of`.

Historical integrations can now preserve:

```text
portfolio_snapshots.as_of = source Portfolio snapshot time
portfolio_snapshots.created_at = persistence time
```

Existing callers remain backward-compatible.

## 4. Bridge contract

New module:

`quantrade/institutional/investment_office_bridge.py`

The bridge is schema-based because the Investment Office capability work still
lives in a separate main-based Draft PR.

Accepted schemas:

- `quantrade_fundamental_observation_query_v1`
- `quantrade_thesis_contract_v1`
- `quantrade_portfolio_opportunity_v1`
- `quantrade_risk_opinion_v1`

This avoids copying capability implementations into the architecture branch.

## 5. Evidence binding

The bridge promotes only Thesis Observations whose source kind is:

- `EXTERNAL_EVIDENCE`
- `RUNTIME_VERIFIED`

It does not promote:

- model artifacts;
- assumptions;
- human analysis by default;
- Client facts as market evidence.

For external evidence, the bridge requires the Thesis Observation to match the
bound Fundamental source observation.

Critical condition:

```text
Thesis Observation observed_at
==
Fundamental source published_at
```

Timestamp mismatch is fail-closed.

The bridge calls the existing canonical `add_evidence()` method with the
actual source timestamp and a source Evidence fingerprint.

## 6. Portfolio binding

Only:

`ELIGIBLE_FOR_PORTFOLIO_REVIEW`

may enter the institutional handoff.

The bridge creates an SPMG institutional position preserving:

- opportunity-cost comparison;
- best capital alternative;
- deterministic capital headroom;
- Portfolio reasons;
- source constraints.

It does not create a target weight.

## 7. Risk binding

The bridge binds the deterministic Risk Opinion into:

- Portfolio snapshot;
- RiskAssessment;
- IPRO position.

Risk states are preserved exactly:

- PASS
- PASS_WITH_LIMITS
- VETO
- REQUIRE_MORE_INFORMATION

A Risk VETO remains an IPRO `VETO` through Committee packaging.

The bridge does not downgrade or override it.

## 8. Missing-risk-information gate

The existing institutional artifact gate can technically become complete once
Evidence, Portfolio, Risk and Challenge artifacts exist.

IO-6 adds an integration-level safety rule:

`REQUIRE_MORE_INFORMATION`

blocks automatic Committee entry even when the existing artifact gate is
otherwise complete.

Missing measured risk cannot be treated as an implicit PASS.

## 9. Counter-Research binding

Thesis Contract CounterClaims become existing ARU Challenge records.

If no CounterClaim exists, IO-6 does not invent one.

The existing `committee_readiness()` then reports:

`adversarial_challenge_id` missing.

This preserves the gap instead of synthesizing false dissent.

## 10. Existing Committee reuse

When:

- existing Committee artifact readiness is complete; and
- Risk status is not REQUIRE_MORE_INFORMATION;

the bridge uses the existing:

`enter_committee()`

method.

No new Committee state machine was created.

## 11. VETO preservation test

The integration suite verifies a Risk VETO survives:

```text
RiskOpinion.status = VETO
→ IPRO institutional position = VETO
→ existing Committee package IPRO stance = VETO
```

The bridge does not create a Founder decision after that.

## 12. Idempotent handoff

The bridge computes a canonical SHA-256 fingerprint over the complete handoff.

The fingerprint and result are written into the append-only institutional
ledger as:

`INVESTMENT_OFFICE_HANDOFF_BOUND`

Replaying the exact same handoff returns the previously bound result and does
not duplicate:

- Evidence;
- SPMG/IPRO positions;
- ARU challenges.

## 13. Verification

Stacked PR #120 workflow:

`P1 Institutional Kernel Tests`

Run:

`37267938620`

Result: **SUCCESS**

**164 institutional tests passed**

New integration tests verify:

- full handoff enters the existing Committee;
- source `observed_at` survives exactly;
- model artifact / assumption are not Evidence;
- timestamp mismatch fails closed;
- Portfolio source `as_of` survives;
- Risk VETO survives Committee packaging;
- REQUIRE_MORE_INFORMATION blocks Committee;
- missing CounterClaim remains an institutional gap;
- NOT_COMPETITIVE Portfolio cannot be rescued;
- handoff replay is idempotent;
- execution-authoritative input is rejected.

## 14. Authority

After a successful IO-6 handoff:

```text
committee_entered = possible when ready
founder_decision_created = false
decision_plan_created = false
paper_authorized = false
execution_authorized = false
live_order_possible = false
```

Committee entry is not capital approval.

## 15. Current system boundary

After IO-6, the executable architecture is conceptually:

```text
PIT Fundamental Evidence
→ Thesis / Counter-Thesis / Falsification
→ Scenario Economics
→ Portfolio Opportunity Cost
→ Independent Risk Opinion
→ Institutional Evidence / SPMG / IPRO / ARU artifacts
→ existing Committee gate
```

The next work should inspect and reuse the existing Performance/Learning layer
before implementing any new outcome subsystem.
