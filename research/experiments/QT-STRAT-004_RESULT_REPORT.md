# QT-STRAT-004 — Golden Run Result Report

Status: **COMPLETED / OPERATIONAL SUCCESS / ZERO STRATEGY SURVIVORS**  
Experiment ID: **QT-STRAT-004**  
Pre-registration anchor: `8ea6b3ff2a08466923bb78df49cdbfb26f83b599`  
GitHub Actions run: `37260197583`  
Evidence commit: `ca2e447`  
Authority: **RESEARCH ONLY / NO PROMOTION / NO EXECUTION**

## 1. Executive result

The first real-market Golden Run of the Strategy Research Sandbox completed
successfully on the frozen KRX 005930 daily scope.

The important result is not that a strategy won.

**None of the four pre-registered candidates passed Stage A.**

Therefore, exactly as pre-registered:

- the TEST holdout was not opened for any candidate;
- no candidate entered top-K;
- no specialist Work was planned;
- no model was called;
- no Portfolio/Risk/Committee authority was created;
- no PAPER or execution promotion occurred.

This is a successful test of the **research process**, not evidence of alpha.

## 2. Dataset evidence

Frozen source:

- instrument: `005930`
- source: Naver historical daily endpoint
- requested window: 2022-01-03 through 2026-09-30
- returned rows: **1,159**
- first trading date: **2022-01-03**
- last trading date: **2026-09-30**
- duplicate dates: **0**
- non-positive close values: **0**
- dates strictly increasing: **yes**
- dataset SHA-256:
  `fd19aebd91cd68d03fbfc41b417e195944b6f06ef6c5a225fb3ff7a6fb6a2c6b`

Partitions:

| Partition | Bars | Return periods | First | Last |
|---|---:|---:|---|---|
| TRAIN | 735 | 734 | 2022-01-03 | 2024-12-30 |
| VALIDATION | 242 | 241 | 2025-01-02 | 2025-12-30 |
| TEST | 182 | 181 | 2026-01-02 | 2026-09-30 |

A one-bar execution lag was applied exactly as pre-registered.

## 3. Frozen cost-adjusted control

The BUY-HOLD control used the same symmetric KRX cost approximation as the
candidates:

- 20.5 bps per unit turnover;
- terminal liquidation charged;
- total control turnover per partition: 2.0.

### Control metrics

| Partition | Net return | Sharpe | MDD |
|---|---:|---:|---:|
| TRAIN | -32.59% | -0.397 | -43.17% |
| VALIDATION | +123.62% | 2.625 | -14.67% |
| TEST | +108.89% | 1.634 | -42.90% |

The large regime difference is itself useful evidence: this single stock moved
from a weak TRAIN period into exceptionally strong VALIDATION/TEST price
performance. No claim is made that this pattern generalizes.

## 4. Candidate results

### CAND-SMA-5-20

TRAIN:

- net return: **-10.00%**
- Sharpe: **-0.166**
- MDD: **-24.73%**
- turnover: **46.0**
- estimated cost drag input: **9.43% of initial equity**

VALIDATION:

- net return: **+40.18%**
- Sharpe: **1.370**
- MDD: **-25.60%**
- turnover per period: **0.0747**
- excess versus cost-adjusted control: **-83.44 percentage points**

Stage A: **REJECTED**

Failed:

- validation did not beat the control;
- validation MDD was worse than -20%.

### CAND-SMA-20-60

TRAIN:

- net return: **-23.95%**
- Sharpe: **-0.488**
- MDD: **-29.52%**

VALIDATION:

- net return: **+91.27%**
- Sharpe: **2.288**
- MDD: **-14.67%**
- turnover per period: **0.0166**
- excess versus cost-adjusted control: **-32.36 percentage points**

Stage A: **REJECTED**

Failed:

- validation did not beat the control.

This was the closest of the four candidates to the control, but the
pre-registered rule does not allow “close enough” to replace the benchmark
criterion.

### CAND-MOM-20

TRAIN:

- net return: **-27.50%**
- Sharpe: **-0.678**
- MDD: **-29.39%**
- estimated transaction-cost amount: **11.48% of initial equity**

VALIDATION:

- net return: **+56.70%**
- Sharpe: **1.704**
- MDD: **-21.06%**
- turnover per period: **0.1245**
- excess versus cost-adjusted control: **-66.93 percentage points**

Stage A: **REJECTED**

Failed:

- validation did not beat the control;
- validation MDD was worse than -20%.

### CAND-ZSCORE-MR-20

TRAIN:

- gross return: **+8.67%**
- net return after costs: **-14.00%**
- Sharpe: **-0.269**
- total turnover: **114**
- estimated transaction-cost amount: **23.37% of initial equity**

VALIDATION:

- net return: **+1.26%**
- Sharpe: **0.167**
- MDD: **-14.07%**
- excess versus cost-adjusted control: **-122.36 percentage points**

Stage A: **REJECTED**

Failed:

- validation did not beat the control.

This candidate is a particularly useful control case because its TRAIN gross
return was positive while cost-adjusted net return became negative. That is
exactly the kind of strategy that an idea-first workflow can overrate if
turnover/friction is not treated as first-class evidence.

## 5. Holdout discipline result

Pre-registration required that TEST be opened only for candidates already
selected using TRAIN + VALIDATION.

Stage A eligible candidates:

```text
[]
```

Selected candidates before TEST:

```text
[]
```

Therefore:

- TEST metrics were **not calculated for any research candidate**;
- TEST-confirmed candidate count is **0**;
- there was no post-hoc substitution of “the next best” candidate.

The TEST control was calculated only to establish and preserve the frozen
benchmark artifact. It was not used to rescue or select a candidate.

## 6. Review / multi-agent behavior

Because zero candidates survived Stage A:

- ReviewGate result: **NO_REVIEW**
- specialist Work planned: **0**
- specialist Work invoked: **0**
- model calls: **0**

This is a meaningful result for the TradingAgents-inspired integration.

The system did **not** manufacture a Bull/Bear/Trader/Risk debate merely because
an experiment existed.

The deterministic layer correctly stopped the workflow before expensive
reasoning.

## 7. What this says about the old QuanTrade loop

The historical QuanTrade process repeatedly tried signals and then inspected
backtest outcomes.

QT-STRAT-004 behaved differently:

1. scope was frozen before results;
2. candidate set was frozen before results;
3. costs were frozen before results;
4. timing lag was frozen before results;
5. eligibility rules were frozen before results;
6. holdout access was conditional and was not triggered;
7. rejected ideas did not generate another ad-hoc parameter search.

This is the main positive result of the experiment.

The Strategy Research Sandbox changed the **research behavior** even though it
did not discover a strategy.

## 8. Dissent / limitations preserved

### Research objection

A single-stock test is narrow. A trend strategy may have value across a
cross-sectional or multi-asset universe even if it loses to one stock during a
very strong rally.

This objection is valid, but it does not change QT-STRAT-004.

### Performance & Learning objection

The benchmark experienced +123.62% validation performance. That makes
benchmark outperformance unusually demanding during this particular period.

Also valid. The response is **not** to weaken the criterion after observing the
result. A new MarketScope requires a new pre-registered experiment.

### Risk objection

The TEST BUY-HOLD control itself experienced approximately -42.90% MDD while
returning +108.89%.

This demonstrates why return alone cannot be the Portfolio/Risk decision.

It also reinforces that “beat Buy & Hold” is a research criterion, not a risk
approval criterion.

### Methodology limitation

The symmetric 20.5 bps cost approximation is not exact side-specific KRX
execution accounting.

It was frozen before the run, applied consistently, and should be improved only
in a future experiment.

### Data limitation

This experiment validates historical daily prices only.

It says nothing about point-in-time fundamentals, news, corporate actions,
universe membership, or live fill quality.

## 9. Experiment verdict

### Pipeline

**ADOPT AS RESEARCH INFRASTRUCTURE, KEEP SANDBOX AUTHORITY**

Evidence:

- real external data fetched successfully;
- immutable dataset hash recorded;
- pre-registration anchor verified in CI;
- one-bar timing applied;
- transaction friction materially affected results;
- deterministic gate rejected all candidates without rule changes;
- TEST holdout stayed closed;
- no unnecessary model calls were produced;
- artifacts were persisted and CI completed successfully.

### Four tested strategies

**REJECT FOR THIS MARKET SCOPE / DATE RANGE**

This is not a permanent global rejection of SMA, momentum, or mean-reversion
families. It is specifically the outcome of QT-STRAT-004.

### LLM candidate generator

**DO NOT ADD YET**

The experiment has not shown that candidate scarcity is the bottleneck.

The larger need is broader, still-pre-registered research coverage without
returning to parameter fishing.

### RL / FinBERT / hierarchical agent expansion

**DEFER**

No evidence from this run justifies adding those layers.

## 10. Next experiment candidate

If continued, the next experiment should receive a new ID and test whether the
same frozen pipeline is useful across a **small pre-registered multi-stock KRX
scope** rather than tuning the four failed 005930 candidates.

Recommended principle:

```text
broaden independent MarketScope
not
retune failed parameters until something passes
```

A sensible next design would use a frozen basket and cross-asset aggregation,
while preserving:

- one-bar timing;
- cost accounting;
- TRAIN / VALIDATION / TEST separation;
- top-K;
- no TEST-based substitution;
- no automatic strategy promotion.

## 11. Evidence files

- `research/experiments/QT-STRAT-004_PRE_REGISTRATION.md`
- `research/experiments/QT-STRAT-004_DATASET.json`
- `research/experiments/QT-STRAT-004_RESULT.json`
- `scripts/run_qt_strat_004.py`
- `.github/workflows/qt_strat_004_golden_run.yml`

GitHub Actions run result: **SUCCESS**

The evidence commit was written by GitHub Actions after artifact verification.

## 12. Authority

Final experiment state:

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
