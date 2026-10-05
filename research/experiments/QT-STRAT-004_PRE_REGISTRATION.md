# QT-STRAT-004 — KRX 005930 Golden Run Pre-Registration

Status: **PRE-REGISTERED / RESULTS NOT YET OBSERVED**  
Date registered: **2026-10-05**  
Experiment ID: **QT-STRAT-004**  
Authority: **RESEARCH ONLY / NO STRATEGY PROMOTION / NO EXECUTION**

## 1. Question

Does the Strategy Research Sandbox created in QT-STRAT-001~003 produce a
reproducible, point-in-time, cost-aware research decision on one frozen stock
MarketScope without reverting to the old ad-hoc “try another signal until one
looks good” loop?

A valid outcome is **zero surviving strategies**.

The experiment is not required to find alpha.

## 2. Frozen MarketScope

- Asset class: **KRX equity**
- Instrument: **005930 (Samsung Electronics)**
- Bar type: **daily**
- Source: Naver historical price endpoint
  - `https://api.finance.naver.com/siseJson.naver`
- Request mode: explicit start/end dates
- Frozen date range: **2022-01-03 through 2026-09-30**
- No news, fundamentals, portfolio holdings, client constraints, or live prices are inputs.
- No current/future bar after 2026-09-30 may enter the experiment.

Single-asset scope avoids changing the universe after observing performance and
avoids cross-sectional survivorship claims. It does **not** prove transfer to
other stocks or markets.

## 3. Frozen partitions

Partitions are fixed before fetching results:

- TRAIN: **2022-01-03 through 2024-12-31**
- VALIDATION: **2025-01-01 through 2025-12-31**
- TEST: **2026-01-01 through 2026-09-30**

Signals are compiled once on the complete chronologically ordered dataset so
lookback windows can use only prior history across partition boundaries.
Metrics are then sliced by return period.

No parameter is re-fit on validation or test.

## 4. Frozen candidate set

### CONTROL-BUY-HOLD

Role: cost-adjusted benchmark control.

Target position is always 1.0.

This is not an alpha candidate and is excluded from top-K research selection.

### CAND-SMA-5-20

```json
{
  "op": "GT",
  "left": {"op": "SMA", "window": 5},
  "right": {"op": "SMA", "window": 20}
}
```

### CAND-SMA-20-60

```json
{
  "op": "GT",
  "left": {"op": "SMA", "window": 20},
  "right": {"op": "SMA", "window": 60}
}
```

### CAND-MOM-20

```json
{
  "op": "GT",
  "left": {"op": "RETURN", "window": 20},
  "right": {"op": "CONST", "value": 0.0}
}
```

### CAND-ZSCORE-MR-20

```json
{
  "op": "LT",
  "left": {"op": "ZSCORE", "window": 20},
  "right": {"op": "CONST", "value": -1.0}
}
```

No candidate may be added, removed, or parameter-tuned after the first market
result is observed. A future experiment may use different candidates, but it
must receive a new experiment ID.

## 5. Frozen signal timing

The safe DSL may calculate a condition using the close of bar `t`, but this
Golden Run does **not** allow that condition to earn the return starting at the
same close.

A one-bar execution lag is frozen before data is fetched:

```text
condition computed using information through close(t-1)
→ target position becomes effective at close(t)
→ evaluated return is close(t) → close(t+1)
```

For the first evaluable return period, the target position is flat because no
prior compiled condition exists.

This is stricter than the Phase 2 reference compiler's immediate
close-to-next-close convention and is chosen to avoid assuming that the exact
closing price can be both observed and executed without delay.

The final artifact must report that the one-bar lag was applied.

## 7. Frozen friction model

Existing QuanTrade KRX assumptions:

- fee: 0.015% each side
- slippage: 0.10% each side
- sell tax: 0.18% sell side

The Phase 1 evaluator currently uses one symmetric bps cost per absolute
position turnover. For this Golden Run the fixed approximation is:

```text
buy one-way = 0.015% + 0.10% = 0.115%
sell one-way = 0.015% + 0.10% + 0.18% = 0.295%
average one-way = (0.115% + 0.295%) / 2 = 0.205% = 20.5 bps
```

Therefore:

- `transaction_cost_bps = 20.5`

The cost-adjusted BUY-HOLD control is evaluated with the same symmetric model,
so the candidate comparison is internally consistent.

This approximation is a known limitation and is not silently upgraded after
results.

## 6. Frozen deterministic eligibility gate

A candidate is **eligible for bounded specialist review** only if all are true:

1. no look-ahead/timing violation;
2. VALIDATION return periods >= 100;
3. TEST return periods >= 100;
4. VALIDATION net return > cost-adjusted BUY-HOLD control net return;
5. TEST net return > cost-adjusted BUY-HOLD control net return;
6. VALIDATION Sharpe > 0;
7. TEST Sharpe > 0;
8. TEST maximum drawdown >= -20%;
9. TEST turnover per period <= 0.25.

These criteria create research-review eligibility only.

Passing does not mean validated alpha, Portfolio approval, Risk approval,
Investment Committee approval, StrategyPassport promotion, PAPER authority, or
execution authority.

## 8. Duplicate and review budget

For eligible candidates:

- signal-path similarity threshold: **0.95**
- maximum candidates retained for bounded review: **top_k = 2**

Planned specialist roles for this Golden Run:

- Quant / Market
- Counter-Research
- Risk & Compliance

Portfolio Management is **not** planned because this experiment intentionally
does not consume the client's current portfolio.

Deep External Research is **not** planned because the four candidates have no
external theory/source dependency.

If no candidate is eligible, no specialist Work should be created.

## 9. Dataset integrity requirements

The runner must persist or report:

- exact source endpoint and request parameters;
- first and last returned trading date;
- row count;
- strictly increasing dates;
- no duplicate dates;
- no null/non-positive close values;
- SHA-256 hash of canonicalized returned date/close rows;
- partition row/return counts.

The dataset is considered historical price data only. This experiment does not
claim point-in-time correctness for fundamentals, news, index membership, or
corporate information.

## 10. Experiment-level success/failure

The **pipeline experiment** is successful if:

- the frozen dataset can be fetched and integrity-checked;
- all frozen candidates are evaluated reproducibly;
- train/validation/test results are produced with the pre-registered costs;
- the eligibility rules are applied without post-result modification;
- rejected/suppressed/selected candidates are all explicitly recorded;
- no model call, order path, or automatic promotion occurs.

The experiment remains informative if every candidate fails.

The experiment fails operationally if data fetch/integrity/reproducibility fails.

## 11. No post-result edits rule

After the first market result is observed, the following are frozen:

- instrument;
- dates;
- partitions;
- candidates;
- parameters;
- cost model;
- eligibility thresholds;
- similarity threshold;
- top-K.

A code bug may be fixed only if:

1. the failed behavior is documented;
2. the original result is not deleted;
3. the fix does not introduce a result-dependent rule change;
4. the run is marked as a new attempt under the same pre-registration.

## 12. Authority invariant

This experiment must always report:

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

## 13. Registration rule

This document is committed before the runner is allowed to fetch the first
005930 market result. Its commit SHA is the pre-registration anchor and must be
copied into the final experiment artifact.
