# QuanTrade — 검증 가능한 진입·비중·청산 의사결정 루프 개발 로드맵

**Recorded:** 2026-10-18 (Asia/Seoul)  
**Classification:** EXTENDS / PROPOSED TECHNICAL ROADMAP, NOT CANONICAL REPLACEMENT  
**Authority:** READ-ONLY RESEARCH AND PAPER-ONLY until separately authorized. NO LIVE ORDER AUTHORITY.  
**Governing source:** [QUANTRADE_CANONICAL_VISION.md](../QUANTRADE_CANONICAL_VISION.md)  
**Existing work:** [provider boundaries](./TRADING_CAPABILITY_PROVIDER_CONTRACT.md), [#111](https://github.com/ringoincidents/quantrade/issues/111), [#126](https://github.com/ringoincidents/quantrade/issues/126), [SOXL research #129](https://github.com/ringoincidents/quantrade/issues/129), [social research #130](https://github.com/ringoincidents/quantrade/issues/130), [meta-sentiment #131](https://github.com/ringoincidents/quantrade/issues/131).

## 0. Fundamental outcome and boundaries

QuanTrade cannot *know* the ex post perfect bottom, top, optimal exposure or guarantee a profit target. It should select from bounded actions **NO_TRADE / ENTER / ADD / HOLD / REDUCE / EXIT / REASSESS** to maximize an explicitly pre-registered, client-specific prospective objective **net of execution costs and tail-risk limits**.

A paper-only objective proposal: maximize scenario-weighted expected terminal utility of portfolio wealth, penalize transaction cost and risk, subject to mandated **maximum committed capital, maximum scenario expected shortfall, concentration, liquidity, horizon, inability-to-trade and kill-switch constraints**. Compare with always-cash, fixed-weight SOXL, unlevered semiconductor exposure, and price-only decisions. Demonstrate genuine incremental gains; do not assume AI/social data help.

Goals include: (a) avoid ruin and excessive loss; (b) seek positive **risk-adjusted after-cost** performance over a specified horizon; (c) preserve cash for other goals; (d) prefer NO_TRADE when evidence insufficient. Financial targets and loss budgets belong in **private** Client Intelligence/Holdings, never the public repository.

## 1. Implementation gap assessment (verified vs unknown)

| Area | Grounded current evidence | Gap / status |
|---|---|---|
| Canonical office structure | Vision specifies Client->Mandate->Research->Portfolio->Risk->Committee->Decision Management->Execution->Learning | **Policy/design defined; complete end-to-end running product not established by files inspected** |
| Deterministic features | \`quantrade/capabilities/features.py\` has native close-only return, total return, SMA5/20, volatility, provider metadata and provider comparison | **Reference provider exists**; no integrated official timestamped ICESEMIT OHLCV/provenance/market-corporate-action context in this feature input |
| Previously tested indicator alpha | \`indicator_significance_report.json\` records seven signals all rejected after correction | **No verified positive trading edge** in the reviewed report |
| Historical SOXL strategy | #129 requires official underlier, adjust splits/distributions, sealed testing, after-cost exit comparison | **Research proposed, not validated** |
| Social and news | #130/131 have curated data, semantic and prospective validators; collector_v1 collects public *news metadata* / Naver *relative search interest* when API allows | **No authorized representative forum feed, no proven predictive lift**; publication time != GDELT seen time |
| Paper ledger | #126 remains OPEN, PROPOSED/PAPER-ONLY | **Complete fill/fee/position/cash/order lifecycle not verified; implement first** |
| Provider abstraction | Architecture names MarketData, Feature, Simulation, PortfolioAnalytics, Execution, Performance; #111 OPEN | **Boundary specified; independent production integration and replaceability proof not established** |
| Broker | Binance Stocks eligibility/order/fee/data feasibility is PENDING in 2026-10-11 record | **No live venue authorization**, and SOXL availability/eligibility unconfirmed |

**Inspection limitation:** this status derives from canonical documents, source files and open issues checked on 2026-10-18, not a full repository tree + running deployment audit. Avoid inferring that any uninspected service does not exist.

## 2. A narrow first vertical slice (deliver THIS before more agents)

**Case:** SOXL October–December tactical recovery, daily close-based signals, NYSE calendar, weekly risk review, no real orders. Minimal alternative actions: CASH, HOLD_SMALL, ENTER_SMALL, REDUCE, EXIT. Larger size optimization follows proven engine correctness.

\`\`\`
Timestamped MarketDataProvider (SOXL + EXACT NYSE Semiconductor Index + QQQ)
        ↓ [RAW, ADJUSTED, trading calendar, corporate actions, as-of availability]
Deterministic MarketState Compiler (features and report quality)
        ↓
Hypothesis/Experiment Registry & Evidence (frozen rule/config/hash, sources & negatives)
        ↓
SimulationProvider (no lookahead, orders, fills, fees, slippage, gaps, ledger)
        ↓
Portfolio Target Calculator (cash, current exposure, options)
        ↓
Independent RiskPolicy (veto, missing inputs => NO_TRADE)
        ↓
CommitteeDecision → DecisionPlan [NOW/DEFERRED/CONDITIONAL/CANCELLED]
        ↓
PAPER ExecutionProvider → reconciled positions/orders/cash/equity
        ↓
Performance Review (net return, DD, alpha vs fair control, forecast calibration)
        └──> append-only evidence and next falsifiable hypothesis
\`\`\`

Outputs of an uninterrupted paper run must be inspectable from **one phone-friendly Case** without generic multi-Lab debugging screens.

## 3. Prioritized engineering gates

### P0 — Versioned data and time integrity [BLOCKING]

- Buy or lawfully obtain verified SOXL daily **raw and adjusted OHLCV**, splits, dividends, NAV/sessions, *exact* ICE NYSE Semiconductor Index (not PHXL SOX/SOXX, and acknowledge pre-Aug-2021 benchmark transition), QQQ and rates/credit sources. Supplier license and exact data availability matters more than size of dataset.
- Standard time fields: \`valid_at\`, \`published_at\`, \`first_seen_at\`, \`ingested_at\`, \`revised_at\`, timezone, provider + revision, market session, adjustment convention.
- Corporate earnings after US close may only affect orders after that announcement. GDELT \`seendate\` is not source's initial publication; Naver DataLab ratio is normalized attention, not crowd bullishness.
- Missing/bad/late/unlicensed inputs must become \`DATA_BLOCKED\` / \`NO_SIGNAL\`, never interpolated into performance.
- **DoD:** whole data-pull reproducible with hash; fixtures for DST, holidays, splits, after-hours timestamps, revised macro data, duplicate posts.

### P1 — Net-of-cost paper trading ledger and counterfactual baseline [BLOCKING, link #126]

- Timestamped \`OrderIntent → Accepted/Rejected → Partial/Filled/Cancelled\`, signed prices / market calendar, idempotency keys, cash, positions, mark-to-market, fees, slippage, spread, FX, distributions and gap losses.
- Same-bar closing signal **cannot fill at that close**. Simulate earliest executable next bar; stop price not guaranteed on gaps.
- Flat/cash, buy-hold SOXL, unlevered exposure and equal-risk fixed portfolio baselines use identical data and costs.
- **DoD:** deterministic replay identical across crash/restart; tests reject stale bar, bad quote/fee, insufficient cash, duplicate order, no fill, partial fill, split handling; reproducible trade ledger and report.

### P2 — Research hypothesis registry & falsification laboratory

- Parse each community claim into \`Claim → Evidence → Contradiction → TestableHypothesis → ExperimentVersion → Outcome\`.
- Do NOT promote self-published probabilities, "6-factor risk" formulas or retrospective cherry-picked 4/4 to strategy authority.
- Freeze model universe, parameters, entry/exit, cost assumptions, data cutoff; log every trial, failed test, multiple comparisons, negative findings.
- Walk-forward train/validation/holdout, leave-year-out (where independent), purge overlapping 1/3/5-day labels, block bootstrap / confidence interval, false-bottom regime audit and actual out-of-sample paper.
- **DoD:** repeated paper experiment reproduces losses as well as gains; explicit \`REJECT / INCONCLUSIVE / PAPER_CANDIDATE\` decision and causal/exposure limitations.

### P3 — Prospective action evaluation / portfolio-size optimizer

- Every decision compares \`NO_TRADE\`, enter at capped exposures, add, hold, reduce, full exit **jointly** on same forecast distribution with portfolio context. No magic "optimal point" label picked from future chart.
- Inputs: client's private mandate, investable surplus and horizon, existing exposures/correlation, financing and other uses, regime-specific forward return uncertainty, 3× daily compounding path and crash/gap stress.
- Optimize **net terminal portfolio utility / risk-constrained expected return** under cost and CVaR/tail loss, liquidity, FX, correlation and concentration limits. Exposure size is not automatically "risk level 15/30/50/70%"; use caps approved by independent Risk.
- Model alternatives start simple: price only → +macro/earnings → +credit → +social. Count additional forecast value on identical heldout sessions, not only accuracy; require a cost/exposure-adjusted benchmark improvement.
- **DoD:** in adverse scenarios outputs \`NO_TRADE\` or smaller risk; identical inputs yield same decision; stable against parameter perturbations; attributable why an action was chosen over alternatives.

### P4 — Entry and exit engine as ONE strategy contract

- Predefine together: qualifying market regime, trigger entry time (next executable bar), invalidation, maximum loss budget, scale-in increments, partial profit-taking, dynamic trailing exit, gap policy, time stop, hard horizon and cash destination.
- Compare exit methods fixed calendar, trend invalidation, 10-day low, volatility-adjusted trailing, staged take-profit, after costs.
- Distinguish **time to buy**, **what size**, and **time to exit**. A regime signal only constrains actions; it never directly submits an order.
- **DoD:** independent replay of profitable and losing trades, parameter robustness, early exit and sharp overnight gap; exact deterministic proposed DecisionPlan.

### P5 — Independent portfolio Risk, Committee, execution and operations

- Hard private mandate: maximum loss/day and lifetime, max size and correlated exposure, liquidity buffer, price quality, realized vs unrealized, loss limits, venue/jurisdiction constraints; Risk can independently veto any expected-return recommendation.
- Committee records thesis, counterargument, alternative, risk veto and approver. DecisionPlan has expiry and must revalidate at execution.
- Isolated ExecutionProvider (paper first), positions vs cash reconciliation, kill switch, broker session/rate limit, network restart/retry and no duplicate orders. **GitHub Action / hourly automation is not a latency-critical market risk stop.**
- Backend service must have persistent state and operational monitoring, independent of LLM session and phone. Live keys are not in the research repository.
- **DoD:** shadow-run multiweeks and injected failures; manual explicit *new* approval and broker eligibility for every promotion; no blanket auto authorization.

### P6 — Evaluation, learning and minimal mobile UI

- After every paper action compute \`gross P&L, net P&L, spread/fees/FX, maxDD, CVaR, benchmark excess, missed upside, invalidated thesis, calibration, turnover and model/cloud costs\`.
- Separate market outcome from research forecast quality, timing, sizing, exit and execution. A profitable trade can be bad process; good risk avoidance can miss a rally.
- Append-only ResearchCase/Decision/Review with model+data+code hash; learning system proposes hypotheses for new tests, **not immediate changes to production strategy**.
- Mobile one-screen: current market regime; investable cash & target; current decision + next action; risk veto; evidence/alternatives; orders/positions; last outcome; approval (separate, role-limited).
- **DoD:** point-in-time reconstruction for any decision and consistent restart; Founder can see WHY/WHY NOT, without long multi-Lab scroll.

## 4. Suggested first controlled experiment

\`QT-SOXL-ENTRY-EXIT-001\` — Compare predeclared A/B/C/D on the same qualified trading sessions:
- A: CASH / no trade.
- B: fixed calendar/reversal entry and calendar exit with fixed small exposure.
- C: price trend + realized-volatility gate and same exit options.
- D: C plus verified credit/rates conditions. Social data enters a *later* incremental ablation only after timestamp rights and representative sampling.
- Ex ante risk of loss and profit target are separate; report net distribution and \`max drawdown\`. \`No trade\` is valid.
- Base engine should demonstrate crash 2018/2020/2022, strong trend 2025 and false rebound 2026, but **do not report 2026 post-Oct-17 performance before it happens**.

## 5. Minimal typed contracts (illustrative)

\`\`\`json
{
  "research_case_id": "QT-SOXL-ENTRY-EXIT-001",
  "as_of_utc": "<UTC timestamp>",
  "data_manifest_sha256": "<verified>",
  "hypothesis_version": "E2-v1",
  "validation_status": "PROPOSED",
  "market_regime": "HIGH_VOL_UNCERTAIN",
  "available_actions": ["NO_TRADE", "ENTER_SMALL", "HOLD", "REDUCE", "EXIT"],
  "candidate": {
    "action": "NO_TRADE",
    "proposed_weight": 0.0,
    "exit_plan": null,
    "risk_budget_ref": "<private mandate ID only>",
    "expected_return_distribution_ref": null
  },
  "risk_opinion": "NOT_YET_REVIEWED",
  "committee_decision": "NOT_AUTHORIZED",
  "decision_plan": "REASSESS",
  "execution_state": "PAPER_DISABLED",
  "evidence": [],
  "counterevidence": ["missing validated outcome distribution"],
  "next_review_at": "<UTC timestamp>"
}
\`\`\`
All shown enum values are proposed interface vocabulary, **not currently deployed state**.

## 6. Next 3 concrete implementation PRs

**PR-1 Data Contract:** typed \`MarketSnapshot\`, \`DataManifest\`, \`TradingCalendar\`, \`CorporateAction\`, point-in-time availability test fixtures. At least one official licensed price source; status \`BLOCKED\` when unavailable.

**PR-2 Replay Simulator / Paper Ledger:** \`SimulationProvider\` + immutable order journal + returns under cash, buy-hold and one frozen entry/exit candidate. Include deterministic crash/holiday/gap and fee tests. Existing issue [#126](https://github.com/ringoincidents/quantrade/issues/126).

**PR-3 Risk + DecisionPlan Loop:** independent hard limits and portfolio proposed weight with \`NO_TRADE\`, \`DEFERRED\`, \`CONDITIONAL\` and expiry; consistent replay and audit; model-dependent suggestions cannot override veto.

Only after these are tested add social and multi-agent sophistication. Existing #111 provider contracts should be reused rather than recreated.

## 7. Operational truth and blockers

At time of authoring: no demonstrated full market-data-to-risk-to-net-P&L-to-decision round trip on validated SOXL market history; no verified profit alpha; source-specific user mandates must remain private; official NYSE Semiconductor Index history, market data rights, cost model and brokerage eligibility are unresolved. **Document is a proposed milestone plan; creation of this file does not constitute code implementation or a completed simulation.**
