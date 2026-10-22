# QT-STRAT-005 — Multi-Stock KRX Transfer Golden Run Pre-Registration

Status: **PRE-REGISTERED / RESULTS NOT YET OBSERVED**  
Date registered: **2026-10-05**  
Experiment ID: **QT-STRAT-005**  
Authority: **RESEARCH ONLY / NO STRATEGY PROMOTION / NO EXECUTION**

## 1. Question

Do the four strategy families frozen in QT-STRAT-004 show enough
cross-sectional transfer across a new, previously unobserved KRX basket to
justify bounded specialist review?

This experiment tests **transferability of the research pipeline and candidate
families**, not portfolio optimization and not live tradability.

A valid outcome is zero surviving strategies.

## 2. Frozen MarketScope

Asset class: **KRX equities**  
Bar type: **daily**  
Source: Naver historical price endpoint  
Requested date range: **2022-01-03 through 2026-09-30**

Frozen instruments:

1. `000660`
2. `207940`
3. `005380`
4. `005490`
5. `006400`

Selection rationale, frozen before market fetch:

- all five belong to the repository's pre-existing static
  `KRX_MARKET_CAP_TOP` research universe;
- none was used as a research candidate instrument in QT-STRAT-004;
- `005930` is excluded because its performance was already observed in
  QT-STRAT-004;
- `373220` is excluded because its listing date falls after the experiment
  start window, which would make the full TRAIN comparison structurally
  different;
- no instrument is selected or excluded based on QT-STRAT-005 performance.

No substitutions are allowed if one instrument performs poorly. If data
integrity fails for any frozen instrument, the experiment is operationally
failed and must receive a documented retry or a new experiment ID.

## 3. Frozen partitions

- TRAIN: **2022-01-03 through 2024-12-31**
- VALIDATION: **2025-01-01 through 2025-12-31**
- TEST: **2026-01-01 through 2026-09-30**

Each stock is evaluated on its own observed trading bars.

No cross-stock price imputation or forward-fill is allowed.

The TEST partition is not opened for a candidate until that candidate is
selected using TRAIN + VALIDATION only.

## 4. Frozen candidate set

The candidate set is copied unchanged from QT-STRAT-004.

### CAND-SMA-5-20

```json
{"op":"GT","left":{"op":"SMA","window":5},"right":{"op":"SMA","window":20}}
```

### CAND-SMA-20-60

```json
{"op":"GT","left":{"op":"SMA","window":20},"right":{"op":"SMA","window":60}}
```

### CAND-MOM-20

```json
{"op":"GT","left":{"op":"RETURN","window":20},"right":{"op":"CONST","value":0.0}}
```

### CAND-ZSCORE-MR-20

```json
{"op":"LT","left":{"op":"ZSCORE","window":20},"right":{"op":"CONST","value":-1.0}}
```

No candidate, parameter, threshold, or formula may be changed after the first
QT-STRAT-005 market result is observed.

## 5. Frozen signal timing

The same one-bar execution lag as QT-STRAT-004 is mandatory:

```text
condition computed through close(t-1)
→ target position effective at close(t)
→ evaluated return close(t) → close(t+1)
```

No same-close observation/execution assumption is allowed.

## 6. Frozen friction model

Same as QT-STRAT-004:

- fee each side: 0.015%
- slippage each side: 0.10%
- sell tax: 0.18%
- symmetric average one-way approximation: **20.5 bps**
- terminal liquidation charged at partition end

Every candidate and every per-stock BUY-HOLD control uses the same evaluator
and cost approximation.

## 7. Cross-sectional aggregation rule

For each candidate and partition, calculate per-stock metrics first.

Then derive only these cross-sectional summaries:

- median net return;
- median Sharpe across non-null Sharpe values;
- median turnover per period;
- worst maximum drawdown;
- count of stocks where candidate net return exceeds that stock's
  cost-adjusted BUY-HOLD control;
- median candidate excess return versus stock-specific cost-adjusted control.

This experiment does **not** average raw prices and does not claim to simulate
an equal-weight portfolio.

The goal is transferability across independent instruments.

## 8. Stage A — review eligibility using TRAIN + VALIDATION only

A candidate is Stage-A eligible only if all are true:

1. all five instruments pass dataset integrity checks;
2. TRAIN has at least 200 return periods for each instrument;
3. VALIDATION has at least 100 return periods for each instrument;
4. candidate beats stock-specific cost-adjusted BUY-HOLD on at least **3 of 5**
   VALIDATION instruments;
5. median VALIDATION excess versus control is **> 0 percentage points**;
6. median VALIDATION Sharpe is **> 0**;
7. worst VALIDATION maximum drawdown is **>= -30%**;
8. median VALIDATION turnover per period is **<= 0.25**.

TRAIN performance is recorded for context and reproducibility but is not used
to retune parameters or replace candidates.

## 9. Duplicate suppression and top-K

Only Stage-A eligible candidates enter duplicate suppression.

- signal-path similarity is calculated by concatenating TRAIN + VALIDATION
  long/flat positions in the frozen instrument order;
- similarity threshold: **0.95**
- maximum retained candidates: **top_k = 2**

Research priority for eligible candidates:

1. larger count of VALIDATION stocks beating control;
2. higher median VALIDATION excess versus control;
3. higher median VALIDATION Sharpe;
4. lower median VALIDATION turnover;
5. deterministic candidate ID tie-break.

This ordering is a research-budget rule, not an investment score.

## 10. Stage B — frozen TEST confirmation

Only candidates selected before TEST is opened receive TEST metrics.

A selected candidate is TEST-confirmed only if all are true:

1. TEST has at least 100 return periods for each instrument;
2. candidate beats stock-specific cost-adjusted BUY-HOLD on at least **3 of 5**
   TEST instruments;
3. median TEST excess versus control is **> 0 percentage points**;
4. median TEST Sharpe is **> 0**;
5. worst TEST maximum drawdown is **>= -30%**;
6. median TEST turnover per period is **<= 0.25**.

TEST cannot be used to substitute a different candidate after selection.

## 11. Specialist-review policy

If zero candidates survive Stage A:

- ReviewGate = NO_REVIEW
- no specialist Work is planned.

If one or more candidates survive Stage A, selected candidates may create only:

- Quant / Market
- Counter-Research
- Risk & Compliance

Portfolio Management is excluded because QT-STRAT-005 is a transferability
experiment, not a current-client portfolio experiment.

Deep External Research is excluded because these strategies have no external
theory/source dependency.

Default budget per Work:

- max model calls: 1
- max tool rounds: 3

The experiment itself does not invoke the Work. It only plans it.

## 12. Dataset integrity requirements

For each frozen stock persist/report:

- endpoint and request params;
- row count;
- first/last returned date;
- strictly increasing dates;
- duplicate-date count;
- non-positive-close count;
- SHA-256 of canonicalized OHLCV rows;
- partition bar/return-period counts.

Also persist a basket hash created from the ordered tuple:

`symbol + per-stock SHA-256`

No stock may be silently dropped.

## 13. Experiment success

Pipeline success means:

- all five datasets are fetched and pass integrity checks;
- all frozen candidates are evaluated reproducibly;
- Stage A is applied without post-result changes;
- TEST remains unopened for unselected candidates;
- rejected/suppressed/selected candidates are explicit;
- model calls remain zero;
- no PAPER or execution authority is created.

Finding alpha is not required.

## 14. No post-result edits rule

After the first QT-STRAT-005 market result is observed, freeze:

- stock basket;
- dates;
- partitions;
- candidates;
- parameters;
- cost model;
- one-bar lag;
- Stage-A rules;
- similarity threshold;
- top-K;
- Stage-B rules.

Bug fixes require preserved failure evidence and a documented new attempt.

## 15. Authority invariant

```text
model_called = false
canonical_evidence_created = false
portfolio_proposal_created = false
risk_limit_changed = false
strategy_approved = false
investment_decision_created = false
paper_promotion_authorized = false
execution_authorized = false
live_order_possible = false
```

## 16. Registration rule

This document is committed before any QT-STRAT-005 runner is allowed to fetch
the first market result. Its commit SHA is the pre-registration anchor copied
into every machine artifact.
