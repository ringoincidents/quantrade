# QT-STRAT-005 — Multi-Stock KRX Transfer Golden Run Result

Status: **COMPLETED / OPERATIONAL SUCCESS / ZERO TRANSFER SURVIVORS**  
Experiment ID: **QT-STRAT-005**  
Pre-registration anchor: `7ea6d1b101cda4e635a2678d96a3b127ad6bb9fc`  
GitHub Actions run: `37260999327`  
Evidence commit: `8f5371b`  
Authority: **RESEARCH ONLY / NO PROMOTION / NO EXECUTION**

## 1. Executive result

QT-STRAT-005 tested the exact same four frozen strategy families from
QT-STRAT-004 across five new KRX stocks:

- `000660`
- `207940`
- `005380`
- `005490`
- `006400`

All five datasets passed integrity checks.

**None of the four strategies passed Stage A.**

Therefore, exactly as pre-registered:

- selected candidates before TEST: **0**
- research-candidate TEST metrics opened: **0**
- TEST-confirmed strategies: **0**
- ReviewGate: **NO_REVIEW**
- specialist Work planned: **0**
- model calls: **0**
- strategy promotion: **0**
- execution authorization: **0**

The experiment therefore succeeded as a pipeline test while rejecting all four
candidate families for this frozen transfer scope.

## 2. Dataset evidence

Every frozen stock returned the same complete historical calendar:

- rows per stock: **1,159**
- first trading date: **2022-01-03**
- last trading date: **2026-09-30**
- TRAIN return periods per stock: **734**
- VALIDATION return periods per stock: **241**
- TEST return periods per stock: **181**
- duplicate dates: **0**
- non-positive close values: **0**
- dates strictly increasing: **yes**

Basket SHA-256:

`c5a9e2efefc74b265d43dbfdb77119daf7c789cc223a189e83c76f5102099db5`

Per-stock hashes are preserved in the machine artifact.

## 3. Frozen methodology

No rule was changed after data fetch.

The experiment used:

- the same four candidate formulas as QT-STRAT-004;
- one-bar execution lag;
- 20.5 bps symmetric KRX cost approximation;
- terminal liquidation cost;
- stock-specific cost-adjusted BUY-HOLD controls;
- cross-sectional median/count summaries;
- TRAIN + VALIDATION selection only;
- TEST available only after candidate selection;
- top-K = 2;
- signal similarity threshold = 0.95.

The experiment is a transferability test, not an equal-weight portfolio
simulation.

## 4. Cost-adjusted BUY-HOLD controls

### TRAIN

| Symbol | Net return | Sharpe | MDD |
|---|---:|---:|---:|
| 000660 | +34.78% | 0.456 | -43.61% |
| 207940 | +4.97% | 0.195 | -25.27% |
| 005380 | +0.30% | 0.152 | -32.92% |
| 005490 | -9.83% | 0.117 | -61.55% |
| 006400 | -62.08% | -0.572 | -69.80% |

### VALIDATION

| Symbol | Net return | Sharpe | MDD |
|---|---:|---:|---:|
| 000660 | +278.76% | 2.826 | -26.92% |
| 207940 | +22.80% | 0.836 | -16.37% |
| 005380 | +39.62% | 1.143 | -21.46% |
| 005490 | +21.50% | 0.718 | -29.67% |
| 006400 | +14.47% | 0.531 | -34.42% |

This shows substantial cross-stock regime dispersion and also an unusually
strong 2025 performance in `000660`.

The benchmark is deliberately stock-specific so a strategy cannot appear
transferable merely because it did well on one strong stock.

## 5. Candidate results

## 5.1 CAND-SMA-5-20

TRAIN:

- stocks beating control: **2/5**
- median excess vs control: **-2.49 percentage points**
- median Sharpe: **-0.019**
- worst MDD: **-57.00%**

VALIDATION:

- stocks beating control: **1/5**
- median excess vs control: **-30.04 percentage points**
- median Sharpe: **-0.010**
- worst MDD: **-27.87%**
- median turnover per period: **0.0664**

Stage A: **REJECTED**

Failed:

- 3-of-5 control-win requirement;
- positive median excess requirement;
- positive median Sharpe requirement.

## 5.2 CAND-SMA-20-60

This was the strongest candidate in TRAIN.

TRAIN:

- stocks beating control: **4/5**
- median excess vs control: **+15.39 percentage points**
- median Sharpe: **0.205**
- median turnover per period: **0.0191**
- worst MDD: **-47.93%**

VALIDATION:

- stocks beating control: **1/5**
- median excess vs control: **-25.68 percentage points**
- median Sharpe: **1.243**
- median turnover per period: **0.0249**
- worst MDD: **-24.85%**

Stage A: **REJECTED**

This is the most informative result in QT-STRAT-005.

The rule looked broadly useful in TRAIN, beating stock-specific BUY-HOLD on
4/5 stocks, but that breadth collapsed to 1/5 in VALIDATION.

Its positive validation Sharpe was not enough to rescue it because the
pre-registered question was **transferability relative to each stock's simple
control**, not whether the strategy itself made money.

Per-stock VALIDATION excess versus control:

- 000660: **-137.21p**
- 207940: **-25.68p**
- 005380: **-4.23p**
- 005490: **-37.20p**
- 006400: **+37.16p**

This is strong evidence of regime/instrument instability for this fixed rule.

## 5.3 CAND-MOM-20

TRAIN:

- stocks beating control: **2/5**
- median excess: **-18.74p**
- median Sharpe: **-0.240**
- worst MDD: **-57.49%**

VALIDATION:

- stocks beating control: **0/5**
- median excess: **-43.10p**
- median Sharpe: **-0.190**
- worst MDD: **-32.79%**
- median turnover per period: **0.1162**

Stage A: **REJECTED**

It failed both the transfer criterion and the -30% worst-MDD criterion.

## 5.4 CAND-ZSCORE-MR-20

TRAIN:

- stocks beating control: **2/5**
- median excess: **-6.75p**
- median Sharpe: **-0.142**
- worst MDD: **-43.37%**

VALIDATION:

- stocks beating control: **0/5**
- median excess: **-29.28p**
- median Sharpe: **0.375**
- worst MDD: **-21.94%**
- median turnover per period: **0.0996**

Stage A: **REJECTED**

Again, a positive median Sharpe did not imply economic edge over the
stock-specific controls.

## 6. Holdout discipline

Stage-A eligible IDs:

```text
[]
```

Selected IDs before TEST:

```text
[]
```

Therefore the runner did not compute research-candidate TEST metrics.

The frozen TEST data and BUY-HOLD controls exist in the dataset/control
artifact, but no failed candidate was given a second chance through TEST.

There was no parameter retuning and no “next-best candidate” substitution.

## 7. Organizational behavior

The system correctly produced:

- `ReviewGate = NO_REVIEW`
- `specialists_planned = 0`
- `specialists_invoked = 0`

This is an important validation of the multi-agent design philosophy.

QuanTrade did **not** call Quant, Counter-Research, Risk, or any debate graph
just because candidate research existed.

The deterministic evidence layer determined that specialist reasoning could
not presently change a promotion decision.

## 8. What QT-STRAT-004 + QT-STRAT-005 jointly say

QT-STRAT-004 showed that none of the four rules beat the frozen 005930
validation benchmark sufficiently to enter review.

QT-STRAT-005 then moved to five different KRX stocks without tuning those
rules.

Again, **0/4 survived**.

This makes the current evidence stronger than a single-stock failure:

> the tested simple technical families have not demonstrated stable,
> cost-aware, benchmark-relative transfer under the current protocol.

This does **not** prove that technical information is useless in general.

It does show that QuanTrade should stop treating these four fixed families as
promising default alpha candidates.

## 9. Important dissent and limitations

### Research dissent

The experiment tests only four simple long/flat technical rules.

Failure of these four rules is not evidence against all systematic strategies.

Preserved.

### Cross-sectional limitation

Five stocks are still a small sample and were drawn from a pre-existing
large-cap research universe.

The experiment does not establish broad KRX market conclusions.

Preserved.

### Benchmark difficulty

Some 2025 BUY-HOLD returns were very strong, especially `000660`.

A candidate can therefore generate positive absolute returns and still fail the
economic edge test.

That is intentional: QuanTrade Value Added should not confuse participation in
a bull move with investment skill.

### Risk limitation

BUY-HOLD controls themselves have large drawdowns in several partitions.

Beating BUY-HOLD is not sufficient for Portfolio/Risk approval.

### Data limitation

Historical price data alone cannot validate:

- fundamentals;
- news;
- corporate-action semantics;
- live execution quality;
- market impact;
- liquidity at intended size.

### Cost limitation

The 20.5 bps symmetric KRX approximation remains a simplification of actual
side-specific costs.

## 10. Experiment verdict

### Strategy Research Sandbox

**ADOPT / KEEP AS RESEARCH INFRASTRUCTURE**

The pipeline has now demonstrated on two real-market experiments that it can:

- pre-register rules;
- freeze data/candidate assumptions;
- enforce one-bar timing;
- include costs;
- compare against explicit controls;
- stop failed candidates before TEST/reasoning;
- avoid unnecessary model calls;
- persist reproducible evidence.

### CAND-SMA-5-20

**REJECT as current default research candidate**

### CAND-SMA-20-60

**REJECT as current default research candidate**

It showed the most interesting TRAIN behavior but failed transfer in
VALIDATION.

### CAND-MOM-20

**REJECT as current default research candidate**

### CAND-ZSCORE-MR-20

**REJECT as current default research candidate**

### LLMCandidateProvider

**STILL DEFER**

The evidence does not say the bottleneck is insufficient idea generation.

Generating hundreds of nearby technical formulas now would risk recreating
parameter fishing at larger scale.

### RL / FinBERT

**DEFER**

No current evidence justifies the complexity.

## 11. Recommended next research direction

Do **not** run SMA 10/30, 15/45, momentum 30, z-score 15, etc. merely because
the present rules failed.

The next meaningful experiment should change the **information family**, not
just the parameter values.

Reasonable candidate directions for a new pre-registered experiment include:

1. deterministic portfolio/risk allocation using existing measured state;
2. event/fundamental hypotheses with point-in-time evidence;
3. volatility/correlation state features;
4. cross-sectional relative-value/ranking hypotheses if a proper historical
   universe contract can be built;
5. specialist reasoning only after a deterministic candidate clears an
   economic gate.

The main lesson is:

```text
broaden evidence
not parameter search
```

## 12. Evidence

- `research/experiments/QT-STRAT-005_PRE_REGISTRATION.md`
- `research/experiments/QT-STRAT-005_DATASET.json`
- `research/experiments/QT-STRAT-005_RESULT.json`
- `scripts/run_qt_strat_005.py`
- `tests/capabilities/test_qt_strat_005_rules.py`
- `.github/workflows/qt_strat_005_transfer_run.yml`

GitHub Actions run: `37260999327` — **SUCCESS**

Evidence commit: `8f5371b`

## 13. Authority

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
