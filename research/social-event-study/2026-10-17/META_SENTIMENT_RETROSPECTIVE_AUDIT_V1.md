# QuanTrade — 2026 SOXL Meta-Sentiment Retrospective Claim Audit v0.1

**As-of 2026-10-17** | **RETROSPECTIVE, PURPOSE-SELECTED, NOT AN IMPLEMENTABLE TRADING BACKTEST**

## Question
Do comments that interpret other retail investors' opinions (e.g. "everyone is buying, so this is a top") align with *later* SOXL price direction more consistently than first-order predictions? This report only demonstrates how to measure that question, NOT whether this strategy is profitable.

## Source material
- [29 manually selected Reddit interpretations and opinions](https://github.com/ringoincidents/quantrade/blob/main/research/social-event-study/2026-10-17/manual_samples_v0.csv) — only dates known, not timestamps, no historical first_seen.
- [Meta-sentiment source library](https://github.com/ringoincidents/quantrade/blob/main/research/social-event-study/2026-10-17/meta_sentiment_cases_v0.csv) — 14 selected old posts, most unscorable.
- [20 DCInside cases](https://github.com/ringoincidents/quantrade/blob/main/research/social-event-study/2026-10-17/dcinside_soxl_curated_sources_v0.csv) — post timestamps known but first_seen during the past NOT known.
- [44 selected SOXL closes](https://github.com/ringoincidents/quantrade/blob/main/research/social-event-study/2026-10-17/soxl_daily_2026_selected.csv), priced by [ChartExchange](https://chartexchange.com/symbol/nyse-soxl/historical/), July–October 2026, with a significant Aug–Sep gap. Not adjusted for distributions in this input.
- [Reddit: r/SOXL July 27 forecaster reputation correction](https://www.reddit.com/r/soxl/comments/1v828iu/its_time_to_admit_it_flaky_was_right/)
- [Reddit: July 30 belief that Korean investors finished liquidating](https://www.reddit.com/r/soxl/comments/1vay6w3/good_thing_i_held_a_bit_longer/)
- [Reddit: October 2 after-$160 all-in post and critique](https://www.reddit.com/r/soxl/comments/1wvx45p/just_went_all_in/)
- [DCInside: October 9 suspicion the bounce is a trap](https://gall.dcinside.com/mgallery/board/view/?id=stockus&no=17941583)

## Reproducible method
`python backtest_retro.py --prices path/to/soxl_daily_2026_selected.csv --reddit path/to/manual_samples_v0.csv --claims handcoded_claims.csv --out .`

Run tests: `python -m unittest -v test_backtest_retro.py`

For **date-only** claims, the earliest *descriptively assessed* reference price is **the close of the first NYSE session strictly after its published US date**, then returns +1/+3/+5 whole trading sessions. This deliberately avoids asserting a same-day tradable close. **Even this anchor is not a validated entry** because the posting and first-observed times were not archived prospectively. Holidays are determined from `exchange_calendars` XNYS, and data gaps cannot be crossed. Prices are unadjusted source closes; there are no executable fills, taxes, fees, currency spreads or ability to short assumed.

A thread may contain multiple comments that are not independent. Consolidation rule: group by `platform × thread × published ET date × discourse layer`; direction from majority of coded non-neutral comments, ties or entirely neutral => no directional call. This is one arbitrary rule, not a validated classifier, and is intentionally **not fitted** to price data. There are only ~3 broad market episodes, not 24 independent experiments.

## Actual pilot results

- Initial claims: **37**, including 29 previously hand-selected Reddit opinions plus 8 added source-linked claims (7 unique source threads, with original buying vs reply-level meta in the same thread).
- Collapsed platform/thread/date/layer units: **24** (not independent market events).
- SOXL close observations in supplied file: **44**.
- Eligible historical forward-replay observations with known true as-of first_seen: **0**.

| Research-labelled category | +1 session correct | +3 sessions correct | +5 sessions correct |
|---|---:|---:|---:|
| First-order direct opinions | 5 / 11 (45.5%) | 6 / 10 (60.0%) | 6 / 10 (60.0%) |
| Second-order *loosely labelled* | **4 / 4 (100%)** | 3 / 4 (75.0%) | 2 / 3 (66.7%) |

The bold result is **not a success rate**; it is a descriptive coincidence conditioned on hand-selection, uncertain labels and 3 episodes. In the +1 meta signals **two correct signs had absolute returns <1%** (-0.0061%, -0.6464%), meaning economically tiny moves, not robust alpha.

### Case-level meta layer (delayed anchor price)

| Source date / source case | Coded sign | Anchor close | +1 day | +3 days | +5 days |
|---|---|---:|---:|---:|---:|
| Jul 27, r/SOXL reputation post | bearish *implied*, hindsight interpretation | Jul 28 $109.54 | -16.02% | **+4.73%** | **+27.72%** |
| Jul 30, r/SOXL liquidation exhaustion comment | bullish explicit conditional interpretation | Jul 31 $114.72 | +1.73% | +15.12% | +22.25% |
| Oct 02, r/SOXL critique of after-rally all-in | bearish explicit | Oct 05 $164.27 | **-0.006%** | -13.24% | -21.84% |
| Oct 09, DC stockus skeptical *question* | bearish *implied*, question not trade | Oct 12 $128.40 | **-0.65%** | -16.39% | unavailable |

**Quality correction:** Jul 27 is *hindsight reputation revision*, not a clean future forecast. Oct 09 is a *question*, not a documented sell call. Restricting to two explicit forward-looking second-order claims leaves **2 observations**: +1 return direction 2/2 but only 1/2 with >1% margin; +3 and +5 direction 2/2. These are 2 selected anecdotes, not testable evidence for an edge.

**Timing sensitivity:** If one (incorrectly) assumes each post was visible before that day's market close and compares that close to next close, the four second-order post-day directions align on only **2 of 4 days** (Jul27 correct; Jul30 0% = no hit; Oct02 wrong; Oct09 correct), instead of 4/4. Neither timing assumption is a verified executable strategy; the large difference demonstrates time-alignment risk.

**Baseline sensitivity:** On the 4 delayed-anchor +1 sessions, an unconditional bearish forecast matched 3/4 signs; the selected meta signs matched 4/4. With a required **>1 percentage point** favorable movement, the 4/4 drops to **2/4**. Explicit 2-signal subset => only 1/2 >1%. A single anecdote can change the statistic dramatically.

### Required next phase before asserting value

1. Source-licensed full 2023–2026 sample of original posts, replies and rolling scores, with **published_at_utc**, **first_seen_at_utc**, **edited_at_utc**, **score_observed_at_utc**, rights and deduplicated parent ID.
2. Pre-register sampling independently of outcome: all eligible SOXL posts within allowed feeds; randomly sample for two-blind-annotator stance/meta/irony classification. Train and test on chronology separated; no event selection based on observed wins.
3. Obtain adjusted SOXL and **the exact SOXL underlier NYSE Semiconductor Index (ICESEMIT)**. SOXX/SOX are proxy controls, not that underlier. Use order-feasible next open + spread/slippage; long-only versus cash; benchmark against past price+news+volatility and cheap negative-control fake signals.
4. Signal comparisons: direct sentiment, generic sentiment volume, meta-sentiment categories, inverse-meta and placebo, and **market return -> next message** reverse direction. Event-cluster bootstrap for independent events with multiple-testing correction. Test alternative trade horizons and 1–3% minimum economic move sensitivity.
5. Report negative and inconclusive results in append-only records. Never treat a model coding test or a few hindsight hits as an approved SOXL trade.