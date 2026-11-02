# QuanTrade weekly review — IONQ / TE → CASH → SOXL

**Observed for this report:** 2026-11-02 19:37 KST (2026-11-02 05:37 EST, before US regular open). **Last completed US regular session:** Fri 2026-10-30 16:00 **EDT**. US DST ended Nov 1. Prices from Nov 2 premarket, where mentioned, are not regular-session closes.  
**Authority:** RESEARCH_ONLY / PAPER_ONLY / NO_TRADE / NO_LIVE_ORDER_AUTHORITY. No client holdings, loss, capital, position count, or private mandate are stored here.
**Scope:** Delta vs [Oct 26 review](2026-10-26_SOXL_IONQ_TE_WEEKLY_REVIEW_ASOF_KST1916.md), [rotation spec](2026-10-19_IONQ_TE_TO_SOXL_ROTATION_RESEARCH_CASE_V0.md), issues [#129](https://github.com/ringoincidents/quantrade/issues/129), [#126](https://github.com/ringoincidents/quantrade/issues/126), [#130](https://github.com/ringoincidents/quantrade/issues/130), [#131](https://github.com/ringoincidents/quantrade/issues/131). Existing #129 event logs already cover Oct30 final closes, TE Oct30 13.44m-share resale registration, 1.58GW contracts, Nov1 Korean exports and Nov2 early premarket. Do not re-count these as fresh independent events.

## 1. Newly aggregated weekly comparison

All values USD **10/23 and 10/30 completed regular-session closes**, StockAnalysis dated OHLC history. Independent venue-level trade audit / corporate-action adjustment / redistribution rights not completed.

| Asset | 2026-10-23 | 2026-10-30 | Week return | 10/16→10/30 | 20-close SMA (Oct5–30) | 5-close SMA | 10/30 vs SMA20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| IONQ | 31.27 | **30.04** | **-3.93%** | -3.96% | 34.482 | 31.580 | -12.88% |
| TE | 2.29 | **2.70** | **+17.90%** | +3.05% | 2.882 | 2.554 | -6.32% |
| SOXL | 83.56 | **77.05** | **-7.79%** | -17.74% | 114.0365 | 95.674 | -32.43% |

Sources: https://stockanalysis.com/stocks/ionq/history/ , https://stockanalysis.com/stocks/te/history/ , https://stockanalysis.com/etf/soxl/history/ . SOXL 10/30 close $77.05; sponsor NAV $77.06 per #129 prior crosscheck, sponsor page may be stale when crawled.

**Additional technical diagnostic:** using exactly 14 completed *close-to-close differences*, simple average-gain/loss RSI(14) is IONQ **34.18**, TE **37.56**, SOXL **29.15**. **Not Wilder's RSI; not directly comparable to vendor RSI**, and only 20 sessions are included. Avoid cherry-picking indicator definitions. SOXL Oct30 single-day **-24.75%**, closing after a $70.23–84.19 regular-session vendor OHLC range (raw consolidated ticks not audited). 10/26–30 close-to-close daily volatility annualized over only five returns: IONQ ~74%, TE ~158%, SOXL ~235%; small-window estimates are highly unstable and NOT calibrated risk limits.

**Critical changed observation:** TE finally had a genuine close-to-close relief rally (+17.90% week) while IONQ lost 3.93% and SOXL lost 7.79%. **TE−SOXL = +25.70 percentage points**, IONQ−SOXL = +3.86pp in this specific Oct23→30 close comparison. This is *ex-post relative returns*, not a fillable timing edge. Oct30 TE -5.59% shows its rally was not monotonic. All three below 20d averages; TE close above its 5d average, SOXL below 5d average. Therefore TE bounce observed, **TE sustained trend recovery not established**, IONQ bounce unconfirmed, SOXL entry unqualified.

## 2. Exact SOXL index and cross-checks

Official sponsor https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs explicitly specifies **NYSE Semiconductor Index (ICESEMIT)**, modified float-adjusted cap-weighted US-listed 30 names, **+300% of *daily* index returns before fees**, NOT 3x cumulative multi-day, NOT SOXX or PHLX SOX.

- Oct30 vendor **NYSE SEMICONDUCTOR (TR)** variant: **3,022.88, -8.23%** versus 3,294.00 prior day. https://www.finanzen100.de/index/ice-semiconductor-tr_H1256474610_330603302/ . This is a **total-return-labeled secondary index variant**. It provides directional independent corroboration of chip crash but **NOT verified ICESEMIT price-return series** or a licensed, same-methodology 20/50/200-day history. Do not splice Oct23 price-index 3,067.23 with Oct30 TR 3,022.88 to claim index return or moving average.
- Independent **PHLX SOX** Oct30 -7.20% to 10,688.80 (https://finance.yahoo.com/quote/%5ESOX/history/) and SOXX Oct30 -8.24% to $471.51 (https://stockanalysis.com/etf/soxx/history/) confirm broad weakness but are **distinct benchmarks**, not SOXL target.
- **ICESEMIT data QA remains BLOCKED:** exact price vs total-return series, licensing, adjusted historical methodology and continuity, especially 2021 index change. A formal SOXL entry condition cannot be promoted on substitutes.

## 3. Company events and macro

**IONQ**: Oct14 $2bn equity / warrants funding and Oct12 Elisity all-stock deal up to $1.3bn remain dilution/valuation risks. Oct30 13G institutional holding report is not new issuance. No confirmed Elisity close or extra issuance in this review. **Nov5 after close Q3 results** official IR: https://investors.ionq.com/news/news-details/2026/IonQ-to-Report-Third-Quarter-2026-Financial-Results-on-November-5-2026/default.aspx . A single Oct27 +7.12% day was followed by Oct28–30 declines; no stable higher lows proven.

**TE**: Oct30 **1.58GW+ Avantus-related module offtake** for 2027–28, >4GW 2027 capacity contracted, positive for G1_Dallas, G2_Austin planned first 2.1GW cell phase Q1 2027; contracts do not prove gross margin, collections or financing. Oct30 SEC 8-K + 424B7 register **13,440,860 potentially convertible shares** relating to **previously issued Sep30 $50m 4.75% 2031 convertible notes**. **Registration ≠ actual conversion ≠ actual issuance ≠ resale**; issuer receives no proceeds from holders' resale. Primary filing: https://www.sec.gov/Archives/edgar/data/1992243/000121390026114466/ea0310173-8k_t1energy.htm . Existing Evervolt IP consideration $18m installment **due Oct30**; completion and cash vs share settlement still **not verified**. Do not confuse Evervolt and Discovery Capital registrations. TE upside and funding risk are distinct.

**AI/semiconductor**: Reuters Oct30 reports Intel -28.6%, Nvidia -4.2%, AMD -10.9%, Nasdaq -2.86%, PHLX SOX -7.2%, following Intel weak Q4 outlook/negative FCF and Amazon AI investment cash-burn concern. https://www.reuters.com/business/nasdaq-futures-tumble-amazon-intel-results-deepen-ai-spending-woes-2026-10-30/ . Intel CDS reportedly +17.5bp to 124.75bp, *issuer-specific*, not market-wide credit OAS. https://www.reuters.com/business/intel-warning-sparks-chip-rout-pc-weakness-clouds-turnaround-2026-10-30/ .
Oct28 Fed held 3.75–4.00% 10–2; dissenters favored hike, so a Fed hold does not mean financing conditions are loose. https://www.atlantafed.org/news-and-events/2026/10/28/fomc-statement . Reuters Oct30 US10y yield **4.931%** (down ~5.8bp that day) while Brent **$117.63**; Treasury rally reflects risk aversion, not proven credit repair. https://www.reuters.com/legal/transactional/global-markets-global-markets-2026-10-30/ .
**Counterevidence:** Korea official Oct exports and memory prices, existing #129 Nov1 entry; and Nov2 premarket Nasdaq100 futures +~0.8% (FT Nov2), **not yet a completed US session**. https://www.ft.com/content/d7fe99f8-d292-4cb5-a8fd-45be0f8cc2b3 . Sector demand and valuation/financing stress can coexist.

## 4. New independent paper fixture (ex-post demonstration, NOT alpha)

Source code: [rotation_fixture_20261102.py](scripts/rotation_fixture_20261102.py). **Synthetic initial positions** 100 IONQ + 100 TE, no actual account data. Fixed, ex-post chosen prices: sell Oct26 **open** IONQ $30.94, TE $2.24; assume T+1 settlement usable by Oct27 **open** SOXL $95.04; sell purchased SOXL Oct30 **close** $77.05. For each order 10bp adverse slippage plus 10bp fee. Integer SOXL shares only, unused funds remain cash. No taxes, FX, market impact, overnight fills, broker-specific cash permissions or official calendar integration. Seven scenario outputs:

| candidate | 10/30 simulated ending equity (USD) |
|---|---:|
| HOLD both (100 shares each) | 3,274.00 |
| Sell IONQ, hold TE, cash | 3,357.82 |
| Sell TE, hold IONQ, cash | 3,227.55 |
| Sell both, hold cash | **3,311.37** |
| Sell IONQ → SOXL, keep TE | 2,771.12 |
| Sell TE → SOXL, keep IONQ | 3,190.88 |
| Sell both → SOXL | **2,688.00** |

**Hindsight-only finding:** Sell-both → SOXL loses **$623.37** relative to sell-both cash in this synthetic period, and **$586.00** versus holding the synthetic two-stock portfolio. This does **not** imply Oct26 cash was ex ante optimal, that the user actually held 100 shares, or that real trades were possible at these fills. Local script tests: seven paths, cash >=0, no unfunded rotation, accounting costs, independent cash benchmark PASS. Not a walk-forward backtest; no robust profit claim. No automatic real order.

## 5. Decision and engineering gates

- **IONQ:** independent WATCH / earnings and dilution risk; a bounce above SMA5/SMA20 is research trigger, not mandatory breakeven sale.
- **TE:** RELIEF_RALLY_OBSERVED but financing/issuance risks unresolved; watch whether above 5-day mean and sustained volume/low structure; may sell independently, not forced paired liquidation.
- **SOXL:** sharp decline plus Nov2 early premarket bounce (already logged #129) does not equal uptrend; 10/30 close 32.43% below its own 20-close SMA. **PAPER_CANDIDATE_BLOCKED / NO_TRADE**.
- **CASH:** fully valid allocation and default baseline when signal or independent Risk absent.
- **#126:** seven-case deterministic fixture is *not* the full immutable order-event paper ledger. Still needs broker calendar/settlement, real fills/partial fills, slippage stress, adjusted data, source licensing, replay/idempotency and OOS/holdout.
- **#130/#131:** no new independently verified first-seen forward-eligible community population or significant incremental predictive alpha. Keep **NO_SOCIAL_SIGNAL**; do not turn Threads risk thresholds into position sizing without precise OAS and factor definition.

**Next review:** Nov2 **23:30 KST** US regular open (DST ended); only after Nov2 **Nov3 06:00 KST** regular close can a new US session be finalized. IonQ Q3 Nov5 after US close. TE final Evervolt payment completion/terms must be confirmed from actual SEC 8-K or primary company disclosure. All research proposals remain non-executable.

**Final verdict:** `TE_RELIEF_RALLY_CONFIRMED_WEEKLY / IONQ_WEAK / SOXL_STRONG_DOWNSIDE / INDEX_VARIANT_QA_BLOCKED / PAPER_ONLY / NO_TRADE`.
