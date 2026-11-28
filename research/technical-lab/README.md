# QuanTrade Technical Lab — replay v1

**EXPLORATORY_NOT_VALIDATED.** Research-only module. No existing backtest.py, forecast, risk rule, brokerage, Railway, workflow schedule or capital allocation changes. #135 G0 remains blocked.

## Run offline

Requires Node.js 20+; no package installation. Supply local CSVs you are permitted to use.

    node research/technical-lab/run.mjs --self-test
    node research/technical-lab/run.mjs manifest.json local-output/mar-001

Copy manifest.example.json to a local manifest and replace paths and SHA-256 with exact file hashes. Paths resolve from current working directory. Use distinct output directories; report.json refuses overwrites. Reports record provenance and hashes of inputs, manifest, engine, rules and runner, metrics, daily NAV/target/actual exposure, simulated fills and fees. No network, secrets, live feeds or order APIs.

Prices: canonical header date,open,high,low,close; explicit legacy-spy and plainbacktest parsers also supported. Ordered unique dates, positive coherent OHLC, gross jumps >35% rejected. At least 200 sessions including first test date. Does not certify exchange calendar, corporate actions or licensed rights. VIX CSV uses CLOSE; HY uses BAMLH0A0HYM2. For M add vix and credit manifest entries with path, source, rights, basis, sha256. GH5 requires vix. Lagged macro observations freeze decisions on missing values; report missingDecisionDays. Weekly schedule uses final observed session as calendar proxy. No cash yield, forced liquidation or FX; fractional positions.

## Frozen scope

rules.json freezes D/H1/H3/H5/GH5, crisis B, staged P/M, execution variants and benchmarks. Older event studies remain evidence, not implemented in v1. Not a general multi-asset engine. Do not optimize again on SPY/QQQ or choose a winner after inspecting results. See #143 and #135.

## Evidence

regression_report.json: 15 synthetic assertions and 13 historical return reproductions executed using exact core functions in a JavaScript runtime before committing. Node CLI has not yet been executed and repository CI has not verified this branch. Reproduction is not predictive validation. No raw market or credit data copied.

PlainBacktest market-data snapshot (2026-09-26), PlainBacktest data contributors, source https://github.com/Sixian-Li/plain-backtest, stated license CC BY 4.0 https://creativecommons.org/licenses/by/4.0/. Parsed and calculated aggregate outputs only; source adjustment and redistribution chain not independently verified. Legacy SPY/VIX/HY sources in #143; archived HY rights and historical publication dates unresolved.

Next: verify CLI in clean Node environment, automate regressions using authorized local data, audit calendar and PIT sources, implement earlier event studies and independent non-US/sector/delisted tests. No Field promotion without canonical gates.

## Multi-asset and multi-timeframe extension

    node research/technical-lab/batch.mjs --self-test
    node research/technical-lab/test_batch.mjs
    node research/technical-lab/batch.mjs batch-manifest.json local-output/batch-001

Use batch.example.json. Requires exact common start and end trading dates and identical observed session calendars across assets; reject mismatches, missing boundaries and short warmup rather than imputing or silently intersecting. All assets initially receive equal independent capital, then drift; no cross-asset rebalancing. Aggregate NAV and NAV-weighted equity exposure are computed from daily sleeves, not averages of individual returns or MDDs. meanSleeveTurnover is explicitly the mean of individual turnover measures, not portfolio-level turnover. All input hashes verified. M/GH5 require macro boundary coverage; interior missing decision days remain reported. Batch report includes each asset's trades, NAV, metrics and final causal multi-timeframe snapshot; does not use MTF indicators as new trading rules. Large batches may require chunking; output is currently in-memory JSON.

Multi-timeframe: daily current close; weekly Monday buckets, monthly calendar buckets, annual calendar buckets. The first higher-timeframe bucket is excluded (potentially truncated). A higher-timeframe bar is only made available on the first observed session of the following period. No unfinished period enters MA/CV features. Missing periods and exchange calendar completeness are not independently audited; this is conservative observed-bar aggregation, not proof of full session coverage. Daily MA 5/10/20/60/120/200/240/480/720/960, weekly 5/10/20/40/60, monthly 5/10/20/30/40/60/100/120, annual 2/3/5/10. SMA slopes are per-bar changes in price units. Compression CV (population) daily 5/10/20/60/120, monthly 5/10/20/30/40/60; support distances from latest completed monthly close to 60/100/120-month SMA. Insufficient history produces null, never zero.

multi_regression.json: 21 synthetic assertions and historical full-prefix checks on 15,328 SPY/QQQ daily rows, exact multi.mjs core functions executed in JS runtime. batch_reference.json: 12 manifest/calendar assertions and independent equal-initial-weight hold benchmark calculation for two real common periods. Neither is proof of an end-to-end Node CLI run. test_batch.mjs adds integration fixtures for CLI/report/hash/calendar/overwrite checks; execution and CI pending. All rule versions remain exploratory; no MTF trading signal or production action.

## Causal event study extension (QT-MAR-O)

    node research/technical-lab/run_events.mjs --self-test
    node research/technical-lab/run_events.mjs event-manifest.json local-output/event-001

Use event.example.json and event_rules.json. Eight predeclared proxies: D/M compression breakout, 100-month support touch, 252-session closing high, first mature daily decline, D/W/Y MA reclaim. Higher-timeframe observations occur only on publication day. Each event and eligible non-event receives 5/20/60/120-session outcomes: next observed open to signal+h close, .995 round-trip multiplier; gross MAE/MFE and intrahorizon low <=90% entry. Censored outcomes remain null. Separate nonoverlap selection per asset/rule/horizon/group; not independent across assets or matched controls. Event calendars are asset-specific (not aligned portfolio). Price/hash audit rejects assets rather than imputing. Hash failures abort; rejected assets are listed. Entire raw observation ledger is saved in one exclusive output JSON; large runs need chunked output in future.

event_pilot.json records 15 executed synthetic assertions and exploratory 7-asset historical results (SPY, QQQ, MSFT, XOM, JPM, KO, GE; 61,398 input daily rows including warmup). AAPL rejected under existing >35% audit rule: 2000-09-29 source close changed -51.87%; this may be a genuine move, not established data corruption. Exclusion can bias results; no automatic deletion or smoothing. Rule thresholds not tuned; new research proxies, not exact replication of all MAR-A–F or cafe rules. Core event functions ran in JS runtime with an equivalent standalone aggregation builder; imported Node CLI and CI remain unexecuted. No production integration. Source attribution and data gate above apply.
