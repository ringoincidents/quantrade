# QT-MRI G0 source audit — 2026-11-22 (confirmed metadata, NO historical test)

**Scope:** first source viability review for [Issue #135](https://github.com/ringoincidents/quantrade/issues/135); extends initial [research preregistration](G0_G1_PREREGISTRATION_2026-11-22.md).
**Status:** G0 SOURCE AUDIT PARTIAL, **FULL HISTORICAL DATA NOT ACQUIRED**, G1 predictive testing NOT RUN.
**Method:** inspected official FRED/FRB/Cboe source notes and time-series metadata. Tool environment has no direct external download route; local/test runs used explicitly synthetic data. Source URLs are evidence of metadata, not a reproducible dataset or a license grant.

## Source-by-source findings

| Source | Verified historical coverage or availability | Rights and time-as-of constraints | Next action |
|---|---|---|---|
| Cboe VIX via FRED `VIXCLS` | Official published range 1990-01-02 to 2026-11-19 in FRED table (observed 2026-11-22). Cboe provides historical daily VIX CSV (1990–present). | End-of-day values must be available before stock-close signal or next session; source/publisher terms and update timestamp verification. | Preferred VIX benchmark once downloaded and checksummed |
| ICE BofA HY OAS `BAMLH0A0HYM2` | **2023-11-21 to 2026-11-19 on FRED** as of this audit; starting April 2026 only a rolling ~3-year history is distributed. | ICE copyright: FRED terms describe **internal use only**, and no third-party publishing/redistribution of raw index 'Top Level Data' without approval. Release observation date need not equal publication timestamp. | **G0 BLOCKED FOR 2000–2025.** Seek licensed long historical data or treat 2023–2025 separately as short low-power analysis. Do NOT pretend 2008/2020 OAS is available from current FRED. |
| Moody's Baa–Treasury spread `BAA10Y` | 1986-01-02 to 2026-11-19 daily on FRED. | **NOT HY OAS**: Moody's Baa = investment-grade edge and spread to 10-year constant maturity, not OAS of below-investment-grade bonds. Moody's copyright text restricts reproduction/redistribution; clarify permitted private use and no raw CSV in public GitHub. Check publication lag and historical vintages. | Distinct long-history **proxy falsification** track only. All results must be explicitly labeled BAA10Y, not 'high-yield'. |
| Chicago Fed `NFCI` | Weekly series released with a lag: FRED reference week ending Fri 2026-11-13 updated Wed 2026-11-18 (example). | Week-end observation must **not** be treated as known on Friday for historical test. Index includes many same-family variables and revisions; not HY OAS. | Additional financial-stress baseline, weekly as-of join |
| St. Louis Fed `STLFSI4` | Weekly financial stress composite; FRED page documents 18 inputs and prior version changes. | Current version's historical series is retro-computed/revised; vintage consistency needed. Cannot substitute credit spread directly. | Optional baseline/challenger after vintage checks |
| FRED `SP500` | Daily S&P500 data page shows a limited, ~10-year window rather than full 2000–2025; also a price index not SPY total return. | S&P index and SPY ETF differ by fees/distributions; copyright applies. | Select long-range, adjusted ETF price history from appropriately licensed source |
| `DGS10` | Daily constant-maturity benchmark from US Treasury via H.15/FRED; published after market reference day per Fed schedule. | Daily market date is **not automatically the same as first public release**. | Next step: verify first-release, vintage/lag and fit in PIT join |

## Legal and research ethics guardrails

- No copyrighted FRED/ICE/Moody's index histories, bulk raw data or derived repackaged index values are included in this public PR.
- A public CSV link is **not** license to redistribute its contents or permit unrestricted automated scraping. Verify usage, API terms, and data retention.
- Do not scrape third-party mirrored pre-2023 HY OAS history merely because it is searchable. Only use data lawfully obtained with documented permitted scope.
- Do not bypass a source-history restriction via an unofficial mirror, silently splice Moody's Baa into HY, or represent NFCI as direct HY spread.
- G0 must separately PASS data availability, terms, publication-time, adjusted prices, as-of join, and point-in-time revision/vintage QA **before** any actual model performance number is published.

## Two-track experiment redesign (maintain H0/H1 and explicit proxy separation)

**Track A: 2000–2025 long-history falsification**
- VIX close + DGS10 + exact as-of QQQ/SPY adjusted returns + **BAA10Y**, optionally weekly NFCI/STLFSI4 as distinct benchmark models.
- Any finding is about **Baa** (investment grade), not evidence that **high-yield** OAS leads equity.
- If source rights/first-known timestamps cannot be verified, mark BLOCKED instead of convenient fake publication dates.
- Development/train 2000–2018, intermediate validation 2019–2022, sealed 2023–2025 if data were truly sealed before investigation; no model tuning on those outcomes.

**Track B: short recent direct HY OAS**
- VIX + BAMLH0A0HYM2 + QQQ/SPY, available ~2023–2025 as of audit and limited recent observations.
- Too short to support claims across 2000/2008/2020 crises; report number of **independent** stress episodes. This track may have little or zero signal count.
- Do not treat the short window as a credible untouched evaluation period if it guided threshold selection. Explicitly disclose contamination and sample-size limitation.

## What was actually implemented and tested during this session

- Added research-only `asof_engine.py`, which rejects missing/naive timestamps; uses only explicitly published values as of each provided equity close; rejects substitution between `BAA10Y` and `BAMLH0A0HYM2`; calculates first VIX >30 cross, post-stress spread-turn candidate and future return + maximum adverse excursion (MAE) by horizon.
- Local Python `unittest -v`: **8 of 8 synthetic tests passed** after correcting an initial as-of join bug. Earlier failed test and fix are preserved here as genuine development history, not ignored.
- End-to-end **synthetic-only** CSV runner completed (343 fabricated weekday closes); two artificial VIX crossing episodes, zero credit-turn episodes, and zero combined events. These are not historical results and prove no finance claim.
- **NO** market data downloaded into executable container due outbound DNS/download restriction; no real historical forecasts, regressions, predictions, backtests, order execution or runtime updates.
- CI in GitHub has not independently been run; local green tests do not constitute deployment/production validation.

## Immediate next action, even without PC

1. Keep G0 PARTIAL/BLOCKED while rights and historical price data remain unresolved; do not produce baseless G1 alpha claims.
2. Retrieve exact price-source terms/history for QQQ and SPY and first-public timestamps for VIX/credit where feasible.
3. When a network-capable authorized runner is available, obtain lawful point-in-time source records, store private or license-permitted raw snapshots with hash manifests and release stamps; then execute `python -m unittest discover -s research/qt_mri -p 'test_*.py' -v`.
4. Run G1 only after data QA passes; require low-power/no-event labels if samples are too short. Save all failures.

## Official source URLs inspected

- https://fred.stlouisfed.org/series/BAMLH0A0HYM2
- https://fred.stlouisfed.org/data/BAMLH0A0HYM2
- https://fred.stlouisfed.org/series/BAA10Y
- https://fred.stlouisfed.org/data/BAA10Y
- https://fred.stlouisfed.org/series/VIXCLS
- https://www.cboe.com/tradable-products/vix/vix-historical-data/
- https://fred.stlouisfed.org/series/NFCI
- https://fred.stlouisfed.org/series/STLFSI4
- https://fred.stlouisfed.org/series/DGS10
- https://fred.stlouisfed.org/series/SP500

**No source URL, current value, or citation alone may override this BLOCKED status or count as an independently verified 2000–2025 as-of dataset.**
