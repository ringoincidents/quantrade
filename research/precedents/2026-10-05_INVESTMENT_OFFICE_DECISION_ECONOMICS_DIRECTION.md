# QuanTrade Direction Proposal — Investment Office Decision Economics

Status: **FOUNDER-DIRECTED PROPOSAL / IMPLEMENTATION AUTHORIZED / NOT A CANONICAL SUPERSESSION**  
Date: **2026-10-05**  
Classification: **EXTENDS canonical vision + NARROWS current implementation priority**

## 0. Decision context

QuanTrade's canonical North Star is already an **AI-native Private Investment
Office for one Client**.

This proposal does not replace that vision.

It narrows the next implementation priority after repeated evidence that simple
price-signal research has not demonstrated robust, transferable alpha.

Relevant current evidence includes:

- historical MA/ADX/RSI strategy validation failure;
- technical-indicator significance program with no surviving edge;
- historical/news-direction experiments that failed their baseline/gates;
- QT-STRAT-004, where four fixed technical candidates produced zero
  Stage-A survivors on a frozen 005930 scope;
- QT-STRAT-005, where the same four candidates again produced zero Stage-A
  survivors across five new KRX stocks without parameter retuning.

QT-STRAT-004/005 currently live in Draft PR #118 and remain experiment-scoped
evidence until separately merged/governed.

The correct response is **not** to manufacture more nearby SMA/RSI/momentum
parameters until something passes.

## 1. Proposed direction

QuanTrade should shift its primary product-development question from:

> "What signal says this asset will go up?"

to:

> "Given the Client, current price, available evidence, valuation assumptions,
> alternatives and risk, is allocating capital to this asset economically
> justified, in what size, and under what conditions?"

The operating object becomes an **Investment Case**, not a trading signal.

Target operating chain:

```text
Client Mandate
→ Research Case
→ Evidence
→ Investment Thesis
→ Scenario / Valuation Economics
→ Counter-Research
→ Portfolio Proposal
→ Risk Opinion
→ Investment Committee
→ Decision Plan
→ Execution
→ Performance & Learning
```

This directly implements the canonical organizational chain rather than
creating a parallel stock-picker architecture.

## 2. What an Investment Case must answer

A material new-security or position-change Case should be able to answer:

### State Delta

What actually changed since the previous Case?

### Thesis / Edge

What economic claim makes the asset attractive or unattractive?

A thesis is not:

- "RSI is low";
- "an analyst target price is high";
- "the LLM feels bullish".

A thesis should identify a causal claim that can be contradicted or falsified.

Examples:

- market expectations understate durable margin improvement;
- consensus revenue growth is too low because a measurable capacity constraint
  is easing;
- the market price embeds a downside assumption inconsistent with currently
  available balance-sheet evidence.

### Valuation / Scenario

What is the asset worth under explicit Bear / Base / Bull or other bounded
scenarios?

What assumptions generate each value?

What is the probability-weighted value under those assumptions?

### Consensus / External Observation

What does the market or sell-side currently appear to expect?

Examples:

- consensus EPS;
- consensus revenue / operating profit;
- sell-side target-price distribution;
- implied multiples;
- company guidance;
- market-implied expectations where measurable.

External targets are **Evidence/Observation inputs**, not authority.

### Counter-Research

What would make the thesis wrong?

Which assumptions are fragile?

Which evidence contradicts the thesis?

### Portfolio Effect

Even if attractive in isolation:

- does it duplicate an existing exposure?
- increase concentration?
- consume scarce liquidity?
- worsen factor/country/currency exposure?
- crowd out a better opportunity?

### Risk

Can the portfolio survive the Bear case?

Does the action conflict with Client capacity, mandate or policy?

### Decision

The output is not automatically BUY/SELL.

Valid governed outcomes include:

- ACT
- HOLD
- WATCH
- RESEARCH_MORE
- REJECT

## 3. Source of potential economic value

QuanTrade should not claim that software structure itself creates alpha.

Potential value can come from several distinct sources:

1. **Beta capture**
   - remain invested in productive assets instead of overtrading;
2. **Analytical edge**
   - better assumptions / valuation / scenario calibration;
3. **Information-processing edge**
   - collect and reconcile material evidence more consistently;
4. **Behavioral edge**
   - avoid panic, FOMO, narrative chasing and thesis drift;
5. **Time-horizon edge**
   - hold a valid thesis through short-term noise when the Client can afford it;
6. **Portfolio-construction edge**
   - allocate capital by opportunity cost rather than isolated attractiveness;
7. **Risk-management edge**
   - prevent one wrong thesis from becoming a portfolio failure;
8. **Execution discipline**
   - avoid unnecessary turnover, friction and poor timing.

Every future performance claim should separate these sources where practical.

## 4. QuanTrade Value Added

The primary economic evaluation remains:

```text
QuanTrade Value Added
= QuanTrade portfolio outcome
- appropriate simple benchmark outcome
- trading friction
- taxes
- incremental research/model/data cost
```

This must be evaluated over time.

A good-looking Investment Case is not proof of value.

## 5. Target domain objects

The proposed product vocabulary is:

```text
ResearchCase
EvidenceClaim
InvestmentThesis
ScenarioSet
ValuationSnapshot
ConsensusObservation
CounterThesis
PortfolioProposal
RiskOpinion
CommitteeDecision
DecisionPlan
PerformanceReview
```

The current implementation starts only with the lowest-risk deterministic
piece:

```text
ScenarioSet
→ InvestmentCaseEconomics
```

No new execution path is authorized.

## 6. Deterministic-first rule

Valuation arithmetic must be deterministic.

LLMs may propose or explain assumptions, but code should calculate:

- probability-weighted fair value;
- expected return versus current price;
- Bear/Base/Bull returns;
- scenario dispersion;
- downside under the lowest-valued scenario;
- upside under the highest-valued scenario;
- expected return above/below a supplied hurdle;
- consensus-target gap when a consensus observation exists.

The calculator must preserve the distinction:

```text
assumption != evidence
calculation != thesis truth
economic attractiveness != portfolio suitability
portfolio proposal != investment decision
investment decision != execution
```

## 7. Target-price policy

Sell-side target prices may be stored only as bounded observations with:

- source;
- observed_at;
- target horizon where known;
- value;
- currency;
- methodology/limitations when known.

QuanTrade must never:

- average target prices and call that intrinsic value;
- treat an analyst rating as an Investment Committee decision;
- infer confidence from the number of analysts alone;
- use a target price without retaining its as-of date.

Consensus is most useful as a comparison point:

> "What does the market appear to expect, and why does our thesis differ?"

## 8. Scenario policy

Scenario probabilities and fair values are **explicit assumptions**.

The system must validate:

- probabilities are finite;
- probabilities sum to 1 within tolerance;
- scenario IDs are unique;
- fair values are positive;
- current price is positive;
- currency is explicit;
- valuation horizon is explicit;
- scenario assumptions retain provenance references when available.

The calculator must not pretend that valid arithmetic means valid assumptions.

## 9. Minimum Sufficient Investment Process mapping

This proposal implements LLMH-040 rather than adding a new universal checklist.

Mandatory spine:

```text
STATE_DELTA
→ DECISION_RELEVANCE
→ THESIS_EDGE
→ PORTFOLIO_EFFECT
→ RISK
→ DECISION
→ LEARNING
```

Conditional specialists remain conditional.

For example, Fundamental Research should not run merely because a stock exists.
It should run when a fundamental question can plausibly change valuation,
confidence, sizing or rejection.

## 10. Development plan

### Phase IO-1 — Investment Case Economics Core

Implement now:

- scenario schema;
- probability validation;
- deterministic expected-value calculator;
- hurdle comparison;
- scenario downside/upside/dispersion;
- optional consensus observation comparison;
- explicit authority boundary;
- tests and synthetic evaluation harness.

No external market/fundamental API required.

### Phase IO-2 — Thesis Contract

Next:

- structured Thesis Claim;
- supporting Evidence refs;
- contradicting Evidence refs;
- falsification conditions;
- assumptions vs observations separation;
- thesis versioning / supersession lineage;
- no model output promoted directly to Evidence.

### Phase IO-3 — Point-in-Time Fundamental Evidence

Only after source review:

- DART/company filings first where practical;
- disclosure/report timestamps preserved;
- no present-day-restated values silently used as historical PIT facts;
- consensus/sell-side observations remain source-scoped.

This phase must solve the point-in-time blocker documented in
`Phase3_펀더멘털신호_스펙.md`.

### Phase IO-4 — Portfolio Opportunity Cost

Compare an attractive Case with:

- current holdings;
- cash;
- benchmark/core allocation;
- other active Cases;
- concentration/correlation;
- Client liquidity requirements.

A security can be attractive and still receive zero allocation.

### Phase IO-5 — Learning / Calibration

Record before outcome:

- scenario probabilities;
- scenario fair values;
- thesis claims;
- expected catalysts;
- expected horizon;
- decision.

Then compare with reality:

- forecast/calibration error;
- thesis error versus bad luck;
- valuation error;
- sizing error;
- timing/execution error;
- benchmark-relative outcome;
- research/model/data cost.

## 11. What is explicitly deprioritized

Current default priority should **not** be:

- automatic generation of hundreds of technical rules;
- nearest-neighbor parameter searches around failed SMA/momentum/z-score
  candidates;
- RL portfolio control before deterministic baselines;
- FinBERT sentiment as an automatic action signal;
- fixed multi-agent debates on every Case;
- sell-side target-price averaging as a pseudo-valuation engine.

These remain possible future experiments only when a concrete capability gap and
Decision-Changing Test justify them.

## 12. First implementation authority

Founder direction authorizes implementation of **Phase IO-1 only** as a
non-authoritative deterministic capability.

Phase IO-1 may:

- validate scenario assumptions;
- perform arithmetic;
- emit an `InvestmentCaseEconomics` research artifact;
- compare internal scenario economics with a supplied hurdle/consensus
  observation.

Phase IO-1 may not:

- create canonical Evidence;
- create a Portfolio Proposal;
- set position size;
- change Risk policy;
- make an Investment Committee decision;
- create an executable DecisionPlan;
- authorize PAPER;
- authorize a live order.

## 13. Relationship to current decisions

This proposal:

- **EXTENDS** the QuanTrade Canonical Vision;
- **NARROWS** the current implementation priority away from signal discovery;
- is consistent with LLMH-033 decision economics;
- is consistent with LLMH-036 cheap-first deterministic market intelligence;
- implements LLMH-040 MSIP at the investment-domain level;
- does not modify the frozen LLM Holdings Runtime architecture.

## 14. Success criteria for the direction

This direction earns continued investment only if QuanTrade can eventually
show, on prospective or properly point-in-time paper cases, that the process
improves one or more of:

- benchmark-relative net return;
- drawdown;
- risk-adjusted return;
- avoidable-loss rate;
- unnecessary-turnover rate;
- thesis calibration;
- scenario calibration;
- capital-allocation quality;

after accounting for model/data/latency costs.

If it cannot, the correct conclusion may still be that the Client should use a
simpler benchmark/core portfolio and keep the Active Book small or empty.

That outcome is acceptable.
