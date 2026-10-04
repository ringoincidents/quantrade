# QuanTrade Strategic System Audit — 2026-09-19

Status: Strategic audit / development reset proposal  
Scope: current repository + accepted QuanTrade operating doctrine  
Audit baseline: architecture/p0-5-gap-audit @ 80b22df9dd61a9867cd71f52f04bf21a57475dea

---

# 0. Executive conclusion

QuanTrade has made real architectural progress, but development has become imbalanced.

The repository is increasingly good at representing **how an investment institution should communicate, record, route, and govern work**, while remaining weak at the harder economic question:

> Can this institution repeatedly produce, test, allocate, monitor, and learn from investment decisions using real, point-in-time data under the Client's actual constraints?

The largest current risk is therefore not missing another department, agent, screen, or workflow.

The largest risk is **Institutional Theater**:
a sophisticated virtual-firm operating system whose investment intelligence, capital allocation science, learning loop, and live operating substrate are not yet strong enough to justify the organizational complexity around them.

This is not a recommendation to discard P1.0–P1.4. The control plane and employee-runtime work are useful foundations. The correction is to stop expanding the shell and redirect development toward the economic and scientific core.

North Star for the next development era:

> QuanTrade is an autonomous personal capital institution for one Client. It continuously models Client capital needs, observes markets, discovers research work, tests hypotheses, constructs portfolios under deterministic constraints, records decisions and outcomes, learns from errors, and escalates only material choices to the Founder. It is judged by economic, scientific, operational, and governance outcomes — not by the number of agents or institutional objects.

---

# 1. What QuanTrade actually is

QuanTrade should not be optimized as:
- a stock recommender,
- an AI chatbot,
- a dashboard,
- a collection of automated scripts,
- a simulation of a securities-company org chart,
- or a multi-agent demonstration.

Its actual economic loop is:

```
CLIENT STATE
  assets / liabilities / income / spending / goals / horizon / constraints
        ↓
CAPITAL POLICY
  liquidity / reserve / risk budget / investable capital / mandate
        ↓
OPPORTUNITY DISCOVERY
  markets / companies / events / anomalies / strategy gaps
        ↓
RESEARCH & EXPERIMENT
  evidence / hypotheses / counter-theses / backtests / failure cases
        ↓
PORTFOLIO CONSTRUCTION
  opportunity cost / sizing / diversification / liquidity / exposure
        ↓
INDEPENDENT RISK & GOVERNANCE
  policy / stress / dissent / committee / exceptions
        ↓
DECISION & EXECUTION
  timing / approval / implementation / transaction cost
        ↓
OUTCOME & ATTRIBUTION
  what happened / why / compared with what / at what risk
        ↓
LEARNING
  thesis quality / model quality / process error / repeated bias
        ↓
CLIENT & CAPITAL UPDATE
        ↺
```

Organization exists to make this loop safer and better. The organization is not the product by itself.

---

# 2. What has been built well

## 2.1 Control-plane foundation

P1.0–P1.2 established several sound primitives:
- Event and Case separation;
- Evidence with provenance;
- PortfolioSnapshot and deterministic RiskAssessment;
- InstitutionalPosition and Challenge;
- immutable-style Decision records;
- DecisionPlan separated from decision;
- simulated execution only;
- review schedules;
- append-only-style ledger with hash-chain verification;
- Founder attention routing.

This is materially better than the legacy JSON/pending-actions architecture.

## 2.2 Employee-runtime direction

P1.3 correctly corrected a major architectural mistake: employees should receive **capabilities**, not one bespoke command per prompt.

Useful primitives now exist:
- Employee;
- WorkOrder;
- Task;
- WorkRequest;
- Message;
- Workspace;
- Artifact;
- ToolRegistry;
- provider-neutral EmployeeAgent;
- model-call and tool-call audit;
- Strategy and Chart workstation examples;
- Secretary delegation.

This is the correct conceptual direction for reusable AI-native organizational infrastructure.

## 2.3 Legacy experimental discipline is stronger than it looks

The old Alpha Lab contains some of the most valuable intellectual assets in the repository:
- predeclared success criteria;
- train/validation separation;
- transaction costs/slippage;
- benchmark comparisons;
- explicit rejection of failed signals;
- multiple-comparison thinking;
- look-ahead contamination awareness;
- survivorship-bias awareness;
- point-in-time concerns;
- preservation of failed experiments rather than silent deletion.

This culture should be promoted into the new institutional architecture rather than treated as merely old code.

## 2.4 P1.4 corrected the Founder-as-scheduler problem conceptually

Client Profile, Goal, Cashflow, Capital Plan, Investment Mandate, Performance record, and autonomous WorkOrder generation are the correct categories.

The important idea is sound:

> Routine institutional work should arise from Client state, portfolio state, market state, risk state, and learning state — not from the Founder continuously inventing prompts.

However, implementation is not yet strong enough to claim that this loop actually operates autonomously.

---

# 3. Critical audit findings

## F-01 — Autonomous WorkOrders are currently capable of becoming inert

Severity: CRITICAL  
Axis: Autonomy / Organization

P1.4 AutonomousWorkEngine creates WorkOrders addressed to offices such as SPMG, IPRO, CCO, and ISLL without assigning a recipient_employee_id.

But OrganizationRuntime.employee_inbox() retrieves WorkOrders only where recipient_employee_id equals that employee.

There is no durable office inbox dispatcher / manager / scheduler that claims office-level work and assigns it to an employee.

Therefore:

```
Mandate gap
  → WorkOrder(recipient_office="SPMG")
  → persisted successfully
  → no employee necessarily sees or executes it
```

The software can record "autonomous work issued" while no autonomous work actually occurs.

Required correction:
- OfficeQueue / Dispatcher / claim semantics;
- employee availability and capability matching;
- assignment audit;
- retry / timeout / dead-letter behavior;
- no claim that autonomous operation exists until this is end-to-end tested.

## F-02 — Cross-office WorkRequest is transport, not orchestration

Severity: HIGH  
Axis: Autonomy / Organization

An employee can create a WorkRequest, but a request addressed only to an office has the same routing problem.

There is no general mechanism that:
- claims the request;
- creates/links child work;
- runs the receiving employee;
- returns artifacts/results;
- wakes the requester;
- handles rejection/timeout;
- preserves dependency semantics.

The current system can model communication, but not yet reliably operate a collaborating firm.

## F-03 — EmployeeAgent can close work while dependencies remain open

Severity: HIGH  
Axis: Autonomy / Governance

On FINISH, EmployeeAgent marks both its Task and WorkOrder COMPLETED.

It does not check:
- outstanding WorkRequests;
- child WorkOrders;
- required artifacts;
- unresolved errors;
- linked Case readiness;
- mandatory evidence.

This allows a model to declare completion while delegated analysis is still unfinished.

Required correction:
WorkOrder completion must be runtime-gated, not model-declared.

## F-04 — P1.3F Artifact Gates were never implemented

Severity: HIGH  
Axis: Governance

The repository itself already identified that the original linear Case chain was a scaffold.

Yet service.py still requires:

```
OPEN
→ RESEARCH
→ PORTFOLIO_REVIEW
→ RISK_REVIEW
→ ADVERSARIAL_REVIEW
→ COMMITTEE
```

This conflicts with the intended firm, where Research, Portfolio, Risk, and ARU may operate in parallel and revise artifacts.

The deferred P1.3F gate is now architectural debt.

However, it should be implemented as a minimal correctness gate, not used as an excuse for another long governance-development cycle.

## F-05 — "Performance → Capital" is currently more nominal than causal

Severity: HIGH  
Axis: Capital / Learning

PerformanceCapitalLoop.record_performance() records performance facts.

During reconcile(), performance_id is checked for existence, but the performance record does not materially drive the capital calculation. Reconciliation is primarily driven by externally supplied:
- client_liquid_cash;
- brokerage_cash;
- invested_market_value.

This is not wrong as an accounting boundary, but the current naming can imply a tighter closed loop than exists.

Missing:
- broker/account cash reconciliation;
- realized proceeds linkage;
- dividends/interest linkage;
- fees/taxes reconciliation;
- external deposit/withdrawal classification;
- attribution linkage to strategies/decisions;
- reconciliation breaks.

A real capital loop needs accounting identity, not only a WorkOrder trigger.

## F-06 — Client Capital math is prototype-grade and currently unsafe as authoritative planning logic

Severity: CRITICAL before real capital use  
Axis: Capital

The P1.4A planner is a useful domain prototype, not yet a financial-planning engine.

Concrete problems:

1. A 12-month horizon can count 13 monthly occurrences because the current inclusive month-index calculation uses end_index - start_index + 1.

2. recurring_monthly_income / recurring_monthly_expense sums active MONTHLY records without respecting whether the cashflow has started yet or already ended relative to the planning date.

3. Goal required-return math assumes a constant monthly contribution over the entire goal horizon even when the underlying income/cashflow may terminate earlier.

4. Taxes, inflation, irregular income, liabilities, account restrictions, currency, and confidence/uncertainty are not modeled except when manually represented.

5. "max_planning_return_pct" is a useful safety ceiling but is not a substitute for a proper risk-capacity model.

Conclusion:
P1.4A must remain explicitly PROVISIONAL until a time-indexed cashflow engine and planning invariants exist.

## F-07 — The new architecture has almost no real Data Plane

Severity: CRITICAL  
Axis: Intelligence / Infrastructure

StrategyDataPlane uses synthetic fixture rows.

Chart Workstation uses synthetic/local bars.

Evidence adapters connect existing structured outputs, but there is no canonical production-grade data plane for:
- point-in-time fundamentals;
- KRX universe history;
- corporate actions;
- investor flow history;
- sector/industry history;
- minute bars;
- valuation history;
- filing/document retrieval;
- source/version/as-of snapshots.

The employee architecture therefore has computers but almost no reliable electricity/data feeding those computers.

This is now a larger bottleneck than agent architecture.

## F-08 — Data provenance stops too early

Severity: HIGH  
Axis: Intelligence / Reproducibility

Evidence has provenance, which is good.

But generic tool outputs do not yet carry a mandatory reproducibility envelope such as:
- provider;
- dataset;
- query;
- as_of;
- retrieval timestamp;
- source version;
- adjustment policy;
- timezone;
- currency;
- transformation/code version;
- missing-data policy.

A chart, screen, or backtest result must be reconstructable later. A JSON output stored in a model Workspace is not enough.

## F-09 — Tool contracts are under-specified

Severity: MEDIUM/HIGH  
Axis: Infrastructure / Agent safety

ToolRegistry validates only required field presence.

It does not currently provide robust:
- type validation;
- enum/range validation;
- output schema;
- data provenance schema;
- cost estimate;
- timeout policy;
- retry semantics;
- idempotency classification;
- data sensitivity classification;
- versioning.

For real LLM employees, typed tools need to become institutional APIs, not merely Python callables with descriptions.

## F-10 — Employee intelligence has not been validated

Severity: CRITICAL to the AI-native thesis  
Axis: Intelligence / Autonomy

ScriptedModelProvider proves infrastructure.

AnthropicEmployeeProvider proves a model can technically be called.

Neither proves that an LLM employee can reliably:
- interpret unseen objectives;
- choose correct tools;
- detect missing data;
- avoid unsupported claims;
- recover from errors;
- delegate well;
- stop at the right time;
- preserve context;
- produce reproducible artifacts.

No unseen-task employee evaluation harness currently exists.

Therefore "LLM employees can run the firm" remains an untested hypothesis.

## F-11 — Context/memory design will not scale as implemented

Severity: MEDIUM/HIGH  
Axis: Agent runtime

EmployeeAgent sends:
- Workspace;
- messages;
- recent tool outputs;
- employee metadata;
- WorkOrder;
- Task;
- tool catalog

directly into model context.

Workspace also accumulates tool_outputs.

Without summarization, artifact references, retrieval, context budgeting, and sensitivity controls, long-running work will eventually become:
- expensive;
- slow;
- context-window constrained;
- difficult to reproduce;
- potentially overexposed to an external model provider.

Persistent memory needs tiers:
working state, artifacts, institutional facts, episodic history, and retrieval — not one growing JSON blob.

## F-12 — There is no real autonomous operating substrate

Severity: CRITICAL  
Axis: Infrastructure / Autonomy

There is no durable production runtime providing:
- scheduler;
- worker queue;
- event bus;
- process supervision;
- retry;
- leases/claims;
- crash recovery;
- health checks;
- secrets management;
- backup/restore;
- monitoring;
- cost accounting.

SQLite is appropriate for the prototype kernel, but GitHub Actions + local SQLite cannot be mistaken for a continuously operating firm.

Do not build a 24/7 scheduler until F-01/F-02 work routing semantics are corrected, otherwise the scheduler will repeatedly generate inert work.

## F-13 — Database evolution has no migration mechanism

Severity: HIGH before deployment  
Axis: Infrastructure

db.py executes CREATE TABLE IF NOT EXISTS against one monolithic schema.

There is no schema version / migration history.

This becomes dangerous as soon as persistent Client/Decision/Strategy history matters.

Institutional memory cannot depend on destructive/manual schema changes.

## F-14 — Ledger is tamper-evident, not immutable

Severity: MEDIUM  
Axis: Governance

The hash chain can detect ordinary mutation, which is useful.

But the SQLite tables themselves are writable, and an actor with DB write access could rewrite rows and recompute the chain.

This is acceptable for the prototype but should be described accurately:
"tamper-evident application ledger", not strong immutable storage.

## F-15 — Production event triage is not implemented

Severity: HIGH  
Axis: Governance / Intelligence

FixtureEventTriagePolicy recognizes synthetic event types.

Unknown event types default to INTERNAL_LOG.

PortfolioRuleEventAdapter emits PORTFOLIO_RULE_MATCH, which the fixture policy does not promote by default.

This is safe in the sense of avoiding false escalation, but it means current Event → Case behavior is still a demonstration policy, not production institutional judgment.

## F-16 — Portfolio construction is the largest missing financial engine

Severity: CRITICAL  
Axis: Capital

The repository has useful deterministic portfolio reporting/risk calculations, but not a canonical Portfolio Construction Engine.

Missing institutional questions include:
- What role does each holding/strategy play?
- What is the opportunity cost of capital?
- How should strategy sleeves be budgeted?
- How do correlated exposures combine?
- How should risk be allocated across ideas?
- What changes when Client liabilities change?
- What rebalance is justified after costs/taxes?
- What is the benchmark and policy portfolio?
- What does "do nothing" look like as an explicit alternative?

Without this layer, Research can discover ideas but QuanTrade cannot rigorously translate them into portfolio decisions.

## F-17 — Risk remains partly provisional and incomplete

Severity: HIGH  
Axis: Capital / Governance

The legacy deterministic risk code is useful, but several policies remain provisional.

The existing "MDD budget" is explicitly an unrealized-return proxy rather than actual peak-to-trough MDD.

Missing or incomplete areas include:
- actual portfolio return series;
- historical drawdown;
- factor/sector/currency exposures;
- scenario/stress testing;
- liquidity;
- tail risk;
- strategy-level risk budgets;
- portfolio risk contribution;
- policy exception authority.

Risk must become a first-class deterministic engine before capital authority expands.

## F-18 — Learning is mostly recording, not learning

Severity: CRITICAL  
Axis: Learning

QuanTrade records many things, but institutional learning requires structured comparison:

```
ex-ante thesis
vs
ex-ante uncertainty
vs
decision
vs
actual outcome
vs
benchmark/counterfactual
vs
attribution
vs
process/model/data error
```

Current Performance records do not yet create:
- thesis scorecards;
- analyst/model calibration;
- recurring-error taxonomy;
- strategy degradation detection;
- experiment lineage;
- strategy promotion/retirement;
- model/tool evaluation updates.

The system has memory, but not yet a learning engine.

## F-19 — The best scientific work is stranded in legacy Alpha Lab

Severity: HIGH  
Axis: Learning / Intelligence

The old repository contains valuable research discipline, but the new institutional runtime does not expose it as an ISLL workstation/service.

There is no canonical:
- Experiment;
- Hypothesis;
- DatasetSnapshot;
- BacktestRun;
- EvaluationProtocol;
- StrategyCandidate;
- StrategyVersion;
- PromotionGate;
- RetirementDecision.

The new company can send ISLL a WorkOrder, but ISLL does not yet have the institutional machinery to do the job.

## F-20 — 81 passing tests overstate system maturity if interpreted economically

Severity: HIGH  
Axis: Validation

The 81 tests are valuable regression tests for infrastructure.

They do not establish:
- investment edge;
- real-data correctness;
- LLM employee quality;
- long-running autonomy;
- crash recovery;
- financial-planning correctness;
- portfolio construction quality;
- live accounting reconciliation;
- production security.

Future status reports must separate:
1. software-contract tests;
2. financial-math validation;
3. data validation;
4. agent evaluation;
5. economic experiments;
6. operational soak tests.

"81 tests passed" is not evidence that QuanTrade is a good investment institution.

## F-21 — architecture branch has diverged from main

Severity: MEDIUM now / HIGH later  
Axis: Engineering

Current compare shows architecture/p0-5-gap-audit ahead of main while also behind main.

This is manageable during prototyping, but prolonged divergence will make integration and CI semantics ambiguous.

Before a persistent runtime is deployed, branch strategy and canonical source-of-truth must be cleaned up.

---

# 4. Six-axis maturity audit

These percentages are not completion claims. They are directional maturity estimates used to expose imbalance.

| Axis | Current maturity | Finding |
|---|---:|---|
| Organization / Control Plane | ~60% prototype maturity | strongest new layer; useful but overrepresented |
| Intelligence / Real Data | ~15% | synthetic workstations; real data architecture is missing |
| Capital Allocation | ~20% | Client/mandate skeleton exists; portfolio construction is missing |
| Learning / Investment Science | ~20% | strong legacy discipline, weak new-runtime integration |
| Autonomy | ~20% | reasoning loop exists; routing/execution/evaluation do not |
| Production Infrastructure | ~15% | no durable scheduler/queue/migrations/monitoring/deployment |

The imbalance matters more than the absolute numbers.

Current architecture resembles:

```
        ORGANIZATION  ████████████
        GOVERNANCE    ██████████
        AGENT SHELL   ████████
        DATA          ███
        ALLOCATION    ████
        LEARNING      ████
        OPERATIONS    ███
```

The next era must flatten this imbalance.

---

# 5. What should be frozen

Until the economic core catches up, freeze:
- creation of additional departments merely for organizational completeness;
- additional LLM employee roles without a measured need;
- broad UI polishing;
- live broker execution;
- automatic policy changes;
- "autonomy" features that only create more WorkOrders;
- new bespoke investment signals without a preregistered experiment;
- Founder OS extraction into a generalized platform.

The system already has enough organizational vocabulary to run the next experiments.

---

# 6. What should be preserved

Preserve and strengthen:
- Event / Evidence / Case / Ledger;
- WorkOrder / Task / Request / Workspace;
- deterministic ToolRegistry concept;
- model-provider abstraction;
- explicit authority boundaries;
- no live broker side effects;
- immutable/superseding records;
- failed-experiment preservation;
- predeclared research gates;
- transaction cost and benchmark discipline;
- point-in-time / survivorship / leakage skepticism;
- Founder attention protection;
- Client-first capital doctrine.

---

# 7. Development Era II — Proof of Investment Institution

The next roadmap should no longer be numbered as a stream of small requested features.

It should be organized around proof obligations.

## Epoch A — Runtime Truthfulness

Goal:
Make the current institutional claims true.

Deliverables:
- office-level queue and dispatcher;
- WorkRequest → child work → response lifecycle;
- dependency-aware WorkOrder completion;
- minimal parallel artifact readiness gate;
- schema migrations;
- restart/recovery tests;
- correct P1.4 time-indexed cashflow math;
- explicit PROVISIONAL flags on unvalidated capital/risk policy;
- canonical branch strategy.

Exit proof:
A system-generated SPMG WorkOrder is actually claimed by a Strategy employee, delegates work, waits for dependencies, produces artifacts, and reaches a valid terminal state after process restart.

## Epoch B — Canonical Data Plane

Goal:
Give employees real, reproducible institutional data.

Required contracts:
- Security Master;
- Market Data;
- Corporate Actions;
- Fundamentals;
- Filings;
- Investor Flow;
- Sector/Industry;
- FX/Macro;
- Client Accounts / Cash;
- Portfolio history.

Every dataset/tool result must carry:
provider, as_of, retrieved_at, version/snapshot, adjustment policy, currency/timezone, missing-data metadata, transformation version.

Priority is not "many providers".
Priority is one reliable vertical slice with point-in-time semantics.

Exit proof:
A research result can be reproduced later from recorded data/query/code versions without trusting model prose.

## Epoch C — Investment Science / Strategy Lifecycle

Goal:
Turn the legacy experimental culture into a first-class ISLL system.

Canonical objects:
Hypothesis → ExperimentProtocol → DatasetSnapshot → BacktestRun → Result → Challenge → Replication → StrategyCandidate → StrategyVersion → Promotion/Reject/Retire.

Required validation:
- preregistration;
- train/OOS/walk-forward where appropriate;
- look-ahead checks;
- survivorship checks;
- point-in-time fundamentals;
- transaction cost/slippage;
- benchmark/counterfactual;
- multiple-testing/data-snooping controls;
- failed-case retention;
- reproducibility.

Exit proof:
An LLM employee can propose a novel bounded hypothesis, ISLL can test it reproducibly, and the system can reject it without Founder intervention when the gate fails.

## Epoch D — Portfolio & Risk Science

Goal:
Translate research into Client-level capital decisions.

Build:
- policy portfolio / benchmark;
- strategy sleeves;
- exposure model;
- deterministic position/risk budgeting;
- portfolio risk contribution;
- correlation/factor/sector/currency constraints;
- actual drawdown history;
- stress/scenario engine;
- rebalance optimizer with cost/tax/liquidity constraints;
- explicit do-nothing alternative;
- PolicyException path.

Exit proof:
Given the same Client Mandate + portfolio + candidate set, deterministic engines reproduce the same feasible allocation/risk outputs and explain every constraint.

## Epoch E — Employee Intelligence Evaluation

Goal:
Prove LLM employees add value over simpler software.

Build unseen-task suites for:
- Strategy;
- Research;
- Chart;
- Risk;
- Secretary;
- later offices only when needed.

Measure:
- task success;
- unsupported claim rate;
- numerical error;
- evidence coverage;
- unnecessary tool calls;
- delegation quality;
- recovery from missing data;
- reproducibility;
- latency;
- model/API cost.

Compare:
- LLM employee;
- deterministic baseline;
- simpler single-agent baseline where relevant.

Exit proof:
A role exists only if it measurably improves the institution.

## Epoch F — Shadow Firm

Goal:
Run QuanTrade continuously without giving it live trading authority.

Duration:
long enough to observe repeated market/client cycles; do not define success from a few days.

Operate:
- real Client/account read-only data;
- real market/fundamental data;
- scheduled/event-driven work;
- autonomous research;
- portfolio proposals;
- risk review;
- simulated/paper execution;
- attribution;
- learning.

Founder receives only escalated matters.

Measure four scorecards:

Economic:
benchmark-relative after-cost paper outcomes, drawdown, turnover, missed opportunity, cash drag.

Scientific:
hypothesis rejection rate, replication rate, OOS degradation, unsupported claims, calibration.

Operational:
Founder interruptions, work latency, queue backlog, failed jobs, recovery, cost per completed work item.

Governance:
unauthorized actions, policy breaches, missing provenance, audit-chain failures, unresolved exceptions.

Exit proof:
QuanTrade can operate as a coherent shadow institution, not merely run isolated tests.

## Epoch G — Controlled Capital Authority

This epoch is NOT automatically reached.

It requires an explicit Founder governance decision after Shadow Firm evidence.

Possible later progression:
simulation → paper → tiny bounded capital → broader authority.

Live execution remains out of scope until the institution demonstrates reliability.

---

# 8. New development law

From this audit forward, every proposed feature must answer:

1. Which North-Star capability is missing?
2. What failure mode does this solve?
3. Why is LLM reasoning better than deterministic software here?
4. What deterministic component should own repeated/calculable work?
5. What evidence will prove the feature works?
6. What would cause us to reject/remove it?
7. Does it improve economic/scientific/operational outcomes, or only make the firm look more complete?

If those questions cannot be answered, do not build it.

---

# 9. AI Holdings implication

QuanTrade should remain the first proving ground.

Do not prematurely generalize Founder OS from unproven abstractions.

Reusable group infrastructure should be extracted only after QuanTrade proves that primitives such as:
- WorkOrder;
- Evidence;
- Decision;
- Authority;
- Ledger;
- Evaluation;
- Workspace;
- Tool;
- Memory

survive contact with real operations.

AI Holdings should treat a future company as an economic engine, not an idea with an org chart.

Suggested progression:

```
Idea
→ Lab
→ measurable capability
→ repeated value production
→ operating unit
→ company
```

QuanTrade's deeper role is to test whether one Founder can safely multiply attention, knowledge, and capital through AI/software while preserving human control over consequential authority.

---

# 10. Immediate recommendation

STOP the previously planned P1.4C "scheduler first" implementation.

A scheduler attached to incorrect routing semantics would automate the creation of inert work.

Immediate engineering order:

```
Strategic Audit accepted
        ↓
Epoch A — Runtime Truthfulness
        ↓
Epoch B — Canonical Data Plane
        ↓
Epoch C/D — Investment Science + Portfolio/Risk
        ↓
Epoch E — Employee Intelligence Evaluation
        ↓
Epoch F — Shadow Firm
```

The next code PR should be selected from Epoch A, not from another user example.

Highest-priority first vertical proof:

> SYSTEM detects a Strategy Coverage Gap → office queue receives WorkOrder → dispatcher assigns a capable Strategy employee → employee inspects real/fixture capability catalog → creates child request to another office → child work is completed → parent resumes → required artifacts are produced → completion gate validates dependencies → full trace survives restart.

Only after that vertical proof should continuous scheduling be attached.

---

# 11. Audit classification

Finding:
QuanTrade is currently overdeveloped in institutional shell relative to investment intelligence, capital allocation, learning, and production autonomy.

Decision proposal:
Declare P1.0–P1.4 the end of "Institutional Foundation Era" and begin "Development Era II — Proof of Investment Institution."

Assumption:
The primary strategic advantage of AI employees will come from flexible research/work discovery and compression, while repeated calculations, constraints, portfolio/risk math, and experimental evaluation remain deterministic.

Experiment:
Use Epoch E unseen-task evaluations and Epoch F Shadow Firm operation to test whether LLM employees actually improve outcomes.

Open Question:
The exact Risk authority model — absolute IPRO veto vs documented Founder PolicyException — remains unresolved and should be decided before controlled capital authority.

Project Update:
No further department proliferation, UI expansion, or live execution should proceed until Runtime Truthfulness and real-data/research foundations catch up.
