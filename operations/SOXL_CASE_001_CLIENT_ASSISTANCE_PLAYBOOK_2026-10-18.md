# QT-SOXL-CASE-001 — QuanTrade Client Assistance Playbook

**Prepared:** 2026-10-18 KST
**Status:** PROPOSED / PAPER-ONLY / REQUIRES CLIENT MANDATE BEFORE ANY FINANCIAL ACTION
**Direction class:** EXTENDS current QuanTrade PIO vision; bounded SOXL investment Case and user-experience protocol, not a canonical mandate or a validated strategy.
**Window:** first operational simulation 2026-10-19 to 2026-12-31, then post-mortem January 2027.
**Related:** [Canonical Vision](../QUANTRADE_CANONICAL_VISION.md), [decision-to-PnL roadmap](../architecture/QUANTRADE_DECISION_TO_PROFIT_ROADMAP_2026-10-18.md), [paper ledger #126](https://github.com/ringoincidents/quantrade/issues/126), [SOXL hypotheses #129](https://github.com/ringoincidents/quantrade/issues/129), [news/social #130](https://github.com/ringoincidents/quantrade/issues/130), [meta-sentiment #131](https://github.com/ringoincidents/quantrade/issues/131).

> Vision: Not to predict perfect tops and bottoms, but to provide evidence-based choices: NO_TRADE, ENTER, ADD, HOLD, REDUCE, EXIT, with current data and after-cost downside controls. **In this proposal, a recommendation is NOT an order and no market trade authority is granted.**

## 1. When exactly QuanTrade should assist

Timezone KST / America-New_York exchange calendar, observe official holidays and extended-hour exceptions. On US daylight savings 2026-10-19 through 2026-10-30 regular session is **KST 22:30–next day 05:00**; after 2026-11-01 DST ends, starting 2026-11-02 regular session is **23:30–next day 06:00**. Do not hardcode the hour; calculate with XNYS calendar and TZDB.

| Moment | Proposed local time/cadence | System work | Founder-facing behavior |
|---|---|---|---|
| Preparation | 2026-10-18, before first observed trading session | Register instrument, objective, official NYSE Semiconductor Index and SOXL source, provider permissions, cost assumptions, funding/mandate placeholders, frozen experiment variants. | One **initial Case card**, no automatic trade |
| After US close | **07:00 KST** after verified official close on each US session | Finalize last-session data, news, signals, volatility, prior decisions; validate revisions, corporate actions and source timestamps. | Save immutable daily state; no push if unchanged |
| Client briefing | **18:30 KST** on weekdays following a US session | Compare Cash / existing holding / small entry / reduce / exit, prepare full counterarguments & data gaps. | One-screen digest; escalate only significant change; phone attendance not assumed |
| Before US open | **21:00 KST** on US session days | Update corporate/market news as of current time, check decision expiry, client mandate and Risk; verify broker/session eligibility for future execution. | Final **proposal** only if gates passed; if not accessible, DEFER rather than unapproved order |
| US session / shocks | Event-driven while market open, **requires persistent backend** | Validate large price change, emergency news/credit/vol volatility, simulated order/position and risk reconciliation. | If paper: record/reassess. Real future: independent circuit breaker/venue-level safeguards, never depend on iPhone or GitHub Action timing |
| Weekly review | Monday 19:00 KST following previous Friday close, existing weekly study as base | Trend, market/regime uncertainty, exposure, competing entry/exit variants, missing data and model calibration. | One concise decision memo and next checkpoint |
| Closeout | At case expiry by 2026-12-31 US regular session close, if paper position exists | Apply hard horizon / exit model, after-cost P&L and counterfactual missed upside; append-only post-mortem. | Show what worked, what failed and what not to repeat |

**User access constraints:** build asynchronous mobile review, not a system where user must watch US markets overnight. Live security-critical risk actions require an always-on host and broker-supported order protections; **hourly ChatGPT automations and 3h GitHub Actions are not such a control**. This document sets desirable cadence, not assertions that workers already run at these times.

## 2. Trigger ladder — thresholds here are *monitoring hypotheses*, not validated SOXL trading signals

| Trigger group | Provisional condition | Next state (never automatic BUY) |
|---|---|---|
| Market shock | Exact semiconductor underlying session absolute move >= **3%**, or five-session move >= **8%** | INVESTIGATE, frozen data screenshot/log with event source |
| SOXL volatility | SOXL session absolute move >= **8%**, five-session fall >= **20%**, or 20-day realized vol abnormal | INVESTIGATE; no promotion without strategy validation |
| Macro/event | Federal Reserve decision, CPI/PPI surprise, TSMC/MU/NVDA earnings, new US semiconductor export restriction, reliable AI-financing/credit dislocation | Competing causal stories, source revisions and risk review |
| Technical entry *candidate* | Official semiconductor underlying close > 20-day SMA two completed sessions and 20-day SMA rising, plus risk regime approved; pre-registered alternatives (5-day reversal, volatility filter) | \`PAPER_CANDIDATE\` only when after-cost OOS evidence exists; else RESEARCH_ONLY |
| Data failure | ICESEMIT unavailable, corporate action mismatch, news publication time unreliable, Risk budget missing, provider permission absent | DATA_BLOCKED / NO_TRADE |
| Risk deterioration while holding | Portfolio loss-budget breach, stale data, new disqualifying event, model invalidation, broker/reconciliation failure | Risk veto and paper halt; later live only using independent approved protective mechanism |
| Profit-taking/time | Target return candidate (+10%, +20%), 10-session low exit, trailing stop, 15-session time stop, Dec final session expiry | Compare as **mutually competing preregistered paper variants**; never cherry-pick after observed outcome |

Missing independent source or unclear estimate = UNKNOWN, not zero risk. Social opinion and long Threads essay = claims to test, never trigger capital movement alone.

## 3. Decision process and who is allowed to act

States:
\`REGISTERED → WATCH → INVESTIGATE → ELIGIBILITY_REVIEW → PAPER_PROPOSAL → PAPER_ACTIVE → PAPER_EXITED → REVIEWED\`
At any stage: \`DATA_BLOCKED\`, \`RESEARCH_REJECTED\`, \`RISK_VETO\`, \`DEFERRED\`, \`EXPIRED\`, \`NO_TRADE\`.

- **Research** produces causal claims, falsifiers, as-of evidence and out-of-sample tests; never capital size or order.
- **Portfolio** compares cash vs small/medium allocations under net-return distributions; uses Client Mandate privately, not in public Repo.
- **Risk** vetoes if uncertain data, correlated exposures, excessive expected shortfall, gap stress, concentration, mandate, cash needs or broker capability missing.
- **Committee** documents action rationale, alternatives and negative evidence.
- **Decision Management** decides NOW / CONDITIONAL / DEFER / REASSESS / CANCEL, enforces evidence freshness and expiry.
- **Execution** is paper-only by default; real orders require separate explicitly limited approval, legal broker access, live order reconciliation, stop safeguards and kill switch. Never infer approval from a GitHub issue, AI text, mobile chat, or prior research.
- **Performance** records forecast vs result, timing choice, sizing choice, exit choice, after-cost returns, slippage, maximum drawdown and system/LLM costs.

Sizing: User must privately define disposable **investment pool K**, **maximum *total-portfolio* stress loss L**, **maximum holding horizon H**, allowable correlation/required liquidity and special prohibitions. For each simulated scenario loss fraction \(q\), maximum proposed capital at risk is capped by \(L / q\), portfolio concentration and broker limitations; \(q\) is a *scenario*, not a guaranteed loss limit (SOXL could lose much more). Risk budget missing => **NO_TRADE**. "70% because six factors low" is not sufficient.

## 4. Standard one-screen Case card

- **Header** Case / instrument / as-of exchange+KST / source freshness / model version.
- **Regime** trend, vol, macro, sector credit, actual underlier.
- **Available choices** CASH / ENTER_10%_OF_APPROVED_POOL / ENTER_20%_OF_APPROVED_POOL / HOLD / REDUCE / EXIT; numbers are *sandbox choices*, not approved allocations.
- **Expected outcome** net return distribution at 1/5/15 sessions, low-tail loss, fees, stress drawdown, relative to cash and matched risk exposure; return unavailable = N/A.
- **Evidence** facts with citations and contradictory evidence.
- **Risk** independent veto / caps / missing Client Mandate.
- **Recommendation** NO_TRADE or proposal with max size and **entry plus exit rules together**.
- **Authority** RESEARCH ONLY / PAPER APPROVED / LIVE NOT AUTHORIZED, always visible.
- **Next review** next scheduled date and event triggers, avoiding notification spam.

Example for 2026-10-18: status **REGISTERED / RESEARCH_ONLY / DATA_AND_STRATEGY_VALIDATION_PENDING / NO_TRADE**, not a claim about actual future price direction.

## 5. SOXL tactical case experiment

Freeze candidate strategy variants before watching performance:
- A CASH all period, B small fixed-weight SOXL entry on fixed date + fixed exit, C underlying index trend / volatility controlled small entry + time limit, D C + verified macro/credit risk features.
- Entry only after fully observed feature, next **actually executable** exchange timestamp, not historical close same bar.
- Every variant has paired exit: loss/thesis invalidation (market gaps modelled), time stop and year-end horizon, plus one of fixed vs trailing profit-taking hypotheses.
- Compare exposure-weighted / equal-risk matched baselines as well as raw SOXL buy-hold and cash. Include a no-trade decision. At least independent walk-forward validation, costs, rough significance and stress.
- Social/news/community add as incremental ablation only after permission, exact original and first-seen timestamp, sufficient denominator, source-revision handling. Poorly sampled forum posts must never raise size directly.
- Performance is *not* finalized when code tests pass. Need real qualified sources, actual historical completed simulation, untouched holdout and several forward weeks/regimes.

## 6. Next 3 PR acceptance contracts (not completed by this document)

**PR-1 data:** exact ICESEMIT/SOXL versioned sources, raw+adjusted corporate actions, calendar+available_at, 3 representative shock fixtures, \`BLOCKED\` on unresolved rights/source.

**PR-2 paper:** immutable order lifecycle, fees, fills/slippage/overnight gaps, cash/positions/equity, idempotent replay and flat/hold/trend baseline; portable test suite and reproducible cost report.

**PR-3 bounded decision:** personal mandate private, Risk veto, size proposal, simultaneous entry/exit and DecisionPlan expiry, paper-only execution with postmortem on one recovered persisted Case.

The above are **requested future engineering**, not claimed implementation. Related technical priority #126 + provider #111. Keep deployment/lab infrastructure minimal.

## 7. One essential client preference unresolved

In private conversation ask: **For this SOXL Case's *dedicated test capital*, what is the maximum KRW loss the client will accept in a very adverse market event?** The target size is meaningless without risk tolerance and total-portfolio constraints. Do not persist the answer in public repository.

**Current rule:** No verified mandate or validated positive strategy => never propose a positive live trade allocation. No executing real orders without separate explicit authorization.
