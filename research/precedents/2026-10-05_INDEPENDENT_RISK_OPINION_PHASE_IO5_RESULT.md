# Phase IO-5 Result — Independent Risk Opinion

Status: **IMPLEMENTED IN SANDBOX / VERIFIED / NON-EXECUTION-AUTHORITATIVE**  
Date: **2026-10-05**

## 1. Purpose

IO-4 determines whether an Investment Case is competitive enough to deserve
Portfolio review and computes deterministic capital headroom.

IO-5 adds an independent Risk boundary.

Risk is not a second Portfolio calculator and is not designed to justify the
Portfolio result.

It may:

- PASS;
- PASS_WITH_LIMITS;
- VETO;
- REQUIRE_MORE_INFORMATION.

## 2. Implemented files

Core:

`quantrade/capabilities/risk_opinion.py`

Reference harness:

`quantrade/capabilities/risk_opinion_evaluation.py`

Tests:

`tests/capabilities/test_risk_opinion.py`

## 3. Required input boundary

Risk accepts only a Case whose Portfolio assessment is already:

`ELIGIBLE_FOR_PORTFOLIO_REVIEW`

A rejected / missing-context Portfolio Case cannot be smuggled into Risk and
later rescued.

The Portfolio assessment must also remain:

- non-proposal;
- non-execution-authoritative.

## 4. Candidate Risk Profile

The bounded candidate profile includes:

- asset ID;
- worst-case scenario return;
- max absolute correlation to current portfolio, when known;
- estimated exit days, when known;
- whether leverage is used;
- risk provenance references.

Risk information is therefore separated from expected-return attractiveness.

## 5. Independent Risk Policy

The Risk policy snapshot includes explicit values for:

- maximum single-asset weight;
- maximum incremental downside budget;
- maximum portfolio drawdown;
- maximum candidate correlation to portfolio, if used;
- maximum exit days, if used;
- leverage permission;
- whether correlation data is mandatory;
- whether liquidity data is mandatory;
- policy references.

No numeric Risk threshold is invented by the module.

## 6. Independent Risk State

The Risk state snapshot contains:

- current candidate-asset weight;
- current portfolio drawdown;
- state references;
- as-of timestamp.

Risk policy and state snapshots may not come from the future relative to the
Portfolio snapshot.

## 7. Independent position ceiling

Risk computes:

### Single-asset headroom

```text
risk max asset weight - current asset weight
```

### Downside-budget ceiling

```text
max incremental downside budget
÷ candidate downside severity
```

Example:

- max incremental downside budget: 2% of portfolio;
- candidate Bear loss: -40%.

Then:

```text
2% / 40% = 5% portfolio-weight ceiling
```

The final Risk ceiling is:

```text
min(
  Portfolio opportunity upper bound,
  Risk single-asset headroom,
  Risk downside-budget ceiling
)
```

The output states explicitly:

`risk_position_ceiling_pct != target_weight`

Risk can reduce the admissible ceiling without selecting the final allocation.

## 8. Veto paths

Current deterministic vetoes include:

- portfolio drawdown limit already reached;
- leverage used while policy forbids leverage;
- candidate correlation exceeds explicit policy limit;
- estimated exit period exceeds explicit policy limit;
- Risk single-asset headroom is exhausted;
- no incremental downside budget remains.

A Risk veto remains visible and cannot be converted into a Portfolio approval.

## 9. Missing-data path

If Risk policy requires:

- correlation data;
- liquidity data;

and the candidate profile lacks that information, the result is:

`REQUIRE_MORE_INFORMATION`

not PASS.

This is important because absence of measured risk is not evidence of safety.

## 10. Reference harness

The harness produces three different outcomes from the same Portfolio-eligible
Case.

### PASS_WITH_LIMITS

Portfolio likes the Case, but Risk downside budget reduces the admissible
capital ceiling.

### VETO

The candidate exceeds the explicit correlation limit.

### REQUIRE_MORE_INFORMATION

Required correlation/liquidity evidence is absent.

This preserves real departmental disagreement.

## 11. Authority invariant

IO-5 reports:

```text
model_called = false
canonical_evidence_created = false
portfolio_proposal_created = false
target_weight_set = false
risk_opinion_created = true
risk_limit_changed = false
committee_decision_created = false
decision_plan_created = false
paper_authorized = false
execution_authorized = false
live_order_possible = false
```

## 12. Verification

Latest Investment Office Core CI:

`37267016324`

Result: **SUCCESS**

Observed tests:

- Investment Case Economics: **10 passed**
- Thesis Contract: **12 passed**
- PIT Fundamental Evidence: **11 passed**
- Open DART Provider: **12 passed**
- Portfolio Opportunity Cost: **12 passed**
- Independent Risk Opinion: **12 passed**
- full capability regression suite: **96 passed**
- all reference harnesses: success

## 13. Existing Institutional Kernel reconciliation

Before creating an IO-6 Committee implementation, the separate
`architecture/p0-5-gap-audit` development line was inspected.

That branch already contains an institutional kernel with:

- `committee_readiness()`;
- `enter_committee()`;
- `build_committee_package()`;
- immutable Founder `decide()`;
- `create_decision_plan()`;
- simulated execution records;
- append-only ledger behavior.

Therefore IO-6 must **not** create a competing Committee/Decision subsystem in
`quantrade/capabilities`.

The correct next work is an integration seam:

```text
IO-1..IO-5 capability artifacts
        ↓
existing institutional Case / Committee package
        ↓
existing Founder / Decision / DecisionPlan governance
```

This avoids two conflicting sources of decision authority.

## 14. Current executable chain

```text
Open DART / PIT Evidence
        ↓
Thesis / Counter-Thesis / Falsification
        ↓
Scenario Economics
        ↓
Portfolio Opportunity Cost
        ↓
Portfolio Review Eligibility + Capital Headroom
        ↓
Independent Risk Opinion
        ↓
PASS / PASS_WITH_LIMITS / VETO / REQUIRE_MORE_INFORMATION
```

The next step is **integration**, not another parallel decision engine.
