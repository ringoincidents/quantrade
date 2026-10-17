# QT-RESEARCH-003 — News / Forum Sentiment vs Semiconductor Returns (SOXL)

**Date:** 2026-10-17 KST. **Status:** FEASIBILITY + ANNOTATION-QUALITY PILOT; FORECAST VALUE UNKNOWN / NO LIVE ORDER AUTHORITY.
**Links:** [SOXL strategy](./2026-10-17_SOXL_YEAR_END_REVERSAL_RESEARCH_V0.md) · [2026 semiconductor event inventory](./2026-10-17_SEMICONDUCTOR_2026_EVENT_CAUSAL_MAP_V0.md) · [SOXL thesis Issue 129](https://github.com/ringoincidents/quantrade/issues/129)

## Research question and falsifiable hypotheses

- S0 / RESPONSE (null candidate): past price moves predict *subsequent social chatter*.
- S1 / FORWARD: premarket changes in bullish/bearish **investment direction** predict the following *open-to-close* return after past returns, risk/vol and news are controlled.
- S2 / VOLATILITY: unusual participation or disagreement predicts future realized volatility or volume, regardless of return direction.
- S3 / INTERACTION: negative financing/rate news + capitulation/social pessimism + improving underlying index price/relative strength jointly help distinguish rebounds from false bottoms.
- S4 / CONTRARIAN: after severe falls, extremely optimistic retail chatter may be a risky dip-buying indicator rather than a bullish leading signal.
- S5 / INCREMENTAL: information from Reddit / Stocktwits / Korean boards must beat news+prices-only forecast on an unopened period (after costs). Anything less is REJECT or INCONCLUSIVE.

**None of S1–S5 has been validated for SOXL as of date.**

## Scholarly context (support and contradictions)

1. Antweiler & Frank (2004), *Is All That Talk Just Noise? The Information Content of Internet Stock Message Boards*, J Finance. 1.5m+ posts: predict volatility; return effect statistically detectable but economically small. https://doi.org/10.1111/j.1540-6261.2004.00662.x
2. Tetlock (2007), *Giving Content to Investor Sentiment: The Role of Media in the Stock Market*, J Finance: news pessimism relates to price pressure/reversion and volume. https://doi.org/10.1111/j.1540-6261.2007.01232.x
3. Chen et al. (2014), *Wisdom of Crowds*, RFS: Seeking Alpha article/comment signals relate to future earnings and returns; Seeking Alpha ≠ Reddit or DC forums. https://doi.org/10.1093/rfs/hhu001
4. Ranco et al. (2015), *The Effects of Twitter Sentiment on Stock Price Returns*, PLOS ONE: aggregate correlations small, volume-peak event reactions more meaningful. https://doi.org/10.1371/journal.pone.0138441
5. Semenova & Winkler (2021), *Social contagion and asset prices*, preprint: Reddit conversations partly driven by past returns and one another; causality and peer effects complicate forecasting. https://arxiv.org/abs/2104.01847
6. Buz & de Melo (2021/2023), *Should You Take Investment Advice From WallStreetBets?*, preprint: short-term directional accuracy of aggregated advice not significantly better than naive random/equal decisions; selections of proactive vs reactive posts can matter. https://arxiv.org/abs/2105.02728

## Source access & legal/technical matrix — no unauthorized scraping

- **Stocktwits:** Public symbol page displays current 24h sentiment and some recent posts, no guaranteed historical full feed; Stocktwits Edge offers up to one year of historical sentiment / message volume / participation overlay (paid UI access). https://help.stocktwits.com/c/stocktwits-edge/stocktwits-edge/historical-sentiment-data. Official API page indicates enterprise inquiries: https://api-docs.stocktwits.com/. Need written/API access permissions to bulk ingest or retain platform content.
- **Reddit:** public posts for manual exploration; API requires explicit approval; Reddit's official 2026 policy states Reddit For Researchers is the authorized research route for eligible academic research. https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy and https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data. Do not circumvent access limits, run unapproved bulk collectors, republish comment text, or train on user content without rights.
- **DC Inside:** some individual public discussions visible https://gall.dcinside.com/mgallery/board/lists/?id=stockus ; comprehensive historic export/API and automated collection permission not verified. Manual exploration only until permission/terms verified.
- **Naver Finance 종목토론실:** visible section exists but full historical access and redistribution authorization not verified; Naver search API is **not** an authorized substitute for wholesale forum scraping. https://developers.naver.com/notice/article/33400.
- **News:** official issuer press releases / SEC filings, legal/licensed timestamped feeds, reputable articles. Publication time, correction time, initial retrieval and source are required. Model estimates/unsourced rumours are low evidence.
- **Prices:** adjusted SOXL daily + exact official NYSE Semiconductor Index (not SOXX), QQQ as control. Need reliable minute or official session OHLC for precise event mapping.

## Pilot A: 7 manually assessed public Reddit items — *direction annotation quality only*

Files:
- [Selected manual pilot samples](./data/2026-10-17_SOXL_SOCIAL_MANUAL_LABEL_PILOT.csv) (source links and scores only, NO post text or names).
- [reproducible prospective diagnostic script](./scripts/social_prospective_diagnostic.py)
- [five leakage-guard unit tests](./scripts/test_social_prospective_diagnostic.py)

The 7 examples are **purposively sampled because of visible label ambiguity**. Exact event times unavailable in the public snapshots, therefore `predictive_eligible=false` on every sample and NO post is backfilled into a pre-close trading signal.

Threshold definition fixed for *this audit only*: third-party sentiment > +0.2 => positive; < -0.2 => negative; else neutral. Human-coded *future price direction*, -1/0/+1, is a different semantic target than third-party emotional valence.

Measured on 2026-10-17:
- Examples: 7
- Directionally labelable: 4
- Same direction as third-party sentiment threshold: **1 of 4**
- Future-return predictions tested: **0**
- This is NOT a population accuracy, sentiment-alpha evidence, model benchmark, or representative sample.

A strong buy recommendation in the selected ChartExchange Reddit examples had a negative external sentiment score -0.683; a historical loss complaint had a positive 0.925; social text polarity and trade stance differ. A true annotation study must use 2 independent annotators and blinded random sampling, with time-varying category and sarcasm.

**Public-site observation (unpaired)**: Stocktwits SOXL public landing page showed bullish sentiment ~71 while SOXL October 16, 2026 closed -12.74%. Snapshot time and metric 24h rolling window are NOT synchronized: descriptive juxtaposition ONLY, cannot infer contradiction/forward relation or contemporaneous correlation. https://stocktwits.com/symbol/SOXL

### Toy prospective time join: unit tests PASSED

Only *rights-cleared*, timestamped post annotations accepted. Inputs:
- post CSV: ticker, platform, source_kind, direction, published_utc, first_seen_utc (plus optional source pointer).
- price CSV: session_date, open_utc, close_utc, soxl_open, soxl_close, qqq_open, qqq_close.

Features from **72h before session open minus 15m**, requiring `max(published_utc, first_seen_utc) <= cutoff`. Includes weekend -> Monday. Calculates only following session intraday prices. Rejects naive dates, future first-observed content, invalid data. Price rows must come from **verified** price sources, not synthetic prices used by tests.

The demonstration tests ran locally on **synthetic market bar inputs**, all 5 passed. They validate TIME ALIGNMENT CODE ONLY; they do not establish market prediction.

## Further preregistration: features and forecast experiment

Separate independent channels:
- `news_fact_tone` (source, factual or speculative, timestamp, unexpected vs expected news), `news_surprise`, `news_volume_z`;
- `forum_direction` (up/down/neutral), `forum_emotion` (fear/euphoria/anger), `forum_action` (buy/sell/wait), `forum_disagreement`, `unique_contributor_count` after compliant aggregation and deduplication, `participation_spike`;
- `novelty` (new fact versus recycled news) and `evidence_quality` (SEC filing versus repeated hearsay);
- `asset_target` mapping: SOXL, NYSE Semiconductor Index, Nvidia, TSMC, MU, AVGO, SOXX, AMD and Korean equivalents. Avoid mapping Korean SK Hynix posts directly to US SOXL without verifying transmission and market timezone.

**Primary target**: next regular-session NYSE Semiconductor Index and SOXL open-to-close direction/return; SOXL levered daily returns evaluated after costs. **Secondary**: next-session realized volatility and session volume. **Negative-control**: past close-to-close return -> *subsequent* sentiment.

Baselines and ablations:
- B0: cash / flat; B1: recent price, trend, volatility, QQQ sector-relative return, rates/credit if available;
- B2: B1 + factual news timestamped; B3: B2 + Stocktwits; B4: B3 + Reddit; B5: B4 + Korean forums (only if permitted and times verifiable).
- Null: shuffle post sentiment among *time-matched* days without shuffling price, lag reversals, time-shift placebo. Control shared market catalysts and overlapping news.
- Pre-register volatility / interest-rate regimes and sentiment score changes (delta/z-score vs rolling 20 sessions), direction, disagreement. Do not choose thresholds in hindsight.
- Train using permitted historical windows, then **2026-10-19 onward forward/untouched**; short 2026 horizon probably not enough for statistical certainty. Rolling weekly aggregates may be highly autocorrelated.
- Review quality: at least 100 random masked multilingual samples, 2 independent annotators, agreement; include sarcasm and 'RIP but buying more' cases. Mislabels invalidate model claims.
- Statistical methods once N sufficient: block-bootstrap or HAC for overlapping daily returns, confidence intervals, correction for multiple hypotheses and regimes, walk-forward validation. Correlation alone cannot establish cause. After-cost / turnover / worst drawdown must be reported.

**Promotion conditions:** no predictive claim until source permission, full input provenance, timestamp/revision checking, sufficient independent observations, honest heldout incremental lift over B2, quantified uncertainty, and independent Risk/Committee gates.

## Next actions
- [ ] Source authorization and lawful data access plan for each named forum (no circumvention).
- [ ] Confirm exact 24h Stocktwits 0-100 sentiment definition and recorded time snapshots; assess Edge export availability/license.
- [ ] Freeze daily or premarket as-of snapshots prospectively where permitted.
- [ ] Acquire reliable official SOXL / ICESEMIT / QQQ prices and event-time news.
- [ ] Create blinded dual human annotation protocol and sentiment/stance/domain model calibrations.
- [ ] Baseline vs news vs forum incremental forecasting / lagged response test when data adequate.
- [ ] Record successes, failures, source restrictions as append-only artifacts.
