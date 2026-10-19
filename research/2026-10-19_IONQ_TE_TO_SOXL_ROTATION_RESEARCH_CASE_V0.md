# QuanTrade research case — IONQ / TE cash transition / SOXL entry (candidate)

**As-of:** 2026-10-19 18:10 KST; US October 19 regular session has not opened.  
**Authority:** PROPOSED, PAPER-ONLY; NO LIVE ORDER AUTHORITY.  
**Privacy:** Public document is an abstract security-rotation experiment. It does not report or infer client holdings, losses, purchase prices, share counts, investable money or specific mandates. Real holdings and client loss limits belong to PRIVATE Client Mandate records and should not be added to this public repository.

## Objective

Compare candidate alternatives under the same historical/forward information set:
- Keep two existing risk-on stocks (IONQ and TE), including possible recovery;
- Trim/risk-reduce one/both following a market rebound or loss of thesis and park available sale proceeds in cash;
- Enter a **capped** position in daily-reset 3x SOXL only if independently validated with simultaneous entry + exit plan;
- Keep cash / no-switch benchmark as a full first-class decision.

**It is not a guaranteed strategy to minimize realized loss**: a wait-for-break-even requirement can block exits and make the underlying purchase disappear, while rotation from risky stocks to 3x levered ETF may increase downside. Distinguish *already incurred mark-to-market loss* from *future expected marginal returns*. From -30%/-40% to breakeven requires approximately +42.9%/+66.7% respectively; historical cost basis must not decide future expected returns.

## Verified facts at latest complete US close, 2026-10-16

| Asset | Oct-16 close (USD) | Key facts and dated sources | Immediate implications |
|---|---:|---|---|
| IONQ | 31.28 | Oct-12 all-stock acquisition of Elisity up to $1.3bn, Oct-14 $2bn equity + prefunded warrants and longer-lived additional warrants; Oct-16 underwriting closing per SEC | Attractive cash resources and technology catalysts coexist with dilution/valuation risks; rally cannot be assumed to repair loss |
| TE | 2.62 | T1 Energy, US solar supply chain/factory, not a semiconductor holding; Sep-28 additional $50m notes due 2031; Oct-6 resale registration of 7,246,377 issued/issuable shares; Aug-12 Q2 revenue $250.1m but continued-op net loss $36.9m | High variance, financial and execution risk with equity supply overhang, no guaranteed beta alignment with SOXL |
| SOXL | 93.67 | Daily 3x **NYSE Semiconductor Index (ICESEMIT)** target; Oct-19 premarket rebound news is not final session | Independent qualification as trade candidate needed; never calculate SOXL as 3x SOXX or SOX over several days |

Price sources https://stockanalysis.com/stocks/ionq/history/ , https://stockanalysis.com/stocks/te/history/ ; filings https://www.sec.gov/Archives/edgar/data/1824920/000119312526424230/ionq-20261014.htm , https://www.sec.gov/Archives/edgar/data/1824920/000119312526419609/ionq-ex99_1.htm , https://www.sec.gov/Archives/edgar/data/1992243/000121390026104291/ea0306948-8k_t1energy.htm , https://www.sec.gov/Archives/edgar/data/1992243/000121390026107289/ea0307775-8k_t1energy.htm , https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs .

Latest *indicative* near-term daily closing-price landmarks, not validated resistance:
- IONQ: recent previous completed session closes $34.35 (Oct 15), $36.27 (Oct 12), $39.89 (Oct 9), Oct16 low $31.11.
- TE: $2.93 (Oct15), $3.21 (Oct12), $3.73 (Oct7), Oct16 low $2.58.
- Technical snapshots Oct16, source stocksetups.com: IONQ RSI~32 and TE RSI~26, both below 20/50/200-day SMA. RSI under 30 does not guarantee recovery; data provider methods may differ.
- SOXL historic watch band Oct16 $93.44-103.93 and October prior closes $107-111, long trend moving averages are far overhead; Oct19 session remains unconfirmed at this as-of.

## User-facing decision ladder — no actual execution

1. **SOURCE SECURITY REVIEW**: Client private mandate defines what funds are at risk, needed cash, time horizon, maximum portfolio loss, venue, allowable assets, tax/FX, existing exact shares and average cost; latest reconciled broker snapshot. Public artifacts never contain values.
2. **SELL RESEARCH**: For each risky stock, maintain independent `EXIT_ON_RELIEF_RALLY`, `EXIT_ON_THESIS_BREAK`, and `KEEP/HOLD` candidates. Price reclaim zones are *research triggers*, not confirmed exit orders. Evaluate gap/volume/relative strength versus QQQ and direct issuance/supply risks. Compare expected remaining returns with SOXL/cash, after costs, without recoup-anchoring.
3. **SETTLEMENT CASH**: Sale cash must be *actually available* before independent SOXL proposal. Check domestic broker's unsettled-cash use, US T+1, FX & fees per account, no assumed immediate leverage/purchasing power.
4. **SOXL QUALIFICATION**: Only SOXL's **actual NYSE Semiconductor Index** price trend/volatility and independently approved Risk permit `PAPER_CANDIDATE`. The macro/credit, AI capex, earnings and sentiment channels may veto or downgrade confidence; social data are not yet predictive-eligible.
5. **JOINT OPTIMIZER**: At each decision time compare `HOLD_IONQ_TE`, `SELL_ONE_TO_CASH`, `SELL_BOTH_TO_CASH`, `SOXL_ENTRY_AFTER_RISK_APPROVAL`, `CASH`; proposed actual tradable size and exit plan only after Client private mandate + validated after-cost estimates.
6. **EXIT AND REVIEW**: For each candidate enter immutable stop/thesis-invalidation, trailing or staged profit-taking, timed maximum holding, tail-gap stress, and manual explicit authority for any live trade. No waiting forever for cost basis.

## Key timing conflict to quantify

Both sides could rally concurrently. A "wait for IONQ/TE to fully recover then buy an SOXL dip" condition can fail if SOXL recovers first. Conversely, liquidating a loser to chase an 8%-up SOXL premarket print can aggravate losses. Retain cash as an allowed terminal state. Backtest 2-leg joint opportunity cost (hold vs rotate vs cash) under matched market dates and the full corporate-action-adjusted history and verified first-observed timestamps. No future price access, no hindsight selection of swing peaks, and independent data as-of recorded.

## Proposed observable state transitions

`WATCH_IONQ`, `WATCH_TE`, `HOLD`, `SELL_CANDIDATE`, `CASH_PENDING`, `CASH_AVAILABLE`, `WATCH_SOXL`, `SOXL_PAPER_CANDIDATE`, `RISK_VETO`, `NO_TRADE`, `EXIT_PLAN_PREPARED`, `PAPER_CLOSED`.

- Source event triggers: dilution/issuance, financial guidance, major contract, closing prices, trend/volatility shifts, relative returns.
- Do not confuse the date a forum/news story is discovered with its publication date.
- Incomplete data => `UNKNOWN` / no order. 
- The monitoring strategy is *proposed*, not yet a deployed tick-level or broker-integrated engine.

## Specific evaluation and acceptance tests

- **E1** IONQ, TE independent rebound thresholds versus sell-now and fixed wait windows, including failed bounce and stock gaps.
- **E2** 2-leg handoff: if one sale occurs and SOXL is no longer attractive, hold cash not force buy; check simulated settlement restrictions and pricing.
- **E3** SOXL entry after fully observed trend confirmation vs buying immediate 8%-up premarket vs staying cash; next executable bar, 1/3/5/10/20 NYSE sessions, costs and path-dependent ETF behavior.
- **E4** Joint portfolio tail risk and per-asset return attribution versus no-switch; size conditional on maximum private loss rather than claimed 'optimal' price.
- **E5** Corporate actions/fund splits and additional stock issuance per ticker; durable audit log; two identifiers for risk and committee.
- **E6** Two positive and two negative scenarios including both rise, both fall, IONQ/TE lag with SOXL rally, and SOXL drop after cash switch.

**Current verdict:** THREE WATCHLIST INSTRUMENTS / NO VALIDATED ORDER TIMING OR TARGET ALLOCATION / RESEARCH ONLY. This document is a test specification, not completed testing and not a trading instruction.

Related https://github.com/ringoincidents/quantrade/issues/126 and https://github.com/ringoincidents/quantrade/issues/129 .
