# QT-SOCIAL-AUDIT-V3 — 과거 커뮤니티 백테스트 편향 감사 및 전향 시세 게이트

**Recorded:** 2026-10-17 KST. **Result:** NOT VALIDATED / NO TRADABLE ALPHA / NO ORDER AUTHORIZATION.

## Findings from reproducible local run

Source: prior curated 68 statements (35 thread-day-layer groups) from 2023–2026 and 2022 qualitative-only; partially available 86 daily SOXL closes. Original data and scripts: [two-track report](../../backtests/2026-10-17/TWO_TRACK_HISTORICAL_FORWARD_REPORT.md), [outcomes](../../backtests/2026-10-17/extended_thread_day_results.csv).

The same 1-session SOXL close change can appear multiple times because independent posts from the SAME DATE share a market outcome. For directional L1 opinions, **15 thread/day groups = only 13 different publication dates**. Under daily aggregation and date-consensus voting, 1-session sign correct **4/13**, compared to prior uncollapsed **5/15**. On those same selected dates, *always-bullish* direction was correct **7/13**, *always-bearish* **5/13** (one return exactly flat). The selected posts do not prove usefulness above a trivial baseline.

For 2nd-order opinions, the apparently strong **4/4** next-session sign match is only **2/4** if the market must move **at least 1%** in the anticipated direction. Importantly, just **two** claims are meaningfully forward-looking (2026-07-30 liquidation/exhaustion conjecture and 2026-10-02 herd warning); the other two are **post-hoc forecaster reputation** and an **open-ended skeptical question**. The strict two had 1-session sign **2/2**, but ≥1% direction move **1/2**.

Four L2 signals have first-later-session close anchors 2026-07-28, 2026-07-31, 2026-10-05, 2026-10-12. Due to overlapping five-session future windows, they constitute **just two** broad price-event clusters: July 28/31 and October 5/12. Not enough independent events for significance, generalization, or an executable model.

The only matched dates with both L1 and L2 samples are **2026-07-30 and 2026-10-02**. On July 30 bullish L1 and L2 agree (no incremental L2 evidence); on October 2 they disagree but subsequent 1-session change is only -0.006%, much smaller than transaction costs. All prices here start from a **hypothetical future regular-session close**, not tradeable as-of orders. Sampling/posting timestamps/first observed historical timestamps are insufficient. Claims were manually chosen after historical prices existed.

## Diagnostic table

| Window | L1: thread/day signed hits | L1: date-collapsed signed hits | L2: loose signed hits | L2: loose >=1% hits | L2: two strict future forecasts >=1% hits |
|---|---:|---:|---:|---:|---:|
| +1 session | 5/15 | 4/13 | 4/4 | 2/4 | 1/2 |
| +3 sessions | 6/14 | 5/12 | 3/4 | 3/4 | 2/2 |
| +5 sessions | 7/14 | 6/12 | 2/3 | 2/3 | 2/2 |

Selected data, overlapping events, no as-of first-seen, no official ICESEMIT, no actual broker fills: **No p-values, causal inference, trading-profit statements or backtest signal claimed**.

## Forward scoring safeguard

Extended a strictly *paper-only* next-open-to-close scoring check with `forward_maturity.py` (runnable ZIP provided in conversation): select first official NYSE session whose open is >15 min after the fixed signal decision time; score at h=1/3/5 only when the actual target session has closed and the verified market data were already first-observed before evaluation. Reject missing intermediate sessions, false exchange clocks (including DST), duplicated bars, unverified corporate action adjustments, late discoveries and frozen-feature timestamps too late. This is **idealized paper change**, not executable return.

Local reproducibility audit: **20/20 focused tests passed** (10 historical bias audit + 10 prospective calendar/price maturity tests), in addition to 17 previously recorded two-track tests.

Status of actual qualified forward social observations remains **zero**. The previously saved Stocktwits sentiment score is an *unsynchronized rolling public display*, not a population-weighted post corpus nor a trading signal. No authorized full-feed platform collector is connected.

## Follow-up gates

1. Authorized consistent sampling of Reddit/Stocktwits/DC historical and forward data with complete frame/selection denominator, precise published and first-seen timestamp, locked/blind labels; no unauthorized bulk scraping.
2. Price/news baseline and same-session paired comparison, all sampled dates including null/contradictory evidence, independent event clusters and honest holdout.
3. Official NYSE Semiconductor Index data for SOXL underlier (SOXX not equivalent), SOXL tradeable prices with splits/distributions, spreads, fees, slippage, gaps.
4. Compare models price-only, +news, +L1, +L2/L3 on 1/3/5 outcomes as future data *actually mature*, then independently review before any promotion.

Related [Issues #130](https://github.com/ringoincidents/quantrade/issues/130) / [#131](https://github.com/ringoincidents/quantrade/issues/131). Reject unproven "inverse sentiment always works" folklore until all gates pass.
