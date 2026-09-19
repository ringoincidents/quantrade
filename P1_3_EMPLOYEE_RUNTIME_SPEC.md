# QuanTrade P1.3 — Employee Runtime, Workstations & Organizational Communication

Date: 2026-09-19
Status: Architecture correction / implementation baseline
Owner: Founder/CEO

## Why this correction exists

P1.0–P1.2 built the institutional control plane correctly: Case, Evidence, PortfolioSnapshot, RiskAssessment, immutable Decision, Ledger, read-only portfolio adapters, and provenance-preserving Evidence.

That is necessary but insufficient.

QuanTrade is not intended to become a larger collection of fixed commands such as:
- read this JSON,
- calculate this fixed indicator,
- emit this fixed report.

The target is a virtual investment firm in which LLM employees can interpret broad goals, discover sub-work, request data/tools/colleagues, revise plans, and produce institutional artifacts — while repeated/mechanical work is delegated to deterministic software.

Core doctrine:

> Flexible reasoning, deterministic machinery, strict institutional memory.

## Founder operating assumption

The Founder does not have the time or specialist knowledge to micromanage every department.

Therefore:
- the Secretary must translate broad Founder intent into routable work;
- employees must plan their own analytical steps;
- departments need workstations, not hard-coded command handlers;
- employees must be able to ask other departments for work;
- routine research may be initiated without Founder involvement within explicit authority/budget;
- capital deployment, policy changes, irreversible actions, and authority exceptions remain controlled.

## What an LLM employee is

An employee is NOT:
- a prompt attached to one script,
- a chatbot with department branding,
- an autonomous trader,
- a fixed workflow node.

An employee IS a runtime identity with:
- role charter
- authority boundary
- inbox
- active tasks
- persistent workspace
- working memory
- available workstation tools
- data permissions
- compute budget
- communication capability
- artifact/report contract
- institutional history references

The underlying model provider must be replaceable.

## Employee runtime entities

### Employee
- employee_id
- office_id
- role
- charter
- authority
- model_profile
- workstation_profile
- status

### WorkOrder
Broad objective from Founder, Secretary, office manager, or authorized employee.

Fields:
- work_order_id
- issuer
- recipient office/employee
- objective
- constraints
- urgency
- linked_case_id optional
- authority_scope
- budget
- status

### Task
Employee-created executable unit of work.

Employees may decompose one WorkOrder into many Tasks without asking Founder for each step.

### WorkRequest
Typed request to another employee/office.

Examples:
- Strategy → Chart: compare technical structure of five candidates
- Strategy → IID: verify causes of earnings change
- IPRO → Strategy: clarify whether growth is one-off
- ARU → IID: search for evidence against thesis

### Message
Human/employee-readable communication attached to WorkOrder, Task, Request, Case, or Artifact.

### Workspace
Persistent employee working area:
- notes
- plans
- queries
- datasets
- charts
- code/notebooks
- intermediate results
- evidence references
- failed approaches
- final artifacts

Workspace state survives a single model call.

### Artifact
A produced work product:
- table
- chart
- screen result
- memo
- dataset
- query
- backtest result
- research note

Artifacts are not automatically Evidence or Decisions.

## Employee reasoning loop

The runtime must support:

1. Understand objective.
2. Inspect available context and prior work.
3. Make/update a plan.
4. Identify missing information.
5. Select tools or request another office.
6. Execute deterministic tools.
7. Inspect outputs/errors.
8. Revise plan.
9. Produce artifacts.
10. Promote sourced facts to Evidence when appropriate.
11. Form an InstitutionalPosition when role-authorized.
12. Report/hand off through the organizational protocol.
13. Record meaningful work history.

This loop must permit branching and iteration. It must not be encoded as one fixed pipeline.

## Department workstation doctrine

A workstation is the employee's computer.

It exposes composable capabilities through typed tools. The LLM decides which tools to call and in what order; deterministic code performs calculations/data operations.

### Shared core workstation

Every analytical employee may receive role-appropriate access to:
- security/universe search
- data catalog / schema discovery
- evidence search
- SQL/query execution against authorized datasets
- Python/statistical compute sandbox
- table builder
- chart builder
- artifact storage
- institutional memory search
- task/request/message tools

No employee receives every permission by default.

### Chart / Technical Analysis workstation

Required capabilities:
- OHLCV by symbol, date range, and timeframe
- 1m/3m/5m/15m/30m/1h/D/W where data provider supports it
- adjusted/unadjusted price metadata
- volume and turnover
- indicator calculation: MA/EMA, RSI, MACD, Bollinger, ATR, ADX, Ichimoku and extensible custom indicators
- cross-sectional scanners
- chart rendering and annotation
- event-window extraction
- pattern collection builder
- forward-return/event-study engine
- dataset export

The LLM may invent a new study by composing these primitives without requiring a new hard-coded command.

### Strategy / Screening workstation

Required capabilities:
- KOSPI/KOSDAQ/security universe
- fundamentals by quarter/year
- derived financial metrics
- foreign/institution/pension trading flow
- price/return/liquidity
- sector/industry classification
- flexible filter/query builder
- ranking
- table/chart generation
- candidate-set persistence
- backtest/event study request
- handoff to Chart/IID/IPRO/ARU

Example objective that must be solvable without adding a bespoke program:
"Find KOSPI/KOSDAQ names with >20% YoY sales growth over the recent three-month reporting window, two consecutive quarters of improving operating margin, and foreign net buying over the last 10 sessions. Add reasons and risks."

A follow-up such as "keep only names also bought by institutions and pension funds" must modify the existing work context rather than start a new bespoke feature.

### Research / IID workstation

Required capabilities:
- source/document/news retrieval
- company filings and earnings materials
- event search
- evidence extraction with provenance
- source reliability metadata
- contradiction search
- timeline construction
- Evidence promotion

### Portfolio / SPMG workstation

Required capabilities:
- current portfolio snapshots
- candidate sets
- allocation simulations
- exposure/factor calculations
- scenario comparison
- deterministic optimization where approved
- portfolio position drafting

### Risk / IPRO workstation

Required capabilities:
- exposure, concentration, liquidity, volatility, correlation
- scenario/stress tools
- policy lookup
- exception detection
- independent recomputation
- RiskAssessment generation

### ARU workstation

Required capabilities:
- read all relevant thesis/evidence artifacts
- contradiction/evidence search
- counterfactual/scenario tools
- request independent data
- challenge creation

## Organizational communication protocol

All employee-to-employee work uses one protocol rather than bespoke function chains.

Core objects:
- WorkOrder
- Task
- WorkRequest
- Message
- Artifact
- Evidence
- Finding
- InstitutionalPosition
- RiskAssessment
- Challenge
- CommitteePackage
- Decision
- LedgerEvent

Required behaviors:
- every request has issuer, recipient, objective, status, timestamps, and linked context;
- recipient may accept, reject with reason, ask clarification, delegate within authority, or complete;
- replies preserve the thread;
- artifacts/evidence are referenced by IDs, not copied as untraceable prose;
- all offices use the same transport/storage semantics;
- office-specific behavior comes from role, tools, authority and output contracts, not a separate ad-hoc pipeline.

## Secretary runtime

The Secretary is the Founder attention router, not merely a chat UI.

Responsibilities:
- understand broad Founder requests
- locate relevant existing Case/WorkOrder/context
- route to office(s)
- split work only when necessary
- request clarification only when material ambiguity blocks safe execution
- monitor open high-value work
- consolidate completed reports
- surface unresolved disagreement
- suppress routine operational noise
- never fabricate missing departmental work

The Founder should be able to say:
"Find interesting Korean names with improving fundamentals and real buying pressure. Investigate the best ones."

The Secretary may create a Strategy WorkOrder, allow Strategy to request IID/Chart/IPRO work, and return a consolidated result without the Founder specifying the pipeline.

## Initiative and company growth

Employees may discover useful work while performing authorized tasks.

P1.3 introduces proposals, not unrestricted self-directed execution.

Employee-generated initiative levels:
- NOTE: record an observation
- PROPOSE_TASK: propose or create a bounded research Task within office budget
- REQUEST_WORK: ask another office for bounded analysis
- PROPOSE_EXPERIMENT: propose a deterministic screen/backtest/research experiment
- ESCALATE: ask Secretary/manager/Founder when authority or budget is exceeded

Allowed without Founder approval:
- read-only research
- deterministic calculations
- bounded scans/backtests
- creation of research artifacts
- internal requests within configured budget
- proposing new hypotheses/experiments

Not allowed without higher authority:
- live orders
- capital allocation changes
- modifying investment/risk policy
- disabling controls
- changing employee authority
- unbounded recurring jobs
- uncontrolled external spending/data purchases
- deleting institutional history

This is how the company can improve without turning autonomy into uncontrolled agency.

## Deterministic software vs LLM responsibility

Use deterministic software for:
- arithmetic
- financial ratios
- indicators
- screen filters
- portfolio/risk calculations
- statistics/backtests
- data transformations
- validation
- deduplication
- state transitions
- permissions
- budget enforcement

Use LLM reasoning for:
- interpreting broad objectives
- planning
- deciding which tools/data are needed
- forming hypotheses
- choosing follow-up analyses
- explaining results
- identifying uncertainty
- deciding when to request another office
- synthesizing conflicting evidence
- proposing new research

An LLM assertion never substitutes for a deterministic calculation when the latter is available.

## Memory model

Separate:
1. Working context — current Task/WorkOrder.
2. Workspace memory — employee's persistent project materials.
3. Institutional memory — Cases, Evidence, Findings, Positions, Decisions, Ledger.
4. Learning memory — validated reusable procedures/experiments.

Do not dump the entire company history into every model prompt. Retrieval is scoped by task, role and permissions.

## Model runtime requirements

- provider/model abstraction
- structured tool calls
- max iterations / token / cost budget
- timeout/retry policy
- explicit tool errors returned to employee
- prompt/context provenance
- model-call audit metadata
- deterministic replay of tool results where possible
- no hidden mutation of institutional records

## Compute sandbox

Employees need a computer, but arbitrary code execution is a security boundary.

Initial compute environment must:
- be isolated from broker credentials
- have no order-submission capability
- expose approved datasets read-only
- limit filesystem/network/runtime resources
- persist selected artifacts, not arbitrary machine state
- log tool invocations
- require explicit adapters for privileged actions

## Development sequence correction

P1.3A — Organization Runtime
- Employee
- WorkOrder
- Task
- WorkRequest
- Message
- Inbox
- persistent Workspace metadata
- common status/ledger semantics

P1.3B — Tool/Workstation Runtime
- ToolRegistry
- capability/permission model
- structured tool invocation
- deterministic compute/data tools
- artifact store

P1.3C — First real employee vertical slice
Strategy Analyst:
- receives broad natural-language WorkOrder
- creates its own plan
- uses a fixture/local universe + fundamentals + flow tools
- modifies its plan on follow-up
- creates table/memo artifacts
- requests one bounded analysis from another office
- produces Evidence-linked report

P1.3D — Secretary orchestration
- broad Founder request → routed WorkOrder
- status tracking
- consolidated response
- Founder interruption policy

P1.3E — Chart Analyst workstation
- multi-timeframe OHLCV
- indicators
- scanners
- chart artifacts
- event-study/pattern collection

P1.3F — Artifact Gates
The previously designed Committee artifact gate is implemented after employees/workstations can actually produce the artifacts.

## Acceptance demonstration

The runtime must demonstrate, using synthetic/local fixture data:

Founder:
"Find Korean stocks with strong recent sales growth, two quarters of improving operating margin, and foreign net buying. Give me reasons and risks."

Expected:
1. Secretary routes a broad WorkOrder.
2. Strategy employee creates a plan without a bespoke command.
3. Employee discovers available data/tool schemas.
4. Employee invokes deterministic screening primitives.
5. Employee persists candidate set/table.
6. Employee requests supporting research/risk work through WorkRequest.
7. Results return through the same organizational protocol.
8. Employee revises analysis.
9. Founder follow-up adds institution/pension buying.
10. Employee modifies existing task/query context rather than requiring new code.
11. Final report references artifacts/evidence.
12. Ledger reconstructs who requested, computed, changed and reported what.

No live investment action is permitted.

## Known risks / non-negotiable design concerns

1. Hallucinated capability: employees must discover tools from ToolRegistry; never pretend a tool/data source exists.
2. Data licensing/coverage: minute bars, Korean investor-flow and fundamentals require real provider coverage later; runtime must expose availability honestly.
3. Cost explosion: autonomous loops need per-task budgets and stop conditions.
4. Agent theater: adding many named LLMs without measurable work separation is forbidden.
5. Prompt-only logic: repeated stable work should graduate into deterministic tools.
6. Silent learning: employees may propose reusable procedures, but production policy/tool changes require validation/versioning.
7. Context contamination: office memory must be scoped; raw model conversation is not institutional truth.
8. Reproducibility: every important conclusion must retain tool inputs, data timestamps, artifact IDs and evidence references.
9. Security: compute/research employees must be isolated from execution credentials.
10. Founder overload: routine work must resolve internally; autonomy is useful only if it reduces, not increases, Founder attention.

## Deferred Founder governance decision

IPRO authority remains unresolved:
- absolute veto on policy breach, or
- Founder override through explicit PolicyException.

Do not silently choose this in code.
