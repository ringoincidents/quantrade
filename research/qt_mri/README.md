# QT-MRI — Market Regime Intelligence research preflight

**Current state: G0 NOT PASSED / NO DATA INGESTED / NO BACKTEST / NO FORECAST / NO TRADE.**

This is a quarantined research-only path for the [2026-11-22 Founder proposal](../2026-11-22_MARKET_REGIME_COMPOSITE_SCENARIO_RESEARCH_V0.md) and [Issue #135](https://github.com/ringoincidents/quantrade/issues/135).

## Read in order

1. [Founder intent and historical research](../2026-11-22_MARKET_REGIME_COMPOSITE_SCENARIO_RESEARCH_V0.md)
2. [Candidate indicator registry](indicator_registry.yaml) — 31 proposed sources, provenance status, actual-data blockers, licensing and as-of safeguards
3. [G0/G1 preregistration](G0_G1_PREREGISTRATION_2026-11-22.md) — minimum VIX/HY/DGS10/QQQ/SPY panel and fixed first falsification experiments

## Before any work resumes

- Check the canonical `QUANTRADE_CANONICAL_VISION.md`, `CLAUDE.md` v3.2, and `market_indicators.py` code-level **no-composite-scores/no-regime-label** constraint.
- Do not use 2026 as an untouched holdout: founder discussion already exposed 2026 market events.
- Do not equate data series existence with point-in-time data availability or legal permission to redistribute.
- Do not build or re-enable a trading signal/dashboard first. No production imports, no auto orders.
- Record new findings (including failure and source blockers) under [Issue #135](https://github.com/ringoincidents/quantrade/issues/135) and preserve provenance.

**First PC/CI deliverable**: source-qualified, hash-addressed raw data and normalized as-of panel with QA report. Until that exists, experiments remain **BLOCKED / NOT RUN**.
