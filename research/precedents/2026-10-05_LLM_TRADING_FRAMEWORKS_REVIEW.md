# 2026-10-05 LLM Trading Frameworks Review

Status: **RESEARCH RECORDED / NO ADOPTION DECISION**  
Direction classification: **REFERENCE_ONLY + PROPOSED EXPERIMENT**  
Authority: subordinate to `QUANTRADE_CANONICAL_VISION.md` and `research/TRADING_OSS_RESEARCH_PROGRAM.md`  
Execution mode: **single-model organizational simulation; not independent multi-agent review**

## 1. Why this record exists

Founder supplied three research examples relevant to QuanTrade:

1. **TradingAgents: Multi-Agents LLM Financial Trading Framework**
2. **Automate Strategy Finding with LLM in Quant Investment**
3. **ALPHA: Advanced Learning for Portfolio Handling Applications**  
   - the supplied screenshot matches this CompAI 2025 paper;
   - a later paper/revision by the same authors appears under the title **HARLF: Hierarchical Reinforcement Learning and Lightweight LLM-Driven Sentiment Integration for Financial Portfolio Optimization**;
   - this record treats the screenshot source as ALPHA and does not assume the two titles are identical artifacts.

The purpose is not to copy these systems. The purpose is to identify concrete engineering patterns that can strengthen QuanTrade while preserving its current canonical identity:

> one Client's AI-native Private Investment Office, with deterministic calculations before LLM reasoning, conditional specialist routing, independent risk, governed decisions, and validation before automation.

No finding in this record grants implementation, production, investment, or execution authority.

---

## 2. Sources and pinned research snapshots

### A. TradingAgents

Repository: https://github.com/TauricResearch/TradingAgents  
Inspected commit: `1394a3f72aa4393e1a98f51b382434c4b4c2d972`  
License: **Apache-2.0**

Relevant inspected files:

- `tradingagents/graph/setup.py`
- `tradingagents/graph/conditional_logic.py`
- `tradingagents/graph/trading_graph.py`
- `tradingagents/agents/managers/portfolio_manager.py`
- `tradingagents/agents/context.py`
- current README / test references for point-in-time, portfolio-aware, structured-agent behavior.

### B. Automate Strategy Finding with LLM in Quant Investment

Repository: https://github.com/kouzhizhuo/Automate-Strategy-Finding-with-LLM-in-Quant-investment  
Inspected commit: `ebcb5ed44a71664316c99b021026358a44aef38d`

Relevant inspected files:

- `main.py`
- `AutoGPT/main.py`
- `AutoGPT/data/prompt/1-preamble.md`

License note:

- no root `LICENSE` file was found at the inspected snapshot;
- therefore this repository is a **design/reference source only** until licensing is independently cleared;
- do not copy source code into QuanTrade on the basis of this review.

### C. ALPHA / HARLF lineage

Screenshot source matched:

- **ALPHA: Advanced Learning for Portfolio Handling Applications**
- Benjamin Coriat, Eric Benhamou
- public paper: https://filuta.ai/papers/CompAI_2025_paper_5.pdf

The paper states reproducibility through three Google Colab notebooks and describes:

- market-data observation vectors;
- FinBERT-derived sentiment;
- base RL agents;
- meta-agents;
- super-agent aggregation.

A later paper by the same authors uses the HARLF title and closely related architecture. That later title is useful as lineage/background, but the present evidence is anchored to the ALPHA paper shown in the supplied screenshot.

---

## 3. Reconciliation against current QuanTrade direction

The external work does **not** justify replacing QuanTrade's current architecture.

It mostly confirms and sharpens several principles already current:

- deterministic measurements before LLM interpretation;
- explicit portfolio context instead of assuming a flat book;
- specialist work with bounded scope;
- counter-research rather than one-sided recommendation;
- point-in-time backtesting discipline;
- explicit portfolio/risk stages;
- structured output and auditability;
- validation before capital action.

The main value is therefore **implementation precedent**, not architectural authority.

The correct question is:

> Which bounded patterns should QuanTrade absorb into its own domain interfaces?

Not:

> Which external framework should become QuanTrade?

---

## 4. Candidate-by-candidate assessment

## 4.1 TradingAgents

Provisional disposition: **LEARN_AND_BUILD + selective ADAPT**

### Useful patterns

#### Isolated specialist execution

`graph/setup.py` builds analyst subgraphs with private message history and returns only each analyst's report.

QuanTrade relevance:

- a Fundamental specialist should not silently inherit a Market Structure specialist's hidden reasoning;
- future independent Seats should receive scoped inputs and produce explicit Artifacts;
- this fits the existing MSIP independent Work contract.

#### Parallel specialist work with a join barrier

Selected analysts may run in parallel and synthesis starts only after their outputs are available.

QuanTrade relevance:

- when multiple specialists are actually justified by the Decision-Changing Test, they should not necessarily run serially;
- parallel execution can reduce latency without weakening separation of duties.

#### Bounded tool/reasoning rounds

TradingAgents limits analyst tool rounds and forces a wrap-up instead of allowing indefinite tool loops.

QuanTrade relevance:

- every specialist Work should have explicit tool/model budgets;
- “more research” must not become an unbounded loop.

#### Complete deterministic router paths

The graph contains explicit path maps for debate/risk routing.

QuanTrade relevance:

- deterministic routers should fail closed and expose every route explicitly;
- unknown labels/states must not crash or silently skip Risk/Review.

#### Missing-context semantics

`agents/context.py` explicitly distinguishes “report absent” from “empty finding”, and “portfolio context not provided” from “flat portfolio”.

QuanTrade relevance:

- absent Client/portfolio/evidence context must remain explicitly unknown;
- missing data must not be converted into neutral or zero values.

#### Point-in-time integrity

Current TradingAgents releases/test references emphasize dated runs, filed-as-of-date fundamentals, decision-log date fidelity, and backtests that only see data available at the analysis date.

QuanTrade relevance:

- this should be a hard validation requirement for any future Strategy Discovery pipeline.

### What should NOT be imported as-is

- fixed analyst → bull/bear debate → trader → aggressive/neutral/conservative → portfolio-manager graph;
- LangGraph as the owner of QuanTrade domain authority;
- debate count as a proxy for decision quality;
- a trader agent that collapses portfolio decision and execution authority;
- whole-framework dependency merely because the architecture resembles an investment firm.

QuanTrade already has a more explicit Client → Strategy → Research → Portfolio → Risk → Committee → Decision Management → Execution model.

TradingAgents should therefore be treated as a source of **execution patterns**, not organizational truth.

---

## 4.2 Automate Strategy Finding with LLM in Quant Investment

Provisional disposition: **LEARN_AND_BUILD / EXPERIMENT_ONLY**

### Useful patterns

#### Deterministic factor evaluation before LLM comparison

The repository uses a factor engine to calculate deterministic performance artifacts before asking an LLM to compare candidate alpha factors.

This ordering is valuable:

```text
candidate formula
→ deterministic calculation
→ measurable evaluation artifact
→ model-assisted comparison/reasoning
```

That is preferable to asking an LLM which strategy “looks best” without measured evidence.

#### Candidate tournament

The code compares candidate factors pairwise and preserves the current winner.

QuanTrade relevance:

- a bounded top-K comparison stage may be useful after deterministic screening;
- however pairwise LLM judgment should remain an Artifact/reasoning layer, not performance Evidence.

### Risks / reasons not to reuse directly

- no verified repository license in the inspected snapshot;
- direct `eval(formula)` style execution is unsuitable for generated strategy formulas;
- the repository uses an older OpenAI Assistants flow;
- the inspected code includes an API-key placeholder pattern that must not be replicated;
- pairwise LLM comparison can be order-sensitive and unstable;
- proprietary/external data dependencies reduce reproducibility;
- a single “best alpha” selection can overfit one historical regime.

### QuanTrade adaptation rule

If QuanTrade builds LLM-assisted strategy discovery:

- the LLM may propose a **safe declarative strategy candidate**;
- generated candidates must pass parser/allowlist validation;
- arbitrary Python/eval execution is forbidden;
- deterministic backtest/robustness metrics are Evidence candidates;
- the LLM may summarize trade-offs but cannot turn a weak backtest into a valid strategy by persuasion.

---

## 4.3 ALPHA / HARLF lineage

Provisional disposition: **EXPERIMENT_ONLY / WATCH**

### Useful patterns

The screenshot and paper describe a compact observation vector containing measurements such as:

- Sharpe ratio;
- Sortino ratio;
- Calmar ratio;
- maximum drawdown;
- volatility;
- cross-asset correlations;
- sentiment score vectors.

This strongly supports QuanTrade's current “AI-oriented calculator” direction.

The useful lesson is not “use RL because the paper used RL.”

The useful lesson is:

> numerical market/portfolio state should be compiled into a structured machine-readable representation before a reasoning model is asked to interpret it.

### Useful implementation ideas

- portfolio analytics as deterministic features;
- correlation/covariance state as structured input;
- sentiment as a bounded external feature rather than free-form prose;
- modular data and sentiment pipelines;
- separate training/test windows and fixed seeds for reproducibility.

### Risks / objections

- the ALPHA paper notes transaction costs were excluded from the illustrated monthly rebalancing experiment;
- hierarchical RL adds substantial model, data, tuning and validation complexity;
- reward design can hide unstable incentives;
- backfill/interpolation choices may create unrealistic historical information if not handled point-in-time;
- impressive historical returns are not sufficient adoption evidence;
- QuanTrade currently lacks a reason to place opaque RL policy authority above its explicit Portfolio/Risk/Committee process.

Therefore RL belongs behind the current Backtest → Paper/Shadow → Micro-live promotion discipline and should not be part of the first implementation wave.

---

## 5. Combined lesson for QuanTrade

The three sources point toward one practical synthesis:

```text
Market / Client / Portfolio state
        ↓
D0 deterministic compilers
        ↓
Candidate research ideas
        ↓
D0 strategy evaluation + point-in-time validation
        ↓
conditional specialist/counter-research
        ↓
Portfolio effect + independent Risk
        ↓
Committee / Decision Management
        ↓
Paper/Shadow only until promoted
```

The critical distinction is:

- **TradingAgents** contributes bounded multi-role execution patterns;
- **Strategy Finding** contributes candidate-generation → deterministic-evaluation ordering;
- **ALPHA/HARLF** contributes compact hybrid observation vectors and a possible long-term experimental RL track.

None of the three should become QuanTrade's application shell.

---

## 6. Proposed capability gap

Current QuanTrade already has:

- `FeatureProvider`;
- deterministic `ReviewGate`;
- provider comparison;
- OSS adoption governance;
- Market State Compiler direction;
- MSIP specialist routing.

The missing bounded capability is:

> **Strategy Research Sandbox** — a safe place to generate, represent, evaluate, compare and reject strategy candidates without granting portfolio or execution authority.

This is narrower than “automated trading.”

It is a research capability inside the Research laboratory.

---

## 7. Organizational trace

### originating_actor

QuanTrade Research / External Intelligence.

### mission_owner

QuanTrade Research capability owner.

### participating_actors

- Research — candidate/hypothesis ownership;
- Quant / Market — deterministic measurements and backtest design;
- Counter-Research — falsification and robustness objections;
- Portfolio Management — portfolio-level relevance;
- Risk & Compliance — downside, concentration, liquidity and tail-risk review;
- Performance & Learning — benchmark, cost, leakage, walk-forward and post-result evaluation;
- Runtime Engineering only if shared Holdings infrastructure later requires modification.

### execution_mode

Single-model organizational simulation for this research pass.

### independence_status

Not independent. Role labels in this record are future organizational mappings, not evidence of independent review.

### dissent preserved

- Research wants broad candidate exploration.
- Risk rejects promotion based on historical return alone.
- Engineering rejects arbitrary generated-code execution and whole-framework ownership inversion.
- Performance requires point-in-time data, cost/friction and benchmark comparison.
- Portfolio Management requires evaluation at total-portfolio level, not isolated asset/factor attractiveness.

### decision_authority

No adoption decision made in this record.

### execution_authority

None.

### future_runtime_mapping

The future independent process should map to durable:

- Mission;
- specialist Work;
- Candidate Artifact;
- Evaluation Artifact;
- Counter-Research Review;
- Proposal;
- Decision;
- StrategyPassport / MarketTransferGate;
- paper/shadow execution;
- Performance & Learning outcome.

---

## 8. Current research decision

**Do not adopt any of the three frameworks wholesale.**

Record them as precedents and proceed, if approved, with a QuanTrade-native Strategy Research Sandbox that:

1. reuses current deterministic/provider boundaries;
2. copies no unlicensed source;
3. keeps candidate generation separate from deterministic evaluation;
4. uses point-in-time and cost-aware validation;
5. uses LLM/multi-agent review only when it can change the decision;
6. grants zero execution authority;
7. leaves hierarchical RL as a later experiment, not the initial build.

See companion implementation plan:

`research/precedents/2026-10-05_STRATEGY_RESEARCH_SANDBOX_IMPLEMENTATION_PLAN.md`
