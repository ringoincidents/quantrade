# QuanTrade Alpha Lab — AI-agent trading case, handoff mechanism, and net-profit gates

- Record ID: QT-RSCH-2026-10-14-AGENT-HANDOFF-001
- Recorded: 2026-10-14 (Asia/Seoul)
- Kind: EXTERNAL CASE STUDY / OPERATING PATTERN / REVENUE PLAN CANDIDATE
- Classification versus canonical direction: `REFERENCE_ONLY + EXTENDS (candidate operating test)`; does not change investment mandate or authorize orders
- Disposition: **WATCH upstream trading claims + LEARN scheduling/handoff/role separation**
- Evidence grade: Author's public self-report and video captions/summary. **No independent brokerage statement, complete transaction ledger, reproducible code, or independently audited P&L verified.**
- Decision authority: None; Research only. No live key/order/risk-policy change, no automatic canonical memory promotion.

## 1. Sources and provenance

1. Primary creator video: Nate Herk, *I Gave GPT 6 Astra $10,000 to Trade Stocks...And This Happened* (published 2026-09-28), https://www.youtube.com/watch?v=eg_1NXDcoPk (video ID `eg_1NXDcoPk`).
2. Creator's self-reported breakdown: https://www.linkedin.com/posts/nateherkelman_i-gave-gpt-6-astra-10000-of-real-money-activity-7510319698249596929-VxzW
3. Derivative transcript/analysis (less authoritative, potentially error-prone): https://prepublish.ai/youtube-transcript/eg_1NXDcoPk ; https://youtubetosummary.com/s/i-gave-gpt-6-astra-10000-to-trade-stocks-and-thi-eg_1NXDcoPk
4. Exchange fee primary source (separate from the video): Binance Stocks FAQ (updated 2026-10-05), https://www.binance.com/en/support/faq/detail/a7469c7703524024b5bc2d492b03639d

**Inspection limits:** Public descriptions, accessible transcript summaries, creator account and repository documentation were inspected; no creator source repository / exact prompt versions / executions / broker audit log reproduced. Do not present this as code audit or independently verified investment performance.

## 2. Observations (not adopted as an alpha claim)

Creator describes a $10,000 seven-trading-day challenge against the S&P 500. Self-reported final portfolio was about $9,900 (-1.0%) versus about $9,980 (-0.2%) for the comparator: approximately **-0.8 percentage points relative performance**, and absolute loss. Short single-window duration, unknown risk-adjusted metrics, potentially non-matched exposures, strategy adjustments during evaluation, and unaudited fills mean this case cannot establish a profitable strategy.

Reported mechanism: scheduled AI sessions perform research and portfolio checks, retain handoff context between invocations, and submit recommended actions to a separate executor integrated with Alpaca. A mid-test role reassignment to a separate Grok Bot and loosened filters was described by the creator. **Separation alone does not demonstrate an independent or correctly governed execution permission boundary.** An executor must never treat arbitrary AI text/email as trade authorization.

## 3. Mechanism decomposition and existing-memory comparison

| Mechanism | Prior QuanTrade / Holdings precedent | Delta classification | Consequence |
| --- | --- | --- | --- |
| Scheduled agent invocations | Holdings Mission/Work and durable background Mission orchestration; QuanTrade daily/CI workflows | VARIANT | Do not create a new scheduler or agent type merely for a video |
| Resumable handoff with context and decision history | Holdings LLMH-051 support return, Change of Watch / Duty Packets; Knowledge/Context Pack | DUPLICATE / EXPERIMENTAL VARIANT | Test recovery of an investment Case after restart, retaining ownership and evidence |
| Research vs execution handoff | `QUANTRADE_CANONICAL_VISION.md` Research -> Portfolio -> Risk -> IC -> Decision Management -> Execution | DUPLICATE | Implement with structured, signed-by-authority order proposal, not natural-language bot-to-bot trade emails |
| Rechecking a strategy when too few trades occur | Historical candidate strategies and `indicator_significance_report.json` show absent validated edge | CONTRADICTS if used to relax risk | **Zero trades is an acceptable result**; never lower risk gates to increase trade counts |
| Objective measurement vs S&P 500 | Professional Decision Process + Performance & Learning canonical requirement | VARIANT | Pre-register **net** after fees/slippage/taxes, drawdown, turnover, and matched risk/exposure benchmark; compare buy/hold and flat |
| Profit from AI agents | No verified alpha in current QuanTrade record | UNPROVEN | AI orchestration does not add measurable trading edge by itself |

Relevant baseline records:
- `QUANTRADE_CANONICAL_VISION.md` (risk independence, PIO process, validation before automation)
- `research/2026-10-11_BINANCE_STOCKS_API_FEASIBILITY.md` (Stocks API and Korean account permissions still unverified; fee-aware paper phase)
- `indicator_significance_report.json` (seven candidates fail required adjusted validation)
- Holdings `docs/research/QUANTRADE_STRATEGY_MEMORY_PROTOCOL_2026-10-05.md`
- Holdings `docs/research/TECHNOLOGY_ASSIMILATION_PROTOCOL_v0.1.md`
- Holdings `AGENTS.md` (Change of Watch, authority, no silent memory promotion)

## 4. Reusable operating pattern

```text
Pre-registered hypothesis / experiment ID
    -> authenticated market data snapshot (time / source / validity)
    -> deterministic features + model-versioned optional interpretation
    -> independent fee/slippage/risk gate (can return NO_TRADE)
    -> immutable paper-order intent + idempotency key
    -> simulated exchange lifecycle (reject / partial / filled / cancelled)
    -> durable P&L ledger and benchmark
    -> handoff snapshot (DONE / open orders / risks / next action / owner)
    -> next scheduled session resumes same experiment, not new mission
    -> bounded performance review / compare / reject or revise
```

Required invariant: Only an authorized executor can transform an approved, typed `OrderIntent` into a broker request; agent notes, email, summaries, or Founder chat do not confer order authority. Mandatory kill switch, recovery, stale-data rejection, duplicate-order protection, and reconciliation between desired and actual exposure. No scheduled CI workflow alone may serve as a time-critical kill switch (see QuanTrade August 2026 scheduler-delay incident).

## 5. Economic gate before more automation

**Unit economics first.** At the Binance Stocks FAQ's published standard USD <=350 order fee floor ($0.35 on buy and $0.35 on sell), a $10 round trip incurs $0.70 platform fees (7% of $10) **before** spreads, execution slippage, conversion and taxes. Actual fee tiers/promotions, eligibility and order-preview must be verified separately. The $10 initial test budget should be treated as **integration capital, not a plausible recurring-income base**. Neither Binance Stocks account eligibility nor read-only Stock API access is yet established. Do not equate crypto Spot with Stocks, bStocks or equity perpetuals.

Success function:
`Net P&L = realized + unrealized P&L - transaction fees - spread/slippage - funding/borrow/conversion costs - applicable taxes - model/API/cloud operating costs`.
Track trading P&L and total system P&L separately; an LLM-assisted process that earns $1 gross while spending $5 on tokens has negative business economics.

## 6. Narrow delivery roadmap (candidate; not authority to trade)

**Gate A — Market & account feasibility (zero orders):** Identify accessible instrument class, current maker/taker/platform fees, minimum trade notional, tick/lot limits, source and timezone, credentials scope/IP handling. Result: verified YES/NO, not an assumption.

**Gate B — Reproducible net-P&L engine:** Timestamped normalized candles/trades, fee/slippage model, deterministic benchmark, complete event log; baseline flat, buy&hold, simple rules; immutable configuration and no lookahead.

**Gate C — Falsifiable hypotheses:** Limit initial search to 1–2 pre-registered strategies. Evaluate walk-forward out-of-sample, regimes, turnover, cost sensitivity, drawdown, Monte Carlo/bootstrap uncertainty. Historical QuanTrade indicator failures remain linked rather than overwritten.

**Gate D — Paper/Shadow continuity:** Multiweek paper run spanning enough actual trades and differing regimes for a meaningful interpretation, plus network/restart/order-duplication/kill-switch injection. Require each session to recover previous experiment / unsettled orders instead of resubmitting.

**Gate E — Governed micro-live proposal:** Only after independent evidence and explicit new approval for a bounded market, symbol set, allocation, stop conditions, permissions, IP allowlist, and real-time monitoring. **Not approved by this record.**

**Stop / reject:** Negative costs-adjusted OOS, costs exceed plausible edge, unverified eligibility/data legality, stale bar or unconfirmed fill, authority ambiguity, unavailable stop, broken recovery, or unclear audit/provenance.

## 7. Deliverable priority

1. Produce a reliable **paper trading ledger and after-cost scorecard**, not another general AI-agent hierarchy.
2. Verify market/broker access without funds transfer or order placement.
3. Run one controlled strategy candidate against flat, buy&hold and matched risk benchmark.
4. Bind existing Holdings Mission continuity and audit only after the stand-alone research loop produces reproducible artifacts.

### Cross-Lab handoff

- QuanTrade owner: Alpha Lab / Quant research, paper ledger, market-specific rule/test data.
- Holdings Core owner (support only): Mission scheduling, Change of Watch, scoped memory retrieval, budget/permissions, audit, kill switch.
- LLMs interpret evidence. D0 computes indicators/position sizing/fees and adjudicates hard constraints; Risk veto is not bypassable.
- No Work/Task is marked implemented, verified or deployed by this study.

## 8. Verification and next revisit

- **Research artifact only**: source links and existing GitHub baseline compared; no software change, no executed backtest, no actual broker/API test, and no live trading from this record.
- Revisit after actual account fee/permission read-only evidence, a versioned paper P&L report, or a new independent source/creator implementation; compare against this record rather than starting research from chat memory.
