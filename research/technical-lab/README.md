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
