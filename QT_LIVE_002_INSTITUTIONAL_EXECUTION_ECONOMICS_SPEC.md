# QT-LIVE-002 — Institutional Decision-to-Execution Economics Lab

Date: 2026-10-03
Status: EXPERIMENT / PAPER FIRST

## Purpose

QT-LIVE-001 proves that QuanTrade can consume live public market data and maintain a durable paper account.

QT-LIVE-002 tests a different question:

> Does a governed AI investment-office workflow add enough decision quality and flexibility to justify its model cost, infrastructure cost, latency, and trading friction?

The experiment therefore evaluates the **institutional process itself**, not only a trading rule.

## Permanent evaluation principle

A strategy or decision process is not economically useful merely because its gross return is positive.

QuanTrade must measure:

`Net Decision Value = Trading Outcome - Trading Friction - AI/Infra Cost - Latency Cost - Process Failure Cost`

where each component is separately observable.

## Decision path under test

Normal path:

`Market observation
→ Event/Opportunity
→ Market/Research review
→ Portfolio view
→ Risk review
→ Adversarial challenge
→ Investment Committee package
→ ENTER | WAIT | HOLD | REDUCE | EXIT
→ Decision Plan
→ PAPER execution
→ Outcome attribution`

The key experimental difference from QT-LIVE-001 is that a signal cannot directly become an execution.

## Shock path

Sudden price moves require a different latency budget.

`Tick/short-bar stream
→ D0 deterministic ShockDetector
→ immediate pre-authorized risk guard
→ D1 urgency/routing
→ bounded Fast IC
→ PAPER response
→ later D2 post-event review`

D0 may only select from pre-authorized paper actions:
- NO_NEW_ENTRY
- CANCEL_PENDING
- HOLD
- REDUCE_25
- REDUCE_50
- EXIT
- ESCALATE

It may not invent a new strategy or increase exposure.

The experiment initially remains paper-only. Automatic live risk action is not authorized.

## Why D0 exists

A frontier LLM is not a real-time risk-control primitive.

If BTC moves materially while:
- market data is fetched,
- a chart is rendered,
- several AI employees reason,
- the committee package is assembled,
- a model/provider retries,

the decision may arrive after the useful execution window.

Therefore immediate safety must be deterministic and pre-authorized; AI explains, challenges, adapts, and decides within a measured latency budget.

## Chart interpretation experiment

Two information paths are compared.

### Path A — Structured market state

`OHLCV/order data
→ deterministic features
→ compact structured context
→ AI`

Examples:
- return over 1m / 5m / 1h / 4h
- realized volatility
- SMA distance/slope
- volume shock
- drawdown
- spread/order-book metrics when available

### Path B — Chart vision

`OHLCV
→ rendered chart image
→ vision-capable model
→ AI interpretation`

Chart vision is optional and must earn its cost.

For every decision episode record:
- chart rendering latency
- chart/image payload size where observable
- vision/provider token usage where reported
- structured-data preparation latency
- model input/output/cached/thinking token counts
- provider/model version
- model latency
- tool latency
- total workflow latency
- market move during deliberation

The experiment should eventually compare Path A vs Path B on the same replay episodes.

## Institutional action vocabulary

A committee result must resolve to one of:
- ENTER_NOW
- WAIT
- HOLD
- REDUCE_25
- REDUCE_50
- EXIT
- CANCEL_PENDING
- PAUSE_NEW_ENTRY
- ESCALATE

Each result carries:
- confidence
- rationale artifact reference
- evidence references
- dissent summary
- expiry / re-evaluation condition
- maximum execution delay

## Economic telemetry

### Market / execution

- event observed timestamp
- decision timestamp
- order-intent timestamp
- simulated-fill timestamp
- observed price at each stage
- spread/slippage assumption
- fee assumption
- position before/after
- realized/unrealized P&L

### AI

Per model call:
- employee / role
- provider
- model
- input tokens
- output tokens
- cached input tokens
- reasoning/thought tokens when exposed
- call latency
- retry count
- calculated USD cost using a versioned PricingSnapshot

Never hard-code one vendor's price into historical records without a pricing version/date.

### Program / infrastructure

- market-data requests
- chart render time
- deterministic-feature compute time
- tool invocations
- workflow wall-clock time
- allocated cloud/compute cost when measurable

### Latency opportunity cost

The process records the price when the event was observed and the price when a decision became executable.

For a proposed long entry:

`entry_delay_bps = (executable_price / event_price - 1) × 10,000`

For an exit/reduction, sign is interpreted relative to the position.

This is recorded separately from ordinary fill slippage.

## Evaluation baselines

Every representative episode should be compared against:

1. **DIRECT_RULE** — deterministic rule executes immediately.
2. **SINGLE_AGENT** — one AI receives the same structured market state.
3. **INSTITUTIONAL** — QuanTrade multi-office workflow.
4. **INSTITUTIONAL_VISION** — institutional workflow with chart-vision evidence when selected.

This prevents measuring QuanTrade only against doing nothing.

## Shock resilience suite

Replay both historical and synthetic episodes:
- ±1% in 1 minute
- ±3% in 5 minutes
- ±5% in 15 minutes
- volatility spike with reversal
- sharp breakout that continues
- market-data stale/failure
- one AI provider timeout
- one AI output-contract failure
- 5s / 30s / 120s artificial reasoning delay

Measure:
- time to containment
- time to decision
- exposure during delay
- missed-opportunity / avoided-loss bps
- model cost
- execution cost
- contradictory action count
- safety-rule violations
- eventual P&L / benchmark difference

## Initial success criteria

QT-LIVE-002 is not successful because one trade makes money.

The experiment is useful when it can answer:
- what the institutional workflow costs per decision;
- how long it takes from event to executable intent;
- whether chart vision improves outcomes enough to justify its cost/latency;
- which tasks can use D0/D1 instead of D2;
- which shock thresholds require deterministic immediate handling;
- whether INSTITUTIONAL outperforms simpler baselines net of all measured costs;
- when the process is too slow and must decline to trade.

## Live transition gate

Real-money micro-live is not permitted until:
- paper institutional path is durable and auditable;
- shock path passes deterministic safety tests;
- cost/latency attribution works end-to-end;
- no hidden real-order authority exists;
- the user/Founder explicitly authorizes the next stage.

QT-LIVE-001 remains the market/paper-account substrate.
QT-LIVE-002 sits above it as the decision-process experiment.
