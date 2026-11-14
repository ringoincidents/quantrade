# Strategy Research Sandbox — Implementable Plan

Status: **PHASE 1–4 COMPLETED IN SANDBOX / NOT PROMOTED**  
Date: **2026-10-05**  
Parent research: `2026-10-05_LLM_TRADING_FRAMEWORKS_REVIEW.md`  
Target repository: **QuanTrade**  
Shared Holdings Runtime changes: **none required for Phase 1–3**

## Implementation progress

- **QT-STRAT-001 / Phase 1: IMPLEMENTED IN SANDBOX**
- Code: `quantrade/capabilities/strategy_research.py`
- Reference harness: `quantrade/capabilities/strategy_research_evaluation.py`
- Tests: `tests/capabilities/test_strategy_research.py`
- Result record: `research/precedents/2026-10-05_STRATEGY_RESEARCH_SANDBOX_PHASE1_RESULT.md`
- No production, portfolio, risk, investment-decision or execution authority granted.
- **QT-STRAT-002 / Phase 2: IMPLEMENTED IN SANDBOX**
- Safe DSL/provider: `quantrade/capabilities/strategy_candidates.py`
- End-to-end harness: `quantrade/capabilities/strategy_candidate_evaluation.py`
- Tests: `tests/capabilities/test_strategy_candidates.py`
- Result record: `research/precedents/2026-10-05_STRATEGY_RESEARCH_SANDBOX_PHASE2_RESULT.md`
- **QT-STRAT-003 / Phase 3: IMPLEMENTED IN SANDBOX**
- Robustness gate/review planner: `quantrade/capabilities/strategy_robustness.py`
- Reference harness: `quantrade/capabilities/strategy_robustness_evaluation.py`
- Tests: `tests/capabilities/test_strategy_robustness.py`
- Result record: `research/precedents/2026-10-05_STRATEGY_RESEARCH_SANDBOX_PHASE3_RESULT.md`
- **QT-STRAT-004 / Phase 4: GOLDEN RUN COMPLETED**
- Pre-registration: `research/experiments/QT-STRAT-004_PRE_REGISTRATION.md`
- Frozen dataset: `research/experiments/QT-STRAT-004_DATASET.json`
- Machine result: `research/experiments/QT-STRAT-004_RESULT.json`
- Result report: `research/experiments/QT-STRAT-004_RESULT_REPORT.md`
- Outcome: operational success, **0/4 candidates Stage-A eligible**, TEST remained closed for all candidates, no specialist/model invocation.
- Pipeline verdict: keep as research infrastructure; no strategy/PAPER/execution promotion.
- Phase 5 (RL/FinBERT) remains deferred.

## Post-Phase-4 transfer experiment

- **QT-STRAT-005: MULTI-STOCK KRX TRANSFER GOLDEN RUN COMPLETED**
- Frozen new instruments: `000660, 207940, 005380, 005490, 006400`
- Same four QT-STRAT-004 candidate families, no parameter retuning
- Pre-registration: `research/experiments/QT-STRAT-005_PRE_REGISTRATION.md`
- Dataset: `research/experiments/QT-STRAT-005_DATASET.json`
- Machine result: `research/experiments/QT-STRAT-005_RESULT.json`
- Result report: `research/experiments/QT-STRAT-005_RESULT_REPORT.md`
- Outcome: operational success, **0/4 candidates Stage-A eligible**, candidate TEST metrics remained closed, no specialist/model invocation
- Evidence: QT-STRAT-004 + QT-STRAT-005 do not support the four simple technical families as default alpha candidates under the current protocol
- Next research principle: broaden the information family rather than parameter-search nearby variants.

## 1. Goal

Build the smallest safe capability that lets QuanTrade:

1. represent a strategy/factor hypothesis;
2. reject invalid or unsafe generated candidates;
3. evaluate candidates deterministically;
4. compare candidates under point-in-time, benchmark and cost constraints;
5. conditionally invoke Counter-Research / LLM synthesis;
6. promote nothing beyond research without existing QuanTrade governance.

This is **not** an autonomous trading system.

---

## 2. Proposed architecture

```text
StrategyCandidateProvider
        ↓
CandidateStrategy
        ↓
Safe Strategy DSL / parser
        ↓
Deterministic StrategyEvaluator
        ↓
StrategyEvaluationArtifact
        ↓
Robustness / leakage / cost gates
        ↓
top-K only
        ↓
conditional Counter-Research / LLM synthesis
        ↓
Research Recommendation Artifact
        ↓
existing Portfolio → Risk → Committee path
        ↓
StrategyPassport only after separate approval
```

### Authority boundaries

Every output must carry:

```text
canonical_evidence_created = false unless independently promoted
portfolio_proposal_created = false
risk_limit_changed = false
investment_decision_created = false
execution_authorized = false
```

A Research Sandbox result is not a trade.

---

## 3. Phase 1 — Deterministic Evaluation Core

Priority: **first**

### Proposed files

```text
quantrade/capabilities/strategy_research.py
tests/capabilities/test_strategy_research.py
research/precedents/<dated evaluation mission>.md
```

### Core schemas

#### CandidateStrategy

Suggested fields:

```text
candidate_id
name
description
source_type
source_ref
universe
market_scope
rebalance_horizon
required_fields
formula_ast
parameter_set
created_at
generator_provider
```

#### StrategyEvaluation

Suggested fields:

```text
candidate_id
dataset_id
as_of_range
train_range
validation_range
test_range
benchmark
transaction_cost_model
metrics
robustness
leakage_checks
provider/version
status
authority
```

### Minimum deterministic metrics

- cumulative return;
- annualized return;
- volatility;
- Sharpe;
- Sortino;
- maximum drawdown;
- Calmar;
- turnover;
- estimated transaction cost;
- max single-period loss;
- benchmark excess return;
- coverage / missing-data rate.

For factor-style research where applicable:

- IC / Rank IC;
- quantile spread;
- factor turnover;
- factor decay.

### Required tests

1. same inputs → same result;
2. future data cannot enter an earlier as-of evaluation;
3. transaction costs reduce net performance;
4. invalid dates fail closed;
5. missing benchmark is explicit;
6. missing data cannot silently become zero;
7. output carries provider/version provenance;
8. no evaluation output can authorize execution.

### Why first

This phase creates the trustworthy measurement layer needed by every later LLM/agent experiment.

No model call is required.

---

## 4. Phase 2 — Safe Candidate Generation

Priority: **second**

### Rule: no arbitrary generated Python

Do **not** reproduce the external project's `eval(formula)` pattern.

Instead define a small strategy DSL/AST allowlist.

Initial allowed primitives can reuse measurements already familiar to QuanTrade:

```text
CLOSE
RETURN(n)
SMA(n)
EMA(n)
STD(n)
RSI(n)
ATR(n)
VOLUME_MA(n)
REF(x, n)
ADD / SUB / MUL / DIV
GT / LT
AND / OR
RANK
ZSCORE
```

Anything outside the grammar is rejected before evaluation.

### Provider seam

Add a replaceable interface conceptually equivalent to:

```text
StrategyCandidateProvider.generate(context) -> CandidateStrategy[]
```

Initial providers:

1. `StaticCandidateProvider` — deterministic fixtures for tests;
2. later `LLMCandidateProvider` — bounded model generation.

The LLM provider outputs only structured candidate descriptions/AST.

It receives no execution permission.

### Required tests

- unknown operator rejected;
- recursion/depth bounded;
- parameter ranges bounded;
- division-by-zero handled deterministically;
- candidate count bounded;
- duplicate candidates detected;
- generated candidate provenance preserved.

---

## 5. Phase 3 — Robustness Gate and Conditional Multi-Agent Review

Priority: **third**

This is where TradingAgents patterns are useful, but not as a fixed graph.

### Deterministic gate first

Reject or downgrade candidates for:

- look-ahead leakage;
- insufficient sample;
- single-regime dependence;
- excessive turnover;
- excessive cost sensitivity;
- unacceptable drawdown;
- unstable parameter sensitivity;
- benchmark underperformance;
- near-duplicate exposure;
- missing required data.

### Top-K only

Only a small number of surviving candidates should reach expensive review.

Default principle:

```text
many candidates
→ cheap deterministic screening
→ small survivor set
→ bounded reasoning
```

### Specialist review

Use existing MSIP logic.

Possible specialist Work:

- Quant/Market — statistical robustness;
- Counter-Research — falsification;
- Portfolio — effect on current portfolio;
- Risk — drawdown, concentration, tail behavior;
- Deep External Research — only if the strategy depends on unfamiliar market structure or theory.

### Parallel execution rule

If multiple specialists are justified, they may run in parallel with:

- scoped context;
- private role input;
- explicit output contract;
- fixed tool/model budget;
- join only after required Artifacts arrive.

This adapts the good part of TradingAgents without importing its fixed organizational graph.

### Stop rule

Do not add another specialist if its strongly positive/negative result cannot plausibly change:

- keep/reject decision;
- size;
- timing;
- confidence;
- risk limit;
- validation stage.

---

## 6. Phase 4 — Strategy Passport Binding

Priority: **after Phase 1–3 evidence**

A successful candidate does not become “active strategy” directly.

The result should feed the existing QuanTrade market-validation model.

Suggested path:

```text
Research candidate
→ deterministic evaluation
→ counter-research
→ Portfolio relevance
→ Risk opinion
→ governed decision
→ StrategyPassport
→ MarketTransferGate
→ PAPER / SHADOW
```

Promotion stages remain:

```text
BACKTEST
→ HISTORICAL VALIDATION
→ PAPER / SHADOW
→ MICRO-LIVE
→ LIMITED AUTOMATION
→ HIGHER AUTOMATION
```

No stage automatically authorizes the next.

---

## 7. Phase 5 — Optional ALPHA/HARLF RL experiment

Priority: **defer**

Do not start here.

Only consider after:

- deterministic baseline exists;
- strategy evaluation is point-in-time safe;
- transaction-cost model exists;
- PAPER baseline is reproducible;
- enough data exists for train/validation/test separation;
- simpler methods have measurable limits.

### Experiment scope

If run later, keep RL behind a replaceable experimental provider.

Input vector may include:

- returns;
- volatility;
- Sharpe/Sortino/Calmar;
- drawdown;
- correlation/covariance features;
- bounded sentiment features;
- current portfolio state;
- regime indicators.

Output remains a **portfolio proposal**, never direct execution.

Compare against simple baselines:

- equal weight;
- buy-and-hold benchmark;
- minimum variance;
- risk parity;
- deterministic strategy-selection baseline.

Must include transaction costs, turnover and walk-forward evaluation.

---

## 8. Concrete first development slice

The recommended first coding slice is intentionally small:

### Build

- `CandidateStrategy`
- `StrategyEvaluation`
- safe AST representation
- deterministic evaluator
- synthetic fixture dataset
- point-in-time split helper
- cost-adjusted metrics
- provenance + authority flags
- tests

### Do not build yet

- RL;
- FinBERT pipeline;
- large multi-agent debate graph;
- live broker integration;
- automatic strategy promotion;
- production model calls.

### Expected value

This first slice gives QuanTrade a reusable research substrate for:

- factor research;
- technical strategies;
- news/event hypotheses;
- portfolio allocation methods;
- future LLM-generated strategies;
- future OSS backtest/provider adapters.

It creates measurable infrastructure before adding expensive intelligence.

---

## 9. Acceptance gate for first slice

Phase 1 is complete only when:

1. at least three synthetic/reference candidate strategies can be evaluated;
2. same data/candidate yields identical metrics;
3. one deliberate look-ahead fixture is caught;
4. one high-turnover strategy becomes worse after costs;
5. one candidate is rejected for robustness/failure criteria;
6. all results identify source/provider/version and dataset window;
7. zero code path creates an order or execution authorization;
8. tests pass in CI;
9. a dated precedent records result, failures and next decision.

---

## 10. Proposed evaluation fixtures

Start with deliberately simple strategies, not “smart” ones:

1. **BUY_AND_HOLD**
2. **SMA_CROSSOVER**
3. **MEAN_REVERSION_ZSCORE**
4. **INTENTIONALLY_LEAKY_FUTURE_RETURN** — must be rejected
5. **HIGH_TURNOVER_NOISE** — should degrade materially after cost

These are validation instruments, not investment recommendations.

---

## 11. Repository ownership

### QuanTrade owns

- candidate semantics;
- strategy evaluation;
- research artifacts;
- MarketScope;
- Portfolio/Risk/Committee interpretation;
- StrategyPassport promotion.

### Holdings Runtime owns only shared mechanics if later needed

- Mission/Work execution;
- model routing;
- cost telemetry;
- scoped context;
- approvals;
- audit.

Therefore the first implementation should **not** expand the Holdings Runtime.

This avoids turning a QuanTrade research need into unnecessary shared-OS scope.

---

## 12. Proposed task sequence if Founder authorizes implementation

### QT-STRAT-001 — Strategy Evaluation Core

Deliver:

- schemas;
- safe candidate representation;
- deterministic metrics;
- PIT split/checks;
- cost model;
- tests.

### QT-STRAT-002 — Candidate Provider + Safe DSL

Deliver:

- provider interface;
- static provider;
- parser/allowlist;
- duplicate/complexity bounds;
- tests.

### QT-STRAT-003 — Robustness Gate + MSIP Review Binding

Deliver:

- deterministic screening;
- top-K survivor selection;
- conditional specialist Work contract;
- explicit skipped/invoked telemetry;
- no execution authority.

### QT-STRAT-004 — Paper Golden Run

Deliver:

- one bounded MarketScope;
- benchmark comparison;
- cost/latency report;
- failure log;
- recommendation: ADOPT / ADAPT / WATCH / REJECT for the capability itself.

Only after these should an RL/FinBERT experimental branch be considered.
