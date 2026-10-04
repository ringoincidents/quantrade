# QuanTrade Canonical Vision

Status: **CURRENT / CANONICAL**  
Effective date: **2026-10-04**  
Supersedes as current direction: ad-hoc chat summaries and any older direction note that conflicts with this document  
Historical source retained: 2026-09-17 founding vision supplied by Founder

---

## 0. Why this document exists

QuanTrade has repeatedly experienced direction drift:

1. a strong product vision is discussed;
2. implementation work accelerates;
3. local technical problems and experiments accumulate;
4. the latest implementation details become more visible than the original company purpose;
5. a later conversation rediscovers the original intent and recenters the project.

The problem is not only product design. It is also a record-governance problem.

A durable organization must distinguish:

- current canonical direction;
- historical sources;
- later extensions;
- superseded ideas;
- experiments;
- rejected ideas;
- implementation status.

No single chat, model invocation, README paragraph, experiment artifact or recent commit may silently redefine the company.

This document is the human-readable canonical projection of the current QuanTrade vision.

---

## 1. North Star

**QuanTrade is an AI-native Private Investment Office for one Client.**

Its purpose is not to predict stocks, generate trading signals, or maximize the number of AI agents.

Its purpose is to implement, in software, the professional process by which an investment organization:

1. understands the Client;
2. defines the investment mandate and capital constraints;
3. observes and researches markets;
4. designs the portfolio;
5. independently controls risk;
6. reaches governed investment decisions;
7. decides whether and when to execute;
8. executes within authority;
9. measures outcomes;
10. learns from the difference between expectations and reality.

Canonical one-sentence definition:

> **QuanTrade는 AI에게 투자를 맡기는 시스템이 아니라, 한 명의 Client를 위한 전문 투자조직의 사고·검증·위험관리·의사결정·실행·학습 과정을 소프트웨어로 구현하는 AI-native Private Investment Office다.**

---

## 2. What remains unchanged from the 2026-09-17 founding vision

The following principles remain current.

### 2.1 Organization before recommendation

QuanTrade is not an “AI stock picker.”

A recommendation is valid only as the downstream result of an organizational process.

### 2.2 Separation of duties

The intended domain chain remains:

```text
Client Intelligence
        ↓
Strategy / Investment Mandate
        ↓
Research
        ↓
Portfolio Management
        ↓
Risk & Compliance
        ↓
Investment Committee
        ↓
Decision Management
        ↓
Execution
        ↓
Performance & Learning
        └──────────────→ Research / Portfolio / Risk
```

Each function has a distinct question and authority boundary.

### 2.3 Evidence is first-class

Important claims should retain source, date, provenance, applicability, limitations and citation.

AI explanations are not evidence by themselves.

### 2.4 Research does not decide portfolio action

Research describes what is happening and what evidence supports or contradicts a thesis.

It does not decide how much of the Client's capital should be allocated.

### 2.5 Portfolio attractiveness and position size are separate questions

A security may be attractive but still inappropriate to add because of concentration, liquidity, correlation, mandate or capital-use constraints.

### 2.6 Risk is independent and may veto

Risk & Compliance does not exist to justify Portfolio Management.

It may reduce, block or veto an otherwise attractive proposal.

### 2.7 Portfolio decision and execution timing are separate

```text
WHAT should the portfolio do?
        ≠
WHEN should the action be executed?
```

A Committee decision may remain valid while Decision Management chooses NOW, DEFERRED, CONDITIONAL, REASSESS or CANCELLED.

### 2.8 Decisions are append-only history

A later decision never silently overwrites an earlier decision.

The organization must be able to reconstruct:

- what was believed;
- what evidence was available;
- what decision was made;
- why;
- what happened later;
- what was learned.

### 2.9 Deterministic calculations before LLM reasoning

Calculations, constraints, market measurements, policy checks and other deterministic work should be performed by code when practical.

LLMs interpret, synthesize and reason about uncertainty; they should not be used as expensive calculators.

### 2.10 Validation before automation

The promotion path remains conservative:

```text
Backtest
→ Historical validation
→ Paper / Shadow
→ Micro-live
→ Limited automation
→ Higher automation
```

No validation stage automatically authorizes the next one.

---

## 3. Important evolution since the founding vision

The original vision remains the foundation, but several ideas have matured.

### 3.1 Strategy now sits explicitly between Client Intelligence and market action

Client Intelligence supplies facts, goals, obligations and constraints.

A Strategy / Capital Mandate layer converts those facts into organizational posture.

Examples:

- LIQUIDITY_FIRST
- CLIENT_REVIEW_REQUIRED
- DEFENSIVE_REVIEW
- REBALANCE_REVIEW
- DEPLOYMENT_REVIEW
- MAINTAIN

Urgent cash needs do **not** imply higher risk.

They normally reduce investable capital or increase liquidity priority.

### 3.2 Market State Compiler

QuanTrade should prefer a deterministic AI-oriented market calculator over repeated visual chart interpretation.

Example output:

- multi-horizon returns;
- moving averages / EMA structure;
- RSI;
- ATR;
- MACD state;
- volume anomalies;
- support/resistance distances;
- candle body/wick structure;
- volatility;
- trend regime.

The structured state is an input to Research, not a recommendation.

### 3.3 Conditional AI invocation

AI should not be called on every market tick or every scheduled run.

A deterministic gate may invoke AI when there is enough uncertainty or impact, for example:

- material market shock;
- regime change;
- portfolio-policy breach;
- allocation gap;
- material new evidence;
- Client mandate conflict;
- unresolved departmental disagreement.

### 3.4 Client Intelligence became a real office

Private Client facts live in the private Holdings Runtime and are versioned append-only.

Client Intelligence:

- detects information gaps;
- asks only questions needed by downstream decisions;
- stores structured answers;
- joins internal meetings on a need-to-know basis;
- does not recommend securities or authorize execution.

### 3.5 Holdings provides shared infrastructure, not QuanTrade's domain model

QuanTrade may use Holdings for:

- Memory;
- Authority;
- Audit;
- Model Gateway;
- Cost Control;
- Mission execution infrastructure;
- Evidence transport;
- Approval;
- Deployment;
- Organizational learning.

But QuanTrade's native operating language remains domain-specific:

```text
Client Mandate
Research Case
Evidence
Investment Thesis
Portfolio Proposal
Risk Opinion
Committee Decision
Decision Plan
Order / Execution
Performance Review
```

Generic `Mission / Work / Artifact` objects are implementation substrate, not the product vocabulary the Founder should have to operate manually.

### 3.6 Market experiments are laboratories, not the identity of QuanTrade

BTCUSDT / Binance paper experiments validate infrastructure, process and decision economics.

They do **not** redefine QuanTrade as a crypto trading bot.

Canonical rule:

> A market experiment is one laboratory inside QuanTrade, not QuanTrade itself.

---

## 4. Organizational roles

### Client Intelligence

Question:

> Who is the Client and what must the portfolio serve?

Owns:

- assets;
- liabilities;
- income/cashflow;
- obligations;
- liquidity needs;
- goals;
- risk preference;
- risk capacity;
- capital uses;
- constraints.

Does not own market forecasts or portfolio decisions.

### Strategy / Investment Mandate

Question:

> Given the Client's situation, what should the organization optimize for now?

Owns:

- capital posture;
- investable surplus;
- liquidity priority;
- planning conflicts;
- mandate interpretation;
- research priorities;
- constraints supplied downstream.

Does not select securities or execute orders.

### Research

Question:

> What is happening and what does the evidence say?

Possible specialist capabilities:

- Macro;
- Fundamental;
- ETF;
- Quant;
- Technical / Market Structure;
- Academic;
- Event;
- Tax / Implementation.

Specialists are invoked when useful. They are not mandatory participants in every case.

Output:

- observations;
- evidence;
- competing interpretations;
- uncertainty;
- limitations.

### Portfolio Management

Question:

> What should this Client's portfolio hold, in what size, and why?

Owns:

- allocation;
- position sizing;
- rebalancing proposals;
- cash allocation;
- diversification;
- concentration;
- factor exposure;
- holding horizon.

### Risk & Compliance

Question:

> Is the proposed portfolio/action acceptable under Client capacity, policy and risk limits?

Owns independent checks for:

- concentration;
- drawdown;
- volatility;
- liquidity;
- leverage;
- currency/country exposure;
- policy violations;
- portfolio-wide risk.

May veto.

### Investment Committee

Question:

> Given Research, Portfolio and Risk, what is the governed investment decision?

The Committee preserves:

- thesis;
- evidence;
- counterargument;
- alternatives;
- risk;
- rationale;
- responsible roles;
- expected outcome.

### Decision Management

Question:

> Is the decision still valid, and should it be executed now?

Owns:

- NOW;
- DEFERRED;
- CONDITIONAL;
- REASSESS;
- CANCELLED;
- EXECUTED.

Timing decisions require evidence and cannot be justified by vague intuition.

### Execution

Question:

> How is the authorized action carried out safely and accurately?

Execution does not invent investment policy.

### Performance & Learning

Question:

> What actually happened, why, and what should the organization learn?

Evaluation distinguishes:

- market outcome;
- thesis quality;
- risk objective;
- portfolio objective;
- timing;
- execution quality;
- data quality;
- model quality.

A decision is not automatically wrong merely because the asset later rose or fell.

---

## 5. Product experience

QuanTrade should feel like a private investment firm, not an engineering dashboard.

A Founder/Client-facing surface should prioritize:

1. current portfolio and liquidity;
2. mandate / posture;
3. material market or portfolio changes;
4. departmental reviews in progress;
5. Committee decisions;
6. execution state;
7. decisions requiring Client/Founder approval;
8. performance and learning.

Internal model calls, generic Runtime objects, raw JSON, stack traces and low-level execution IDs remain available for audit but are not the primary experience.

---

## 6. Anti-drift rules

### Rule 1 — No recent implementation may redefine the North Star

A new experiment, UI, model provider or workflow is subordinate to this vision unless an explicit superseding decision is approved.

### Rule 2 — Every material direction change is classified

A new statement that changes direction must be recorded as one of:

- EXTENDS
- NARROWS
- SUPERSEDES
- EXPERIMENT
- REJECTS
- REFERENCE_ONLY

“Latest chat wins” is forbidden.

### Rule 3 — Canonical direction and implementation state are separate

A principle may be current but not yet implemented.

An implementation may exist but later be superseded.

Never infer one from the other.

### Rule 4 — Domain semantics outrank generic infrastructure semantics

Holdings Runtime may implement shared mechanics, but QuanTrade product decisions should be expressed in investment-domain objects and roles.

### Rule 5 — Experiments remain scoped

Validation is bound to explicit market, strategy, data and execution assumptions.

Knowledge may transfer. Validation does not.

### Rule 6 — One-shot models do not write canonical truth directly

A model may draft records and propose claim relationships.

Canonical promotion, supersession and high-authority direction changes must pass Runtime governance and provenance checks.

### Rule 7 — Future work reads canonical context before proposing change

Before material QuanTrade development:

1. read this canonical vision;
2. retrieve current related decisions/Claims;
3. inspect current implementation;
4. identify whether the proposal extends, conflicts with or duplicates existing direction;
5. only then implement.

---

## 7. Current non-goals

QuanTrade is not currently:

- a public brokerage;
- a third-party asset manager;
- a fully autonomous live trading bot;
- a crypto-only system;
- a stock recommendation chatbot;
- an agent-count demonstration;
- a vehicle for maximizing model usage.

Live capital movement remains tightly governed.

---

## 8. Current priority

The immediate priority is not to add more agents.

It is to make the full company loop coherent and observable:

```text
Client
→ Strategy / Mandate
→ Research
→ Portfolio
→ Risk
→ Committee
→ Decision Management
→ Execution
→ Performance & Learning
→ organizational learning
```

The next major QuanTrade milestone should demonstrate this loop on a bounded real or paper case without bypassing missing Client information, evidence, independent risk review or execution authority.

---

## 9. Record-governance requirement

This document is a projection, not the sole memory mechanism.

Future organizational memory should preserve:

- the original 2026-09-17 source;
- this current canonical projection;
- later changes as new Claims/Decisions;
- explicit supersession/extension relations;
- implementation bindings;
- verification evidence.

The goal is not to prevent the vision from evolving.

The goal is to make it impossible for the organization to forget **how and why** it evolved.
