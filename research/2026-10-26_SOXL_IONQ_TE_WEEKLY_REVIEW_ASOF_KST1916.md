# QuanTrade weekly | IONQ / TE → cash → SOXL
**First observed in this review:** 2026-10-26 ~19:16 KST / 06:16 EDT. **Last fully completed US regular session:** Fri 2026-10-23 16:00 EDT. 2026-10-26 Monday premarket quotes explicitly EXCLUDED from all closing-return calculations.  
**Research authority:** NO_TRADE / RESEARCH_ONLY / PAPER_ONLY. No client position size, cost basis, P&L, budgets, or approvals in this public report.

## Incremental findings since 2026-10-19 weekly review

1. **The original “wait for IONQ/TE bounce then buy a cheaper SOXL” two-leg timing assumption did not jointly materialize.** By Oct 23 IONQ nearly flat vs Oct 16, TE -12.60%, SOXL -10.79%. A SOXL price dip appeared but **not** a verified SOXL uptrend entry. Waiting for a TE recovery would have failed to release cash. Cash was a viable benchmark, not necessarily an opportunity lost.
2. **Actual index secondary series newly located:** 2026-10-23 ICE/NYSE Semiconductor Index (vendor calls it ICE Semiconductor Index) 3,067.23, +0.67% day, 2026-10-22 3,046.89 (-6.87%), Oct 16 3,161.90. This is a *third-party publication*, NOT directly verified ICESEMIT licensed feed. The series is below computed 20-session SMA ~3,470.53 (-11.62%); site says above 200-session SMA. Official ICE ticker/version/price vs total-return variant, corporate-action methodology, rights, 200SMA reproduction remain DATA_QA_BLOCKED. SOXX and PHLX SOX are NOT interchangeable.
3. **AI credit deterioration now has company-level measurements**: Reuters 2026-10-22 reports Meta 5y CDS widened to ~114.79bp (+7.6bp) after capex guidance $135–145bn and Q3 free cash flow -$2.12bn; WSJ 10/23 reports Meta, Oracle and SpaceX bond spreads widened even as some equities stabilized. Credit conditions are MIXED / sector stress, not “fixed by bond rally.” 10y US Treasury yield Oct 23 close ~4.988% (Oct 16 5.098%; -11bp week), but Brent Oct23 $116.72. No independent cross-sectional credit model qualified for trade.
4. **Fundamentals offer counterevidence to broad chip-demand collapse**: Texas Instruments Q3 sales $6.06bn (+28% YoY) and Q4 guide $5.8–6.3bn; Lam Research fiscal Q1 sales $8.22bn (+55% YoY), but guidance failed to lift shares; demand can be strong while valuation and financing contract. Semiconductor index Oct23 +0.67% after Oct22 -6.87% is not a sustained reversal.
5. **TE positive operations / negative funding**: Oct22 Commerce waiver to import up to 1.725GW solar cells protects Dallas module operations while G2 2.1GW cell facility targets Q1 2027 first production. Oct21 SEC 8-K reports third $30m Evervolt payment chosen as 9,962,645 shares but issuance **deferred** under 4.99% ownership cap; earlier 2,246,377 deferred, combined 12,209,022 unissued deferred, NOT newly sold. Fourth $18m payment due Oct30. Waiver is NOT dilution cure.
6. **IONQ**: Oct 12 Elisity up to $1.3bn all-stock deal expected Q4, Oct14 $2bn offering remains valuation/dilution risk. Official Oct22 announcement schedules Q3 results Nov 5 after US close. No independently confirmed closing of Elisity in this review.
7. **Community #130/#131**: curated historic first/second-order sentiment has no new licensed, first_seen verified forward eligible samples in reviewed issue state; prediction incremental OOS alpha remains unproven. GitHub Actions collector workflow *configured* but remote successful production operation was not independently verified in this review.

## Verified US regular-session close series (USD; as of Oct 23)
Source: Stock Analysis daily historical OHLCV. SOXL alternative ChartExchange **header snapshot** $83.44 vs historical table / Stock Analysis $83.56 has a known provider/quote-definition discrepancy. All calculations here use the **explicit Stock Analysis daily historical close $83.56**, tagged PROVISIONAL until official venue methodology reconciled.

| date EDT | IONQ | TE | SOXL | third-party NYSE Semiconductor index |
|---|---:|---:|---:|---:|
| Oct 16 | 31.28 | 2.62 | 93.67 | 3161.90 |
| Oct 19 | 30.78 | 2.54 | 98.65 | 3217.80 |
| Oct 20 | 31.26 | 2.47 | 97.55 | 3206.79 |
| Oct 21 | 32.28 | 2.38 | 103.24 | 3271.65 |
| Oct 22 | 31.16 | 2.31 | 82.11 | 3046.89 |
| Oct 23 | 31.27 | 2.29 | 83.56 | 3067.23 |
| Oct16→23 return | -0.03% | -12.60% | -10.79% | -2.99% |

**Relative difference, percentage points**: SOXL minus IONQ = -10.76pp; SOXL minus TE = +1.81pp. **This is not a return on an actual executed rotation**. From Oct19 close to Oct23: IONQ +1.59%, TE -9.84%, SOXL -15.30%; “missed SOXL upside” was negative in this specific observed interval, not an eternal property.

**Computed close-only SMA20** from the 20 completed sessions 2026-09-28 through 2026-10-23, unadjusted Stock Analysis daily series and secondary index source (rounded):
- IONQ $37.5925; close $31.27 => -16.82% below SMA20
- TE $3.1860; close $2.29 => -28.12%
- SOXL $127.8455; close $83.56 => -34.64%
- Third-party ICE Semiconductor index 3470.532; 3067.23 => -11.62%.
SOXL SMA5 $93.022, 50-day third-party TipRanks $124.83, 200-day $123.13; below all. SOXL Oct22 -20.47% with 174.0m shares vs Oct23 +1.77% with 92.7m, **not** confirmation of bottom. Daily-reset leverage and path dependence matter; a -20.47% day needs +25.74% from the subsequent close to recover.

**RSI data quality issue:** Vendor RSI(14) as-of Oct23 diverges: SOXL AlgovestIQ 22.87 vs TipRanks 30.86, IONQ StockTi 23.8 vs tradmap 33.90; TE SwingTradeBot 22.48 vs Investing.com India 37.134. Provider lookback, smoothing, historical adjustment and timestamp are not harmonized. **Do not build entry rule on a picked vendor RSI number**. MACD generally negative, but differing calculations also need pinned reproducible series.

## Independent risk / decision alternatives

| candidate | evidence | action state |
|---|---|---|
| HOLD_IONQ | Oct23 $31.27, SMA20 $37.59, still equity issuance/Elisity risk, Nov5 earnings | WATCH / evaluate exit-on-relief vs hold independently |
| HOLD_TE | Oct23 $2.29, SMA20 $3.19, 5 consecutive down closes Oct19–23, $2.21 Oct23 intraday low, Oct30 Evervolt $18m payment | WATCH_HIGH_RISK; relief rally **not observed** |
| SELL_IONQ_TO_CASH | potential de-risking but no private mandate or validated exit signal | PAPER comparison only |
| SELL_TE_TO_CASH | persistent downside + deferred shares, waiver positive operations | PAPER comparison only |
| SELL_BOTH_TO_CASH | may avoid further correlated risk but realization of existing loss does not predict next return | PAPER comparison only |
| CASH_ONLY | explicit baseline; can wait for independent SOXL qualification | ALLOWED RESEARCH BENCHMARK |
| SOXL_SMALL_PAPER | third-party index under 20SMA, sector credit elevated, verified ICESEMIT direct licensed series missing, OOS strategy not passed | **RISK_VETO / NO_TRADE** |

Do not force cash handoff into SOXL. Settlement, broker buying-power policy, FX, tax, risk budget and live authority must all be validated privately before any real order.

## Retrospective, strictly illustrative after-cost ledger (NOT a historical strategy backtest)

**Artificial account** (unrelated to any real user's holdings): initial 10 IONQ shares + 100 TE shares; no initial cash. Hypothetical fixed instructions: after Oct19 close, sell both at Oct20 next-open reference, wait T+1 business day, buy **one** SOXL share at Oct21 next open, exit after 3 regular sessions at Oct23 close. This choice was made retrospectively, so **NO OOS/alpha inference**. Each fill has 0.10% adverse slippage **plus** 0.10% proportional fee, no minimum commission, no FX/tax, assumed tradable at reference open/close, no partial fills, no price impact. Weekend-only business day settlement mock, US holidays not fully modeled. Buying-power restriction forbids use of unsettled cash.

| date | action | reference | cash effect |
|---|---|---|---:|
| Oct20 open | SELL 10 IONQ | $30.28 | +$302.19470280 (pending) |
| Oct20 open | SELL 100 TE | $2.47 | +$246.50624700 (pending) |
| Oct21 pre-open assumed | T+1 settlement | — | $548.70094980 available |
| Oct21 open | BUY 1 SOXL | $102.86 | -$103.06582286 |
| Oct23 close | SELL 1 SOXL | $83.56 | +$83.39296356 pending until Mon Oct26 |
| Oct26 | settle proceeds | — | **final cash $529.02809050** |

**Comparators at Oct23:** CASH_ONLY after Oct20 sale and fees $548.70095; **HOLD_NO_SELL** marked to Oct23 close $541.70 (not liquidated, no sale fees); ROTATE_1_SOXL $529.02809. Thus the illustrative SOXL round-trip costs ~$19.67286 net vs cash-only and the switch underperforms hold by ~$12.67191. These numbers are **scenario mechanics only**; cannot generalize from one cherry-picked sequence. Weekend T+1 simulated as next weekday; holiday/DTCC processing/actual settlement and slippage remain limitations.

5 local unit checks pass for pending-cash rejection, next-weekday settlement, idempotency, insufficient cash, exact after-cost result. A working file is provided in this conversation; it is not a deployed backend, exchange API or validated trading engine.

## Required next steps / acceptance gates
1. Obtain permissioned official ICESEMIT **price/total return definition** and immutable 2021 index methodology transition; reconcile 10/23 ETF official close/NAV and 2026 corporate actions.
2. Freeze indicator formulas and source series; calculate RSI, MACD, ATR, vol, trend and relative strength from the *same* adjusted data as of each timestamp, no stale or conflicting vendor mixing.
3. On next US close, assess IONQ close > $32.28/$34.35 or lower low < $30.19, TE whether $2.21 low persists and whether $2.47/$2.62 can be recovered; these are **watch bands**, not trade triggers.
4. SOXL needs index higher-low and trend recovery, 20SMA direction, credit-risk normalization and separate Risk mandate; Oct23 +0.67% index rebound insufficient.
5. Check TE Oct30 payment filing, IONQ Nov5 earnings, Microsoft/Alphabet/Amazon AI capex, Fed Oct28 decision; date/time sources to be reverified.
6. Run a preregistered historical walk-forward 2-leg portfolio study with settlement, fees, FX, tax, matched-risk cash/hold comparisons and NO_TRADE baseline; no strategy promotion without after-cost OOS.

## Source registry (published event vs observation time)
- https://stockanalysis.com/stocks/ionq/history/ — historical daily OHLCV through Oct23; observed Oct26
- https://stockanalysis.com/stocks/te/history/ — historical daily OHLCV through Oct23; observed Oct26
- https://stockanalysis.com/etf/soxl/history/ — historical daily OHLCV through Oct23; observed Oct26
- https://stock-marketdata.com/ice-nyse-semiconductor-index — *secondary* ICE index daily series through Oct23, not directly licensed official; observed Oct26
- https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs — fund 3x daily objective, 2021 benchmark history; observed Oct26
- https://www.tipranks.com/etf/soxl/technical-analysis and https://www.algovestiq.com/etf/soxl/technicals — conflicting RSI, dates as noted
- https://www.reuters.com/business/metas-credit-risk-indicator-jumps-record-high-after-results-2026-10-22/ — Reuters Oct22 Meta CDS and capex
- https://www.wsj.com/livecoverage/stock-market-today-dow-sp-500-nasdaq-10-23-2026/card/tech-company-bonds-stay-under-pressure-even-as-stocks-stabilize-TMyeVOcU4MrrJAJVaxBE — WSJ Oct23 company bonds
- https://www.reuters.com/world/china/global-markets-global-markets-2026-10-23/ — Reuters Oct23 US close, Brent/yield
- https://www.portfolio-terminal.com/markets/10-year-treasury-yield — US 10y Oct23 close 4.988%; independent provider
- https://www.wsj.com/business/earnings/texas-instruments-posts-higher-profit-revenue-23a867a6 — TI results Oct22
- https://www.investors.com/news/technology/lam-research-lrcx-stock-fiscal-q1-2027-earnings/ — Lam results Oct21
- https://www.sec.gov/Archives/edgar/data/1992243/000121390026111378/ea0309217-8k_t1energy.htm — TE 8-K filed Oct21, event Oct15, issuance deferred
- https://energydigital.com/globenewswire/3386137 — TE original GlobeNewswire Oct22 waiver release
- https://www.nasdaq.com/press-release/ionq-acquire-elisity-accelerate-zero-trust-quantum-era-2026-10-12 — IonQ Oct12 acquisition
- https://investors.ionq.com/news/news-details/2026/IonQ-to-Report-Third-Quarter-2026-Financial-Results-on-November-5-2026/default.aspx — official Oct22 earnings calendar

**Status:** MATERIAL_WEEKLY_EVIDENCE_UPDATE / SECONDARY_ICESEMIT_FOUND / ETF_TREND_BEARISH / IONQ_FLAT_TE_WEAK / META_CREDIT_STRESS / PAPER_FIXTURE_PASSED_NOT_OOS / NO_TRADE.
