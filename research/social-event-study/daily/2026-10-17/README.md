# QuanTrade | DCInside SOXL fixed-query snapshot 2026-10-17

**Status:** exploratory / NONREPRESENTATIVE / NOT A TRADE SIGNAL. Run time is written in `run_asof.txt` (UTC). Reviewed by ChatGPT on 2026-10-17. Public URLs only, with no usernames/raw text.

## Observed result

Nine gallery × synonym queries attempted (stockus, krstock, tenbagger × SOXL, 속슬, 속쓸), using external web search constrained to the 2026-10-17 date. **Zero confirmed 2026-10-17 posts**. This is **not evidence there were zero posts**, and search results cannot establish the number or proportion of bearish/bullish posts. Some results ignored the date qualifier. Search coverage was unquantified, *not complete or randomized*.

Five additional historical individual-source examples were independently observed in indexed results: 4 stockus, 1 krstock. All five are **retrospective discovery** with observation timestamp in October 2026; therefore **none** are eligible for a trading/predictive backtest on their historical publication day. Distinguish this from the previously curated 20 sources stored in `research/social-event-study/2026-10-17/dcinside_soxl_curated_sources_v0.csv`.

10/17 Saturday KST is outside US regular equity trading. Last available US regular-session close was 10/16 ET. Any stock price provided must retain original source and adjusted/unadjusted basis.

## What the code does

- `search_attempts_20261017.csv`: records **attempts**, not full search-engine result counts. Missing results are a source-coverage limitation.
- `curated_observations_20261017.csv`: individual retrospectively retrieved historical discussion source pointers and stance estimates. Source labels are analyst interpretations, not independent double-coded annotations.
- `dc_snapshot.py`: validates precisely one record per fixed search pair; refuses to label search-engine results exhaustive; rejects unknown/naive/future timestamps, duplicate posts, and retrospective data marked prospectively tradable. Emits a JSON snapshot with `population_sentiment: UNKNOWN` when the denominator is unreliable.
- `test_dc_snapshot.py`: 8 regression tests. `snapshot_20261017.json`: script-generated result.

Run:
```
cd research/social-event-study/2026-10-17/dcinside-daily
python -m unittest -v test_dc_snapshot.py
python dc_snapshot.py --attempts search_attempts_20261017.csv --observations curated_observations_20261017.csv --asof "$(cat run_asof.txt)" --output snapshot_20261017.json
```

## Next sample schedule (future, subject to user permissions/platform conditions)

- One fixed **prospective** daily observation cutoff, preferably a consistent 19:00 KST time. Query the same three gallery IDs and all aliases. Keep other synonyms in a separately versioned search configuration so the sampling universe does not silently drift.
- Preserve query attempts even when failed, timing, observed number of matches if count can be validated, exact source IDs/URLs, `published_at`, `first_seen_at`, query engine and basis. Source-verified total population is needed to estimate an unbiased sentiment proportion.
- Stratify gallery and day type (normal, selloff, rebound), random-sample eligible results with an auditable seed only when the complete result universe is legitimately accessible; never infer all-community post counts from a web search engine.
- Respect site terms, privacy and deleted-post policies; no unlicensed bulk crawler; avoid content reproduction/user IDs.
- For price alignment: use NYSE Semiconductor Index as **SOXL exact underlying**; SOX, SOXX, QQQ for control only; offset KST->US session with market holidays and DST. If the post was first found after an event, it cannot be used to predict that event.
- Train news + price baseline before trying social features; score one-day and five-day held-out forward returns with Brier/log loss, calibration, incremental performance, worst drawdown and after-fee sim. Use reverse-lag price->sentiment test. No live orders.

## Source URLs newly observed in this pass
- https://gall.dcinside.com/mgallery/board/view/?id=stockus&no=17891785 (Oct 2; title only)
- https://gall.dcinside.com/mgallery/board/view/?id=stockus&no=17489017 (Aug 19; decline/frustration)
- https://gall.dcinside.com/mgallery/board/view/?id=stockus&no=16939427 (Jul 18; optimistic)
- https://gall.dcinside.com/mgallery/board/view/?id=stockus&no=15521490 (May 5; FOMO buy)
- https://gall.dcinside.com/mgallery/board/view/?id=krstock&no=1864906 (Jun 5; ambiguous sarcasm)

## Interpretation
We can audit a **repeatable query process**, but we do NOT yet have a complete, fixed-probability, legally licensed forum sample, reliable denominator, or prospective labels to make statistical or investment claims. An apparent 0 same-day result means *not found or not indexed by our search*, never *the community was silent*. Missing data is a legitimate experimental outcome.