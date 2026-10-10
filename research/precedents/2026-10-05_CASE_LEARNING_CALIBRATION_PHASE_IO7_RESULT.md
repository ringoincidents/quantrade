# Phase IO-7 Result — Investment Case Learning & Calibration

Status: **IMPLEMENTED IN SANDBOX / VERIFIED / DESCRIPTIVE LEARNING ONLY**  
Date: **2026-10-05**

## 1. Purpose

QuanTrade now has deterministic layers for:

- point-in-time fundamental evidence;
- Thesis / Counter-Thesis / Falsification;
- Scenario economics;
- Portfolio opportunity cost;
- independent Risk Opinion;
- InstitutionalKernel handoff design.

The remaining research-domain gap was learning.

The question is not:

> "Did price go up?"

The useful question is:

> "Were the frozen expectations calibrated, did the Thesis survive its
> falsification tests, and did the opportunity outperform its simple
> counterfactual benchmark?"

IO-7 implements that evaluation without creating a new Performance/P&L system.

Actual Client capital performance remains the responsibility of the existing
institutional `PerformanceCapitalLoop`.

## 2. Implemented files

Core:

`quantrade/capabilities/case_learning.py`

Reference harness:

`quantrade/capabilities/case_learning_evaluation.py`

Tests:

`tests/capabilities/test_case_learning.py`

## 3. Frozen forecast inputs

IO-7 consumes an already-frozen:

`InvestmentCaseEconomics`

and therefore reuses the assumptions that existed before the outcome:

- entry/current price;
- probability-weighted fair value;
- expected return;
- required-return hurdle;
- probability of price loss;
- probability of meeting the return hurdle;
- lowest/highest scenario fair values.

It does not recompute historical forecasts with knowledge of the outcome.

## 4. Outcome Snapshot

The later outcome carries:

- Case ID;
- evaluation timestamp;
- realized asset price;
- benchmark return over the same evaluation period;
- source references.

Rules:

- outcome must occur after the Case as-of;
- realized price must be positive;
- benchmark return must be finite;
- at least one outcome source reference is required.

## 5. Return forecast error

The deterministic review calculates:

```text
realized return
= realized price / entry price - 1
```

and:

```text
return forecast error
= realized return - expected return
```

It also reports absolute forecast error and the realized price's deviation from
the probability-weighted fair value.

This is forecast-quality evidence, not an investment recommendation.

## 6. Benchmark comparison

The artifact reports:

```text
counterfactual excess vs benchmark
= realized asset return - benchmark return
```

The field is deliberately named **counterfactual**.

It does not claim actual QuanTrade portfolio value added because the Case may
have been:

- rejected;
- watched;
- sized differently;
- never executed.

Actual portfolio performance belongs in the institutional performance layer.

## 7. Probability calibration

Scenario economics already supplies two clearly testable probabilities:

### Loss event

Forecast:

`P(realized price < entry price)`

Outcome:

0 or 1.

IO-7 records the per-Case Brier component:

```text
(predicted probability - actual event)^2
```

### Required-return hurdle event

Forecast:

`P(realized return >= required return)`

Outcome:

0 or 1.

A second Brier component is stored.

These components can later be aggregated across many Cases.

## 8. Thesis falsification

Every Thesis Contract already requires explicit Falsification Conditions.

IO-7 requires one result for every frozen condition:

- `TRIGGERED`
- `NOT_TRIGGERED`
- `UNRESOLVED`

Resolved results require source references.

Falsification observations cannot occur after the outcome evaluation timestamp.

Overall Thesis learning status:

- any triggered condition → `FALSIFIED`
- otherwise any unresolved condition → `UNRESOLVED`
- otherwise → `NOT_FALSIFIED`

## 9. Important separation: Thesis correctness vs price result

The reference harness deliberately demonstrates:

### Case A

- realized asset return: positive;
- Thesis falsification: **TRIGGERED**.

Result:

`FALSIFIED`

A profitable price outcome does not prove the Thesis was correct.

### Case B

- realized asset return: negative;
- falsification condition: **NOT_TRIGGERED**.

Result:

`NOT_FALSIFIED`

A negative price outcome does not automatically prove the original causal
Thesis was false.

This prevents outcome bias from rewriting the investment record.

## 10. Cross-Case calibration aggregate

`aggregate_case_calibration()` calculates descriptive multi-Case metrics:

- mean return forecast error;
- mean absolute return forecast error;
- mean loss-event Brier score;
- mean hurdle-event Brier score;
- mean counterfactual excess versus benchmark;
- falsified Case count;
- unresolved Case count.

It explicitly reports:

```text
statistical_significance_established = false
actual_portfolio_value_added_measured = false
```

Descriptive aggregation is not proof of alpha.

## 11. Reference harness numbers

The synthetic reference forecast has:

- entry price: 100
- expected return: +20%
- loss probability: 25%
- hurdle probability: 75%

Case A realizes price 110:

- realized return: +10%
- forecast error: -10%p
- benchmark return: +8%
- counterfactual excess: +2%p
- loss-event Brier: 0.0625
- hurdle-event Brier: 0.0625
- Thesis: FALSIFIED

Case B realizes price 80:

- realized return: -20%
- forecast error: -40%p
- benchmark return: +8%
- counterfactual excess: -28%p
- loss-event Brier: 0.5625
- hurdle-event Brier: 0.5625
- Thesis: NOT_FALSIFIED

Two-Case descriptive aggregate:

- mean forecast error: -25%p
- mean absolute forecast error: 25%p
- mean loss Brier: 0.3125
- mean hurdle Brier: 0.3125

These values are fixtures only.

## 12. Authority invariant

Every CaseLearningArtifact states:

```text
model_called = false
canonical_evidence_created = false
portfolio_proposal_created = false
risk_opinion_created = false
committee_decision_created = false
decision_plan_created = false
performance_record_created = false
paper_authorized = false
execution_authorized = false
live_order_possible = false
```

Learning cannot silently create a new trade.

## 13. Verification

Latest Investment Office Core CI:

`37268309033`

Result: **SUCCESS**

Observed:

- Investment Case Economics: **10 passed**
- Thesis Contract: **12 passed**
- PIT Fundamental Evidence: **11 passed**
- Open DART Provider: **12 passed**
- Portfolio Opportunity Cost: **12 passed**
- Independent Risk Opinion: **12 passed**
- Case Learning & Calibration: **12 passed**
- full capability regression suite: **108 passed**
- all reference harnesses: success

## 14. Relationship to existing institutional PerformanceCapitalLoop

The architecture line already contains `PerformanceCapitalLoop`, which records:

- actual Client period performance;
- economic P&L;
- fees/taxes;
- cash/reinvestment reconciliation;
- learning Work generation.

IO-7 does not duplicate it.

The intended future integration is:

```text
CaseLearningArtifact
        ↓
strategy / thesis performance state
        ↓
existing PerformanceCapitalLoop
        ↓
learning WorkOrder when review is warranted
```

That should be implemented as an adapter after branch reconciliation.

## 15. Current closed-loop architecture

The intended full program is now represented as:

```text
PIT Evidence
→ Thesis
→ Scenario Economics
→ Portfolio Opportunity Cost
→ Independent Risk
→ Institutional Committee
→ Governed Decision
→ Outcome
→ Forecast / Thesis Calibration
→ existing Performance & Capital Learning
```

The major remaining blocker for a **real** Investment Case Golden Run is now
external data availability/configuration rather than missing core domain
structure.

The Open DART live probe ran in safe mode on 2026-10-05 and confirmed that the
repository currently has **no `OPEN_DART_API_KEY` secret configured**.

No live DART data was fabricated or substituted.
