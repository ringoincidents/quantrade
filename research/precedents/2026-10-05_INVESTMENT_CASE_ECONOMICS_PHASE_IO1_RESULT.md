# Phase IO-1 Result — Investment Case Economics Core

Status: **IMPLEMENTED IN SANDBOX / VERIFIED / NON-AUTHORITATIVE**  
Date: **2026-10-05**  
Direction source: `2026-10-05_INVESTMENT_OFFICE_DECISION_ECONOMICS_DIRECTION.md`

## 1. What changed

QuanTrade now has a deterministic domain capability for evaluating the arithmetic
of an Investment Case.

The implementation deliberately does **not** decide whether a security should be
bought or sold.

It answers a narrower question:

> Given explicit scenario assumptions, current price and a required-return
> hurdle, what are the resulting economics?

Implemented file:

- `quantrade/capabilities/investment_case.py`

Reference harness:

- `quantrade/capabilities/investment_case_evaluation.py`

Tests:

- `tests/capabilities/test_investment_case.py`

## 2. Domain contract

### ScenarioAssumption

Each scenario carries:

- scenario ID;
- label;
- probability;
- fair value;
- optional thesis note;
- Evidence refs;
- assumption refs.

The capability explicitly labels scenario values as **ASSUMPTION** inputs.

A valid probability-weighted calculation does not validate the assumptions as
true.

### ConsensusObservation

Optional external consensus/target input carries:

- source ID;
- observed timestamp;
- target value;
- currency;
- optional horizon;
- methodology/limitation note.

Consensus is comparison-only.

It is not used to calculate QuanTrade's internal probability-weighted value.

## 3. Deterministic calculations

The calculator produces:

- probability-weighted fair value;
- expected return versus current price;
- required-return hurdle;
- expected excess over hurdle;
- hurdle-met boolean;
- lowest/highest scenario fair values;
- lowest/highest scenario returns;
- probability of price loss;
- probability of meeting the return hurdle;
- probability-weighted fair-value standard deviation;
- scenario dispersion as percent of current price;
- optional current-to-consensus return;
- optional internal weighted value versus consensus gap.

No LLM is used for any arithmetic.

## 4. Validation boundaries

The module fails closed when:

- case ID / asset / currency is missing;
- timestamps are invalid or timezone-naive;
- current price is non-positive;
- valuation horizon is non-positive;
- scenario IDs are duplicated;
- probabilities are non-finite or outside 0..1;
- probabilities do not sum to 1 within tolerance;
- fair values are non-positive;
- refs are empty strings;
- consensus currency differs from the Case currency;
- consensus observation is dated after the Case as-of time;
- consensus value is non-positive.

## 5. Authority boundary

Every `InvestmentCaseEconomics` artifact states:

- `model_called = false`
- `canonical_evidence_created = false`
- `thesis_validated = false`
- `portfolio_proposal_created = false`
- `position_size_set = false`
- `risk_opinion_created = false`
- `risk_limit_changed = false`
- `committee_decision_created = false`
- `decision_plan_created = false`
- `paper_authorized = false`
- `execution_authorized = false`
- `live_order_possible = false`

This preserves the canonical separation:

```text
Research economics
!= Portfolio Proposal
!= Risk Opinion
!= Committee Decision
!= Execution
```

## 6. Reference harness behavior

### CASE-REFERENCE-001

Synthetic scenario assumptions:

- Bear: 25%, value 55,000
- Base: 50%, value 120,000
- Bull: 25%, value 170,000
- current price: 100,000
- required return: 15%

Deterministic output:

- weighted fair value: 116,250
- expected return: +16.25%
- hurdle: met
- probability of price loss: 25%
- lowest scenario return: -45%
- highest scenario return: +70%

This intentionally demonstrates:

> positive expected economics can coexist with substantial downside.

No trade authority is created.

### CASE-REFERENCE-002

Synthetic scenario assumptions yield weighted fair value equal to current price.

- expected return: 0%
- required return: 12%
- hurdle: not met

Again, no BUY/SELL output exists.

## 7. Target-price handling precedent

A synthetic sell-side consensus target is included in the first reference Case.

The tests verify that changing/adding this target does **not** alter the
internally calculated weighted fair value.

This is the first executable precedent for:

> analyst target price = external observation, not intrinsic-value authority.

## 8. Verification

GitHub Actions workflow:

`Investment Case Economics Tests`

Latest verified run:

`37263639296`

Result: **SUCCESS**

Evidence from the run:

```text
Investment Case tests: 10 passed
Full capability regression suite: 37 passed
Reference harness: success
```

The regression suite includes existing ReviewGate/FeatureProvider capability
tests from current `main`.

## 9. Organizational mapping

### Research

Owns the scenario assumptions, thesis/evidence relationship and uncertainty.

### Deterministic calculator

Owns arithmetic only.

### Counter-Research

Future Phase IO-2+ may attack assumptions/evidence.

### Portfolio Management

Must separately decide whether an economically attractive Case deserves capital
relative to current holdings, cash and alternatives.

### Risk & Compliance

Must separately judge whether the downside is acceptable.

### Investment Committee

Receives downstream departmental artifacts; this capability never creates a
Committee decision.

## 10. What is intentionally not implemented

Phase IO-1 does not implement:

- DCF;
- PER / EV-EBITDA valuation models;
- DART ingestion;
- analyst-report scraping;
- consensus aggregation;
- automatic scenario probabilities;
- automatic thesis generation;
- Counter-Research model calls;
- Portfolio sizing;
- Risk veto logic;
- BUY / SELL / HOLD recommendation generation;
- PAPER or live execution.

Those are separate governed capabilities.

## 11. Next bounded step

The next useful implementation is **Phase IO-2 — Thesis Contract**.

The goal should be to make a Case unable to hide the difference between:

```text
Observation
Assumption
Inference
Thesis Claim
Contradicting Evidence
Falsification Condition
```

That contract should be implemented before attaching external fundamental data
or LLM-generated research, because otherwise the system will collect more
information without a durable structure for deciding what it means.
