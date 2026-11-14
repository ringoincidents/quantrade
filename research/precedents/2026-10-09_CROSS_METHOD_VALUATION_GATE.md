# Cross-Method Valuation Gate — Post QT-CASE-002 Adoption

Status: **ADOPTED FOR FUTURE INVESTMENT CASES / NON-AUTHORITATIVE CAPABILITY**  
Date: **2026-10-09**  
Origin experiment: **QT-CASE-002**

## Problem

A single valuation method can look internally coherent while being highly
sensitive to its chosen economic representation.

QT-CASE-001:

`P/E expected return = +31.39%`

QT-CASE-002:

`Cash-flow DCF expected return = +0.995%`

Both were deterministic and used the same frozen Case price.

Therefore "deterministic" does not mean "robust."

## Adopted rule

QuanTrade should represent valuation methods as independent method artifacts
before Portfolio review.

Examples:

- P/E
- EV/EBIT
- DCF
- DDM
- residual income
- sum-of-parts

A method remains analysis. It does not receive Portfolio or trade authority.

## Reusable contract

Implemented:

`quantrade/capabilities/valuation_crosscheck.py`

Core objects:

- `ValuationScenarioSnapshot`
- `ValuationMethodSnapshot`
- `ValuationCrossCheckInput`
- `ValuationCrossCheckArtifact`

## Comparison invariants

Methods must share:

- Case price;
- required-return hurdle;
- scenario IDs;
- scenario probabilities.

Mismatch is fail-closed.

No hidden probability reweighting or method weighting is performed.

## Classification

### CROSS_METHOD_CONFIRMED

Every valuation method independently clears the required-return hurdle.

### CROSS_METHOD_MIXED

At least one method clears and at least one does not.

### CROSS_METHOD_REJECTED

No method clears.

Classification itself has no capital authority.

## Robust aggregation

For each aligned scenario:

```text
robust fair value
=
minimum fair value across all methods
```

Then:

```text
robust weighted fair value
=
sum(probability * robust scenario fair value)
```

This is intentionally conservative.

The gate reports method disagreement rather than averaging it away.

## Future Portfolio routing

Recommended future routing contract:

```text
independent valuation methods
        ↓
Cross-Method Valuation Gate
        ↓
CONFIRMED + robust hurdle passes
        ↓
Portfolio Opportunity Cost
```

A MIXED result should normally remain Research/Counter-Research material unless
an explicitly governed policy says otherwise.

This rule is prospective. It does not rewrite QT-CASE-001 or QT-CASE-002.

## Why this matters

The gate is a direct defense against a common failure mode:

> choose one plausible valuation model → obtain an attractive fair value →
> treat arithmetic precision as confidence → size capital.

QuanTrade instead preserves disagreement as information.

## Authority invariant

The cross-method capability always keeps:

```text
model_called = false
canonical_evidence_created = false
portfolio_proposal_created = false
target_weight_set = false
risk_opinion_created = false
committee_decision_created = false
decision_plan_created = false
paper_authorized = false
execution_authorized = false
live_order_possible = false
```

## Current limitation

The initial implementation requires aligned scenario IDs/probabilities.

Future methods such as SOTP or Monte Carlo valuation may not naturally share
the same scenario structure.

Do not weaken the contract by silently mapping incompatible distributions.

A later extension should define an explicit distribution-comparison contract
instead.
