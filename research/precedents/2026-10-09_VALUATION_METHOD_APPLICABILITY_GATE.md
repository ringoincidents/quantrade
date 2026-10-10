# Valuation Method Applicability Gate — Adoption After QT-CASE-003

Status: **ADOPTED FOR FUTURE INVESTMENT CASES / NO CAPITAL AUTHORITY**  
Date: **2026-10-09**  
Origin: **QT-CASE-003 + QT-CASE-003-CORR-001**

## Problem exposed by the holdout

The first second-issuer holdout, Samsung SDI (`KRX:006400`), did not fail
because Open DART lacked basic EPS.

The frozen QT-CASE-003 contract requested:

`ifrs-full_BasicEarningsLossPerShare:IS:CURRENT_PERIOD`

Open DART reported the same exact IFRS account under:

`CIS`

The original holdout therefore stopped, as preregistered.

A later read-only schema diagnostic established the distinction:

```text
semantic accounting identity
!=
issuer-specific DART statement placement
```

QT-CASE-003 remains an immutable **PROCESS_PORTABILITY_FAILURE**.

It was not rewritten to pass.

## Semantic correction result

QT-CASE-003-CORR-001 preregistered one bounded correction:

- basic EPS and parent profit may resolve from predeclared `IS | CIS`;
- cash-flow accounts remain `CF`;
- parent equity remains `BS`;
- account-name guessing is forbidden;
- issuer-specific alias inference is forbidden;
- zero matches fail;
- multiple allowed matches fail.

The semantic layer then resolved successfully:

`PE semantic = READY`

`DCF semantic = READY`

But semantic readiness did **not** make the valuation methods economically
applicable.

Observed domain facts included:

- FY2025 basic EPS: **-8,796 KRW**;
- FY2025 profit attributable to owners: **-649.47B KRW**;
- 2025-H1 YTD basic EPS: **-5,415 KRW**;
- 2026-H1 YTD basic EPS: **3,991 KRW**;
- reconstructed owner-cash-flow proxy remains non-positive under the frozen
  QT-CASE-003 method.

Therefore:

```text
PE = NOT_APPLICABLE
reason = NON_POSITIVE_EPS
```

and:

```text
OWNER_CASH_FLOW_DCF = NOT_APPLICABLE
reasons include:
- NON_POSITIVE_FY2025_OWNER_PROFIT
- NON_POSITIVE_FY2025_EPS
- NON_POSITIVE_IMPLIED_SHARES
- NON_POSITIVE_TTM_OWNER_CASH_FLOW
```

No substitute P/B, EV/EBITDA, analyst target, or other model was selected.

## Adopted distinction

Future QuanTrade research must distinguish at least three different states:

### 1. Semantic metric unavailable

The required accounting concept cannot be resolved under the predeclared
semantic contract.

Examples:

- zero exact-account matches;
- ambiguous multiple allowed matches;
- required historical period missing.

This is a **data/semantic applicability** problem.

### 2. Semantic metric available, valuation method not applicable

The data are real and resolved, but the mathematical/economic domain required
by the valuation method is invalid.

Examples:

- P/E with non-positive earnings;
- owner-cash-flow DCF with non-positive frozen cash-flow anchor;
- implied-share denominator not positive.

This is a **method applicability** problem.

It must not be mislabeled as "bad company" or "low fair value."

### 3. Valuation method applicable

Only after semantic and domain gates pass may valuation arithmetic run.

## Implemented capabilities

### Semantic Metric Applicability

`quantrade/capabilities/fundamental_semantics.py`

Core objects:

- `SemanticMetricRequirement`
- `SemanticMetricApplicabilityInput`
- `SemanticMetricApplicabilityArtifact`

Statuses:

- `READY`
- `MISSING`
- `AMBIGUOUS`

Rules:

- exact IFRS account identity;
- only preregistered statement divisions;
- exact fiscal period;
- exact amount suffix;
- no account-name fallback;
- no issuer-specific alias inference;
- actual resolved statement placement is preserved.

### Valuation Method Applicability

`quantrade/capabilities/valuation_method_applicability.py`

Core objects:

- `DomainCheck`
- `ValuationMethodApplicabilityInput`
- `ValuationMethodApplicabilityArtifact`

Statuses:

- `READY`
- `NOT_APPLICABLE`

The gate never auto-selects a substitute valuation method.

## Adopted future chain

```text
PIT provider
    ↓
Semantic Metric Applicability
    ↓
Valuation Method Applicability
    ↓
method-specific valuation
    ↓
Cross-Method Valuation Gate
    ↓
Portfolio Opportunity Cost
    ↓
Independent Risk
```

If a required method is NOT_APPLICABLE, a mandatory cross-method policy must
not pretend the missing method agreed with the others.

Instead:

`INCOMPLETE_REQUIRED_METHODS`

and downstream Portfolio/Risk remain blocked unless a separately governed
policy explicitly defines another valid method set **before** seeing the Case
result.

## Why automatic substitution is prohibited

Without this gate, a system can accidentally optimize its own conclusion:

```text
P/E fails because earnings are negative
→ switch to P/B
→ P/B looks bad
→ switch to EV/EBITDA
→ keep searching until one method looks attractive
```

That is not robustness. It is post-result method shopping.

QuanTrade must preregister the applicable method family or method-selection
policy before observing the economic output.

## Experiment lineage

### QT-CASE-003

- target: Samsung SDI `006400`
- preregistration:
  `bf59d2b3b147d2a2864c151ba7751a3b136563ed`
- frozen failure run:
  `37866181333`
- source:
  `a02b6700dfa6461ea0d476d46ee7bb0fdcbea526`
- result:
  **PROCESS_PORTABILITY_FAILURE**
- economic valuation: not produced

### QT-CASE-003-CORR-001

- preregistration:
  `1c52896c63cae1f8398dfd276e936e813007e4bb`
- successful corrective run:
  `37866735828`
- frozen source:
  `92c2c77ac93941a55cd47450c2aafe18e68e33d5`
- artifact:
  `11588816078`
- semantic gates: READY
- P/E method: NOT_APPLICABLE
- owner-cash-flow DCF: NOT_APPLICABLE
- Cross-Method status:
  `INCOMPLETE_REQUIRED_METHODS`
- Portfolio: not invoked
- Risk: not invoked

The correction is diagnostic/product-development evidence, **not** a restored
holdout.

## Authority invariant

Both applicability gates always remain non-authoritative:

```text
model_called = false
canonical_evidence_created = false
valuation_created = false
substitute_method_selected = false
portfolio_proposal_created = false
target_weight_set = false
committee_decision_created = false
execution_authorized = false
live_order_possible = false
```

## Next validation rule

The next untouched issuer Case must use the semantic and method-applicability
gates from the beginning.

Do not reuse Samsung SDI as the next holdout.

The next Case should be preregistered before querying its Case-period economic
values and should be allowed to end in:

- READY + valuation;
- MISSING;
- AMBIGUOUS;
- NOT_APPLICABLE;
- CROSS_METHOD_MIXED/REJECTED/CONFIRMED.

All are valid experimental outcomes.
