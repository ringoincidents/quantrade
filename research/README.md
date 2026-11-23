# QuanTrade Research — durable entry points

This is a **research index**, not implementation authority. The canonical company direction remains in [QUANTRADE_CANONICAL_VISION.md](../QUANTRADE_CANONICAL_VISION.md), and the earlier alpha failure/prediction-disablement gates remain in [CLAUDE.md](../CLAUDE.md).

## Foundational data research — retrieve before new API/history work

- **[Market Data Vault — reusable licensed historical price storage + versioned indicator library](market_data_vault/README.md)** / [Issue #137](https://github.com/ringoincidents/quantrade/issues/137) / [Draft PR #138](https://github.com/ringoincidents/quantrade/pull/138): collect once, retain source rights/provenance, keep private raw data, deterministically recompute indicators. First check this catalog when a study stalls over data or indicator formulas. **P0 is synthetic-test-only, no licensed market feed/populated research data, no execution or authority.**
- This infrastructure is a prerequisite for serious [Market Regime Composite/10,000-path scenario research](2026-11-22_MARKET_REGIME_COMPOSITE_SCENARIO_RESEARCH_V0.md). Avoid repeating the same data-acquisition blocker in each strategy.

## First retrieve before restarting similar work

| Topic / trigger | Durable record | Next action |
| --- | --- | --- |
| **Market-bottom research; VIX / high-yield OAS / DXY / RSI / US rates / exports / gold / oil; composite market state index; 10,000 Monte Carlo forecast fan; one-chart UX** | [QT-MRI-2026-11-22 — Complete Founder intake & experiment plan](2026-11-22_MARKET_REGIME_COMPOSITE_SCENARIO_RESEARCH_V0.md), [tracking Issue #135](https://github.com/ringoincidents/quantrade/issues/135) | **STOP / read first.** G0 provenance-safe data registry + G1 VIX/HY credit spread lead-lag study. NOT VALIDATED; no forecasting activation or order authority. |
| SOXL year-end rebound / market seasonality | [2026-10-17_SOXL_YEAR_END_REVERSAL_RESEARCH_V0.md](2026-10-17_SOXL_YEAR_END_REVERSAL_RESEARCH_V0.md) | Review existing gate and ICE NYSE Semiconductor Index/LETF path-dependence before duplicate research. |
| SOXL, IONQ, TE capital rotation and risk | [2026-10-19_IONQ_TE_TO_SOXL_ROTATION_RESEARCH_CASE_V0.md](2026-10-19_IONQ_TE_TO_SOXL_ROTATION_RESEARCH_CASE_V0.md), [2026-11-18 risk review](2026-11-18_SOXL_IONQ_TE_INCREMENTAL_RISK_REVIEW.md) | Review evidence blockers and independent risk, no assumed live trade. |
| External quant OSS assimilation | [TRADING_OSS_RESEARCH_PROGRAM.md](TRADING_OSS_RESEARCH_PROGRAM.md) | Research first, pin upstream version/license, promote only through validated gates. |

## Intake rule

New market strategy ideas and external forecasting projects are `OBSERVED` sources until reproducible, point-in-time and out-of-sample evaluation supports them. Keep sources, old predictions, data limitations, negative tests and supersession append-only. A future worker should look up this index and active GitHub issues **before** building yet another predictor or dashboard. Neither this index nor an open issue authorizes capital movement or core architecture changes.
