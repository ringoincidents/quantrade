# QT-MRI G0→G1 pre-registration: data integrity before predictive claims

- Research case: [QT-MRI-2026-11-22](../2026-11-22_MARKET_REGIME_COMPOSITE_SCENARIO_RESEARCH_V0.md)
- Issue: https://github.com/ringoincidents/quantrade/issues/135
- Document date: 2026-11-22 Asia/Seoul
- Type: **PRE-REGISTERED DESIGN DRAFT**, not a completed test
- State: **G0 NOT PASSED / NO PRICE MODEL / NO TRADE AUTHORITY**
- Machine-readable source candidates: [indicator_registry.yaml](indicator_registry.yaml)
- Intent: make the eventual PC/CI session start at one reproducible test, instead of debating indicators again or building a pretty but unverifiable dashboard.

## A. Critical discovered incompatibility

The existing `market_indicators.py` explicitly prohibits:
- creating an aggregate market score or named market regime;
- generating rank, signal light, buy/sell interpretation;
- silently changing the strict output schema (an audit fails closed).

This is an **existing active code-level restriction**, not a missing function. New research must live in a quarantined `research/qt_mri` path with no production imports, no enabled scheduled workflow, no modified current dashboard, and no real trading. A future production score/chart would require a separate authorized change to the existing policy/architecture **after successful evidence gates**. This research proposal does not supersede `CLAUDE.md` v3.2 alpha disablement or `QUANTRADE_CANONICAL_VISION.md`.

## B. G0 data tasks and evidence required

1. **Inspect source and legal boundaries**:
   - Cboe official historical VIX: https://www.cboe.com/tradable_products/vix/vix_historical_data (daily; check historical continuity and permitted redistribution);
   - FRED VIXCLS: https://fred.stlouisfed.org/series/VIXCLS;
   - ICE BofA HY OAS `BAMLH0A0HYM2`: https://fred.stlouisfed.org/series/BAMLH0A0HYM2 (licensed ICE index inside FRED: check specific source's usage terms; percentage points → basis points ×100);
   - FRED DGS10: https://fred.stlouisfed.org/series/DGS10;
   - SPY and QQQ official fund pages and a consistent long-horizon adjusted price/total-return data vendor (source **unresolved**);
   - do NOT use FRED `SP500` as the only 2000–2025 benchmark. The FRED series page states daily history is limited to approximately 10 years: https://fred.stlouisfed.org/series/SP500.
2. **Historical point-in-time values**: FRED API `realtime_start` / `realtime_end` and `vintage_dates` support ALFRED views: https://fred.stlouisfed.org/docs/api/fred/series_observations.html . Vintage values alone do **not** prove the data was public before US stock close: confirm the earliest available business day/time as a *separate* field.
3. **Time join contract**:
   - each input has `observation_date`, `value`, `first_public_at_utc`, `source_revision`, `retrieved_at_utc`, `earliest_signal_use_at_utc`;
   - for an unknown first-publication timestamp, use **conservative next confirmed availability** or block those sample dates—not same-day assumption;
   - US closing signal cannot place an order at that same close; next executable session only;
   - monthly Korean export values enter only AFTER first official release; subsequent revisions must not leak.
4. **Price hygiene**: price vs total return, dividends/splits, OHLC and fund inception dates, sector benchmark identity, US/KR calendars and timezone changes, missing values and vendor disagreement; freeze one consistent provider or record a blocker.
5. **G0 minimum data deliverable**: `source_manifest.json` recording exact query/URL/terms/retrieval timestamp, raw immutable files or hash pointers, `asof_panel.parquet` (if license permits), `qa_report.md` listing sample counts, end dates, lag assumptions, missing and inconsistent values, `G0_STATUS.md` PASS/BLOCKED. The candidate registry alone is not a completed dataset.

## C. Core question and hypotheses

- **Target**: QQQ and SPY total return / adjusted price. If only price-index or adjusted-price proxy is available, explicitly call this out and keep a consistent target. KOSPI and SOXX are separate later tests.
- **H0 (default)**: new VIX/credit signals do NOT improve out-of-sample conditional forward risk-adjusted outcome or predictive score against basic price-trend/unconditional benchmarks.
- **H1 (fear)**: a first daily VIX cross above 30 contains forward-return information, but may exhibit substantial further drawdown. This is not equivalent to exact-bottom timing.
- **H2 (credit turn)**: after a prior credit stress widening episode, a *persisting* high-yield OAS contraction is associated with more favorable 5/20/60-day forward returns or lower interim drawdowns, conditional on prior known state.
- **H3 (incremental value)**: combined VIX+credit turn adds held-out information over VIX alone, credit alone, and simple past-return/volatility/trend baselines.

Falsification must include equity-leading-credit as well as credit-leading-equity episodes. The target is not to prove the narrative but to estimate whether conditional information exists at all.

## D. Initial fixed signal definitions, **PROVISIONAL / NOT FITTED**

Freeze these before running; do not modify after inspecting the 2023–25 holdout. Sensitivity checks below are secondary and must be disclosed as multiple tests.

- **F1 VIX panic-entry episode**: VIX end-of-day value **first crosses upward from below 30 to >=30** at an actionable as-of timestamp. Separate stress groups 30–39.99 / 40–49.99 / >=50 descriptive only. Re-arm only after VIX below 25 for at least 10 available observations.
- **F2 High-yield OAS turn**: at decision timestamp, OAS has reached its own **trailing 252-known-observation 80th percentile** within the preceding 20 observations (all percentile computation uses past-only data), and the last 5 known observations show OAS decrease of **at least 15bp** (negative 0.15 percentage points). The as-of release must be verified. The signal is tested independently of VIX.
- **F3 Combined**: F1 first-cross panic episode followed by F2 within 20 available US equity-trading sessions. No entering on a future-dated F2; every entry occurs only on its first fully-known signal timestamp.
- **F4 Price-only challenger**: QQQ/SPY trailing 200-session close SMA + trailing 20-session return and volatility, all measured from information available at t.
- **Avoid overlapping pseudo-observations**: group signals into events; after an event, block another same-family *independent episode* count for 60 US equity sessions. Still report daily conditional descriptive result separately and label the dependence.

**Why these definitions?** The numbers are fixed hypothesis parameters, not optimized settings and not approved entry conditions. If they yield too few events, report inadequate power rather than relaxing the threshold after the fact.

## E. Evaluation targets and labeling rules

For each signal as-of t, evaluate next executable US session and:
- cumulative forward 5, 20, 60 trading day target returns (clarify price or total return);
- 126-day return exploratory, not part of pass decision;
- win rate versus unconditional matched benchmark, distribution quantiles, median, event counts, independent episode counts, 95% confidence intervals via event/block bootstrap;
- **maximum adverse excursion** over the next 20/60 trading sessions; missed upside / waiting cost relative to immediate baseline;
- whether a local drawdown trough occurs before/after signal for descriptive diagnostics only (future-known *ex-post* trough labels must never be used as feature or to trigger entry);
- historical lead/lag cross-correlation at -60,-20,-5,0,+5,+20,+60 trading days with stationary transforms and overlapping-window caveats, not arbitrary graph alignment;
- after-cost executable fill simulation only after price data, spreads, currency and slippage can be verified; otherwise no profitability claim.

Training/validation timetable:
- Proposed development: **2000–2018**, then sequential validation **2019–2022**, sealed chronological holdout **2023–2025**. These are conceptual until available data coverage is verified (do not fabricate observations).
- 2026 is **NOT sealed**: founder and prior assistant already inspected 2026 market events while shaping the hypothesis. Only new genuine prospective signal recording may be pre-registered after 2026-11-22.
- Walk-forward expanding windows with appropriate purge/embargo around overlapping horizon labels; no leak from hyperparameter fitting into holdout.
- State all selection attempts (not only best), crisis leave-one-episode-out and at least one sign-flipped/factor-shuffled negative control. Distinguish exploratory discovery from confirmatory claims.

## F. Explicit baselines & success conditions

- **Baseline 0**: unconditional 5/20/60-day target return distribution, with no factor.
- **Baseline 1**: buy-and-hold, including how forward drawdowns compare (not a strategy by itself).
- **Baseline 2**: simple trailing 200d price trend + realized 20d volatility; identical training and evaluation cut.
- **Baseline 3**: VIX alone, credit alone; combined model must outperform the *better* simple alternative in the same holdout.
- **Decision standard**: report OOS uncertainty and actual effect sizes, calibration if predictive probabilities are estimated, and risk-aware after-cost utility. An impressive backtest on 2026 or with <5 independent crises is NOT evidence of a durable strategy.
- **Pass classification**: G1 `INTERESTING_NOT_VALIDATED` if conditional effects are unstable or CIs broad; G2 `NEEDS_HOLDOUT` if model selection contaminated; G3 probabilistic predictions blocked without credible calibration. Do not quietly replace fail with a visually smooth score.
- **Future conditional simulation**: first challenge historical unconditional bootstrap, then benchmark against regime-conditional and volatility models; only use 10,000 paths to reduce simulation sampling noise, not to assert market predictability.

## G. Strict execution and engineering boundaries

- Research-only, no live orders, no new automatic scheduled production tasks, no private client balances or positions in public repo, no secrets/API keys committed.
- Do not import this research into `market_indicators.py` or bypass its audit blacklist.
- Do not edit `QUANTRADE_CANONICAL_VISION.md` or `CLAUDE.md` to match a speculative new model.
- No Holdings DB writes, Core schemas, or new Runtime workers from this G0 candidate.
- No adoption of an arbitrary Claude Skill before pinning version, license, security and independent benchmark evidence.
- GitHub branch/PR is documentation for review, **not** evidence a model ran or a requirement to merge production code.

## H. Resumption checklist

1. Retrieve [Issue #135](https://github.com/ringoincidents/quantrade/issues/135) and source idea record; inspect existing v3.2/price-signal failures.
2. Read this pre-registration **before fetching data or tuning parameters**.
3. Read [indicator_registry.yaml](indicator_registry.yaml); select only the minimal priority_1 series (VIX, HY OAS, DGS10, QQQ, SPY).
4. Fix source rights, timestamps, price adjustment and as-of alignment. Populate raw panel and QA; mark G0 BLOCKED if source/rights/split/version cannot be verified.
5. Once G0 PASS, run F1/F2/F3/F4 against baselines. **Preserve every negative test**.
6. Only then decide whether expansion to DXY, 2y/real yields, gold, oil, Korea exports and eventual one-chart composite has empirical justification.
7. Log outcome and next blocker in Issue #135; do not claim model validated merely because graph render succeeded.

## I. Source register / methodological starting points

- Cboe VIX historical data: https://www.cboe.com/tradable_products/vix/vix_historical_data
- FRED data series and third-party rights: https://fred.stlouisfed.org/series/BAMLH0A0HYM2 and https://fred.stlouisfed.org/series/SP500
- FRED/ALFRED real-time parameter contract: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- The prior research question and analogues are preserved in the parent document. These URLs are **source discovery**, not proof of the claimed predictive performance.

**No empirical result was produced by this pre-registration. Re-evaluate choices when source rights/coverage are known; changes must be versioned BEFORE inspecting held-out outcomes.**
