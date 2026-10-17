# 2026 반도체 사건·가격반응 탐색 분석 v1
**Status: DESCRIPTIVE / NOT CAUSAL / NOT VALIDATED / NO LIVE ORDER AUTHORITY**
**Data cutoff: 2026-10-16 US close; recorded 2026-10-17 KST**

## Data and reproducibility
- Event provenance: [2026 event inventory](./2026-10-17_SEMICONDUCTOR_2026_EVENT_CAUSAL_MAP_V0.md), Issue #129.
- [14 selected event-day observations](./data/2026-10-17_SEMICONDUCTOR_EVENT_RETURNS_SELECTED.csv) manually transcribed from three public daily-close tables:
  - https://chartexchange.com/symbol/nasdaq-soxx/historical/
  - https://chartexchange.com/symbol/nasdaq-qqq/historical/
  - https://chartexchange.com/symbol/nyse-soxl/historical/
- [Reproducible diagnostic script](./scripts/semiconductor_event_diagnostic.py).
- Run: `python research/scripts/semiconductor_event_diagnostic.py research/data/2026-10-17_SEMICONDUCTOR_EVENT_RETURNS_SELECTED.csv`
- All 14 dates were *post hoc* selected from public event descriptions, **not** a randomized independent sample.
- SOXL pursues +300% of the *DAILY* performance of **NYSE Semiconductor Index (ICESEMIT)**, NOT SOX/SOXX. Official: https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs
- Daily returns are source-displayed close-to-close percentages, not total-return adjusted. An event-based 1-day price difference is not an executable strategy.

## Exploratory comparison
`relative_pp = SOXX daily return (%) - QQQ daily return (%)`. This is NOT beta-adjusted abnormal return, nor a causal attribution.

| Source story group | Dates | SOXX > QQQ | SOXX < QQQ | Median relative | Average relative |
|---|---:|---:|---:|---:|---:|
| demand_guidance (earnings/forecast) | 7 | 4 | 3 | +0.536 pp | +0.405 pp |
| macro_credit | 5 | 1 | 4 | -1.674 pp | -0.994 pp |
| price_regime (historical rally markers) | 2 | 2 | 0 | +1.740 pp | +1.740 pp |

Notable observations and falsifying examples:
- Feb 26 Nvidia earnings: SOXX -3.043%; QQQ -1.206%; SOXL -9.073%. Strong earnings are *not* sufficient for an ETF rally.
- Jun 25 Micron results: SOXX +3.940%; QQQ +0.811%; SOXL +10.036%.
- Aug 18 oil/yields: SOXX -4.960%; QQQ -1.693%; SOXL -14.802%.
- Oct 14 inflation/funding shock: SOXX -4.501%; QQQ -1.966%; SOXL -13.350%.
- Oct 15 TSMC Q3 record results but broader selloff: SOXX -0.907%; QQQ -0.130%; SOXL -2.886%.
- Oct 16 credit stress: SOXX -4.171%; QQQ -2.497%; SOXL -12.725%.

Pricing path stress examples (SOXL historical **closing prices**, dividends/splits must be reverified):
- Jun 25 $252.61 → Jul 29 $91.99: **-63.58%**, despite Jun 25's positive earnings reaction.
- Sep 14 $101.13 → Sep 22 $151.95: **+50.25%**; Sep 22 → Oct 16 $93.69: **-38.34%**.
These are not tradable strategy returns or forecasts.

## WHY NOT SIGNIFICANT
1. 14 hand-selected historical events (and shared Oct 14–16 shock cluster) **violate independence and sample-selection assumptions**.
2. Event-time precision unresolved: event before/after market close changes the correct comparison date. **Sep 30 Micron release date must be verified**.
3. News overlaps: yields, debt financing, geopolitical conditions, and corporate earnings coincide.
4. `SOXX - QQQ` ignores style/beta and constituent differences, and neither is SOXL's index.
5. ETF displayed daily percentage may differ from NAV/adjusted returns due distributions or market close quality.
6. No full 2026 daily benchmark data or rates/credit data dataset is authenticated here. NO p-values, correlation, causality, alpha or signal significance computed.

## Priority next experiment (requires upstream data)
- Acquire official time-stamped ICESEMIT + adjusted SOXL/SOXX/QQQ/SPY daily returns and corporate actions.
- Capture source publication UTC/ET, expected versus surprise earnings, pre/post market status; block overlapping events.
- Add FRED 10Y nominal/real yields, HY spreads, oil and an AI finance credit proxy with release-time alignment.
- Estimate event CAR over [0,+1], [0,+5] and matched control dates, market/beta factor adjustment and robust confidence intervals.
- Pre-register macro/credit filters and conduct held-out 2026 prospective replay without changing earlier parameters.
- Compare with unlevered index, cash, volatility-limited SOXL and no-trade benchmarks including after-cost return and worst drawdown.
- Store negative results; no position change until independent Risk/Committee and explicit Client authorization.

**Finding:** macro/credit-stress dates descriptively show more SOXX underperformance than earnings-guidance dates in this tiny *selected* sample. **Statistical significance / causation: UNKNOWN. Trading edge: NOT VALIDATED.**
