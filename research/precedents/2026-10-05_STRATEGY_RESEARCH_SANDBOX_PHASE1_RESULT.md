# Strategy Research Sandbox Phase 1 — Result

Status: **SANDBOX IMPLEMENTED / NOT PROMOTED**  
Date: **2026-10-05**  
Parent: `2026-10-05_STRATEGY_RESEARCH_SANDBOX_IMPLEMENTATION_PLAN.md`  
Execution mode: **single-model organizational simulation; not independent review**

## 1. Why Phase 1 was built

The implementation deliberately starts from the experiments QuanTrade already ran instead of treating the new LLM-trading papers as a clean slate.

Historical evidence already says that candidate-generation enthusiasm is not enough:

- the original MA/ADX/RSI strategy produced **583 trades**, validation Sharpe-like **-0.055**, validation MDD **-30.82%**, underperformed Buy & Hold in train and validation, and failed its gate;
- Experiment B produced **577 trades**, validation Sharpe-like **0.049**, validation MDD **-29.69%**, still underperformed Buy & Hold, and failed its gate;
- the seven technical-indicator significance candidates all ended **우위 없음(폐기)** after the pre-registered multiple-testing process;
- the 706-record historical news-direction track was below its simple majority baseline, and the later live cohort also showed no significant D+1/D+5 confidence advantage under the pre-registered Fisher test;
- QT-LIVE-001's SMA trend control is explicitly an **infrastructure baseline, not validated alpha**;
- QT-LIVE-002 still has partial decision-economics telemetry, so missing model cost/latency cannot be interpreted as zero;
- QT-LIVE-003 ReviewGate shadow agreed with the existing routing intent on the observed Client mandate conflict, but actual AI-call cost/latency remains unobserved and claimed savings remain zero.

Therefore Phase 1 does not attempt to discover alpha. It builds a trustworthy measurement boundary that future candidate generators must pass through.

## 2. Historical lessons encoded into code

The new evaluator makes the following requirements executable:

1. **Point-in-time data is mandatory.**
   - A dataset that is not declared point-in-time fails closed.
   - The declaration must carry a provenance/evidence reference.
   - Each signal has an `information_cutoff`; if it is later than the signal's effective timestamp, the evaluation raises `LookaheadDetected`.

2. **Transaction cost is explicit.**
   - Position turnover is measured deterministically.
   - Cost is charged on each absolute position change, including the initial move from flat.
   - High-turnover behavior can therefore look acceptable before friction and fail after friction.

3. **Benchmark is explicit.**
   - Every evaluation reports the same-series Buy & Hold reference and benchmark excess return.
   - A research candidate cannot be discussed as “good” without the comparator being visible.

4. **Missing/invalid market data fails closed.**
   - No silent zero fill.
   - No implicit missing-price imputation.

5. **Deterministic measurement comes before reasoning.**
   - No LLM call exists in this module.
   - Candidate generation, Counter-Research, and synthesis remain later stages.

6. **Research authority stays separate from capital authority.**
   - Every result says:
     - `canonical_evidence_created = false`
     - `portfolio_proposal_created = false`
     - `risk_limit_changed = false`
     - `investment_decision_created = false`
     - `execution_authorized = false`
     - `live_order_possible = false`

7. **v1 is long-only.**
   - Target position is bounded to 0..1.
   - Shorting/leverage is intentionally excluded instead of being silently assumed.

## 3. Implemented files

- `quantrade/capabilities/strategy_research.py`
  - `CandidateStrategy`
  - `PriceBar`
  - `PositionSignal`
  - `DatasetMetadata`
  - `ScreeningPolicy`
  - deterministic `evaluate_strategy()`
  - return / annualized return / volatility / Sharpe / Sortino / MDD / Calmar / turnover / cost / benchmark metrics
  - point-in-time and look-ahead validation
  - non-authority contract

- `quantrade/capabilities/strategy_research_evaluation.py`
  - deterministic synthetic reference dataset
  - Buy & Hold reference
  - SMA crossover reference
  - high-turnover negative-control style candidate
  - explicit future-information leakage negative control
  - cost/no-cost comparison

- `tests/capabilities/test_strategy_research.py`
  - deterministic-repeatability test
  - non-authority test
  - point-in-time failure test
  - point-in-time evidence-reference test
  - future-information rejection test
  - transaction-cost degradation test
  - benchmark-underperformance rejection test
  - missing-data fail-closed test
  - reference-experiment safety lesson test

- `scripts/run_strategy_research_evaluation.py`
  - prints the deterministic reference experiment artifact

## 4. Local verification

The exact Phase 1 logic was exercised locally before repository write.

Result:

```text
8 tests
8 passed
0 failed
```

This is local verification only. It is not CI evidence and does not promote the capability.

## 5. Reference experiment observations

The synthetic fixture is intentionally a test instrument, not an alpha claim.

With 50 bps cost:

### Buy & Hold reference

- gross total return: approximately **7.66%**
- net total return: approximately **7.12%**
- turnover: **1.0**

### SMA crossover reference

- net total return: approximately **4.17%**
- turnover: **2.0**

### High-turnover reference

- zero-cost net total return: approximately **+1.00%**
- 50 bps cost-adjusted net total return: approximately **-16.93%**
- turnover per period: **1.0**
- deterministic screen: **REJECTED** by explicit turnover policy

### Look-ahead negative control

- intentionally sets one signal's information cutoff after its effective time;
- evaluator result: **rejected with `LookaheadDetected`**.

These values validate plumbing and guards only. They are not evidence that any strategy has predictive edge.

## 6. Organizational interpretation

### Research

Can now submit bounded candidate position series for deterministic measurement.

### Quant / Market

Owns data timing, cost, metric and benchmark correctness.

### Counter-Research

Can challenge the method after deterministic facts exist instead of debating raw ideas.

### Portfolio Management

Still must evaluate total-portfolio relevance separately.

### Risk & Compliance

Still owns risk acceptance and may reject a research survivor.

### Investment Committee / Decision Management

Receive no authority from a `SURVIVES_DETERMINISTIC_SCREEN` label.

### Execution

Has no path into this module.

## 7. What was intentionally NOT implemented

- LLM candidate generation;
- arbitrary Python generation or `eval()`;
- strategy DSL;
- RL;
- FinBERT;
- multi-agent debate graph;
- broker integration;
- StrategyPassport auto-promotion;
- any change to real-account files or order path;
- any change to Holdings Runtime.

## 8. Open issues discovered while taking over

A separate existing branch still contains the deeper institutional kernel work.

Open PR #108 (`TASK-071: bind Research evidence to runtime-verified sources`) targets `architecture/p0-5-gap-audit`, not `main`.

Its review contains an unresolved correctness issue: the promoted market Evidence should preserve the market observation timestamp in `evidence.observed_at` instead of recording only the later review time.

That issue is outside this Phase 1 capability PR and was not silently modified here. It should be reconciled before that institutional branch is treated as current merged implementation.

## 9. Next proposed step

Do **not** jump to RL or a large multi-agent graph.

The next bounded step is QT-STRAT-002:

```text
safe declarative candidate representation
→ parser / allowlist
→ duplicate + complexity bounds
→ StaticCandidateProvider
→ only then bounded LLMCandidateProvider experiment
```

The deterministic evaluator built here remains the mandatory downstream gate.
