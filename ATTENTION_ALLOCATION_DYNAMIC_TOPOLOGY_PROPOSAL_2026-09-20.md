# QuanTrade Architecture Proposal — Attention Allocation & Dynamic Intelligence Topology

Date: 2026-09-20
Status: Founder decision proposal / architecture hypothesis
Base: architecture/p0-5-gap-audit

## 0. Why this proposal exists

QuanTrade is an investment institution. Its scarce resource is not only money; it is also attention, model calls, data retrieval, analyst time, and Founder attention.

A system that deeply analyzes every headline, price move, filing, portfolio fluctuation, and anomaly is not autonomous intelligence. It is an expensive event processor.

The missing question before Research is:

> What is worth thinking about now because resolving it could materially change the Client's capital allocation, risk, or future opportunity set?

This proposal therefore adds an Attention Allocation capability before Intelligence and challenges the assumption that a fixed multi-department topology should process every problem.

This is a proposal, not an accepted doctrine. It must be validated against simpler alternatives.

## 1. Revised economic loop

CLIENT CAPITAL / MANDATE
→ Portfolio & Liability State
→ Observation / Delta Detection
→ ATTENTION ALLOCATION
→ only material questions receive cognitive budget
→ INTELLIGENCE / RESEARCH
→ CAPITAL ALLOCATION
→ EXECUTION
→ PERFORMANCE / ATTRIBUTION
→ LEARNING
→ updated Attention Policy
→ loop

Research is not the protagonist. Client capital is.

## 2. Attention is capital

QuanTrade should explicitly treat cognitive resources as a budget:

- deterministic compute;
- data/API retrieval;
- LLM calls/tokens;
- deep-research time;
- parallel-agent count;
- human/Founder interruption.

The objective is not to maximize research volume.

A useful long-run objective is closer to:

portfolio-relevant information gained
-------------------------------------
cognitive cost + latency + Founder attention

No fixed scalar formula is accepted yet. The purpose is to make the tradeoff measurable.

## 3. Sources of candidate questions

Candidate questions may originate from:

- portfolio structure and exposure changes;
- risk-limit proximity or correlation changes;
- performance/attribution anomalies;
- Client cashflow, liabilities, goals, or mandate changes;
- thesis-monitor variables;
- company filings and corporate actions;
- market prices/volatility/liquidity;
- macro/rates/FX/commodities;
- news and geopolitical events;
- alternative data;
- model/tool disagreement;
- failed prior predictions;
- internal learning and recurring process errors;
- unexpected relationships discovered by deterministic monitoring.

NEWS and PRICE_MOVE are only two possible event sources.

A small internal anomaly may deserve more attention than a major headline.

## 4. Decision-Relevance Gate

Before expensive research, ask:

> If this uncertainty were resolved, is there a plausible path by which the Client's allocation, risk posture, liquidity plan, monitoring policy, or opportunity set would change?

Candidate dimensions:

- Portfolio Relevance
- Potential Capital/Risk Impact
- Novelty versus already-known information
- Uncertainty
- Actionability
- Time sensitivity
- Research cost
- Existing evidence quality

Conceptual priority only:

Priority ~ Relevance × Impact × Novelty × Uncertainty × Actionability / Research Cost

This is not production math. It is a hypothesis to test.

Possible outcomes:

IGNORE
LOG_ONLY
MONITOR
CHEAP_VERIFY
DEEP_RESEARCH_CANDIDATE
IMMEDIATE_RISK_REVIEW

Zero deep-research cases on a day can be a successful outcome.

## 5. 24/7 does not mean 24/7 LLM reasoning

Continuous operation should be layered.

### Layer 0 — deterministic monitoring

Low-cost software continuously computes/detects:

- prices, returns, volatility;
- portfolio weights/exposures;
- risk thresholds;
- correlations and concentration;
- cash/liability changes;
- filings/events metadata;
- scheduled macro events;
- thesis watch variables;
- evidence freshness;
- data-quality breaks;
- unusual deltas.

### Layer 1 — cheap triage

Small rules/models classify whether a delta is:

- expected/noise;
- already explained;
- relevant but non-urgent;
- potentially decision-relevant.

### Layer 2 — question formation

Only selected deltas become explicit investment questions.

### Layer 3 — research-budget allocation

Allocate bounded cognitive budget based on expected decision value.

### Layer 4 — expensive intelligence

Use an architecture appropriate to the problem: one agent, ensemble, specialists, or full institutional process.

## 6. Dynamic intelligence topology

Human firms keep persistent departments partly because humans are persistent employees.

AI workers do not require the same topology.

QuanTrade should test whether the persistent layer should be the Institutional Kernel while the reasoning topology is composed on demand.

Candidate router:

Problem / Question
→ classify uncertainty, consequence, complexity, independence needs, authority risk
→ choose the smallest adequate topology

Possible topologies:

A. DETERMINISTIC_ONLY
- calculations, constraints, reconciliation, known rules.

B. SINGLE_AGENT
- bounded evidence retrieval/synthesis with low consequence.

C. INDEPENDENT_ENSEMBLE
- independent judgments useful for ambiguity/calibration.

D. SPECIALIST_TEAM
- e.g. Research + Quant + Critic where specialization/context isolation has measured value.

E. FULL_INSTITUTIONAL_PROCESS
- material capital/risk decisions requiring provenance, independent challenge, authority separation, durable decision record.

Employees/roles may be instantiated for the task and dissolve afterward.

Persistent institutional state remains:

- Client Mandate;
- Portfolio/Capital state;
- Evidence;
- deterministic financial engines;
- authority rules;
- Decisions;
- Ledger;
- evaluations;
- institutional learning/memory.

## 7. The architecture itself is now a hypothesis

QuanTrade must compete against simpler systems.

Primary competing hypothesis:

> A simpler single agent or independent LLM ensemble can equal or outperform QuanTrade's institutional architecture at lower cost for many investment tasks.

If true, remove unnecessary structure.

If partly true, route those task families to the simpler topology.

If false for a task family, identify the exact failure mode that institutional structure fixes.

The research question is not:

> At what complexity does QuanTrade finally win?

It is:

> For which failure modes does each architecture improve reliability, decision quality, cost, and governance?

## 8. Experimental consequences

Do not benchmark only final-answer correctness.

Measure:

- substantive task success;
- unsupported claims;
- provenance;
- numerical correctness;
- uncertainty/calibration;
- recovery from tool/data failure;
- contradiction handling;
- risky/forbidden action attempts;
- reproducibility;
- model calls;
- input/output tokens where available;
- data/API cost;
- elapsed time;
- Founder interruptions;
- downstream portfolio-decision usefulness.

Candidate controlled treatments:

1. Single Agent
2. Independent Ensemble
3. Role-based Specialist Team
4. QuanTrade Institutional Process

Budget fairness matters. A four-agent system cannot claim superiority merely by spending four times the inference budget.

## 9. Research discovery benchmark

Bounded E1 tasks test whether an employee can execute a known evidence task.

A later benchmark should test whether the institution can discover what deserves research.

Seed examples should be intentionally incomplete:

- a portfolio correlation regime shift;
- a filing inconsistency;
- a macro anomaly;
- a supply-chain bottleneck signal;
- a thesis-monitor break;
- a performance attribution surprise.

Success is not reproducing a preselected narrative.

Success is discovering important variables, counter-evidence, falsification conditions, and portfolio implications while ignoring irrelevant information.

## 10. Claim decomposition — capability hypothesis, not database commitment

For material theses, QuanTrade should test whether decomposing narratives into claims improves reliability.

Example:

Hormuz disruption
→ effective oil supply decreases
→ crude price pressure increases
→ inflation path changes
→ rate path may change
→ portfolio exposures affected

Each edge can carry:

- evidence;
- counter-evidence;
- confidence/calibration;
- magnitude;
- lag;
- source/provenance;
- last verified;
- falsification condition.

Do not build a graph database merely because this representation is attractive. First prove that structured claim decomposition improves research/monitoring outcomes over simpler notes.

## 11. What this proposal explicitly rejects

- analyze every market event;
- make every Event a Case;
- make every Case a deep-research project;
- run many agents because multi-agent looks sophisticated;
- keep 15 offices active on every problem;
- equate research volume with investment intelligence;
- let LLMs own deterministic financial calculations;
- optimize UI/organizational realism before economic proof;
- make the Founder the routine work generator.

## 12. Promotion gates

Attention Allocation becomes accepted architecture only if experiments show that it:

1. reduces unnecessary deep research/cognitive spend;
2. preserves or improves detection of material portfolio-relevant questions;
3. does not systematically miss high-impact weak signals;
4. improves information gained per unit of cognitive budget;
5. produces traceable reasons for escalation/non-escalation.

Dynamic topology becomes accepted only if routing among architectures beats or matches a fixed topology on reliability/cost/governance.

## 13. Immediate implications

Do not implement a broad 24/7 news-analysis pipeline.

Do not create more permanent departments.

Continue E1 to establish agent/runtime competence.

Then design the next evaluation layers around:

- architecture-vs-architecture comparisons;
- attention/research-discovery tasks;
- point-in-time real data;
- portfolio/risk translation;
- learning from prior decisions.

The next major production investment should still be justified by evidence from these experiments.

## 14. Founder decisions requested

This proposal asks the Founder to decide later, after reviewing experimental evidence, whether to adopt:

- Attention Allocation as a first-class North-Star engine;
- cognitive budget as an institutional resource;
- dynamic on-demand reasoning topology instead of fixed department routing;
- architecture competition/simplification as a permanent development law.

No implementation authority follows automatically from this document.

## Classification

Finding:
QuanTrade currently has a Research/organization-centric architecture without an explicit mechanism for deciding what deserves expensive thought.

Assumption:
Selective attention and dynamic reasoning topology can preserve decision quality while reducing cognitive cost and institutional overhead.

Experiment:
Compare attention policies and reasoning topologies under matched data/model/tool/budget conditions.

Open Question:
What measurable policy best balances false negatives (missed material signals) against research cost and noise?

Decision Proposal:
Reframe the North Star as Client Capital → Attention Allocation → Intelligence → Capital Allocation → Learning, subject to empirical validation.
