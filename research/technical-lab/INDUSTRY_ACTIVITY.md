# QT-INDUSTRY-ACTIVITY-0.1 — exploratory economic activity proxy
Status: EXPLORATORY_NOT_VALIDATED, no investment authority. Scope is isolated research under #146; #142 live/watchlist scope and #138 source storage untouched. This is a new descriptive research contract, not a new MAR indicator or entry rule. All thresholds are heuristic, frozen before real data; no fitting or empirical validation.

## Initial US source candidates (official pages checked 2026-11-28)
| Industry | Two required measures | Source candidates | Limitation |
|---|---|---|---|
| Semiconductor/components | production index, utilization | Fed G.17 NAICS 3344 [IPG3344S](https://fred.stlouisfed.org/data/IPG3344S), [CAPUTLG3344S](https://fred.stlouisfed.org/series/CAPUTLG3344S) | same production/capacity family, US not global chips |
| Petroleum | products supplied, crude production, daily average monthly | [EIA petroleum supply](https://www.eia.gov/petroleum/supply/monthly/) | domestic demand proxy/production, not profitability or global balance |
| Power infrastructure proxy | electricity retail sales MWh, nominal power construction NSA | [EIA electricity sales](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_01), [Census construction](https://www.census.gov/construction/c30/data/index.html) | weather, nominal spend, not grid orders |
| Construction proxy | housing starts SAAR, total nominal construction spending NSA | [Census indicators](https://www.census.gov/economic-indicators/housing_starts), [construction spending](https://www.census.gov/construction/c30/data/index.html) | mixed residential/all construction, no inflation correction |
| FDIC banks | total loans, ROA | [FDIC QBP](https://www.fdic.gov/quarterly-banking-profile), [historical archive](https://www.fdic.gov/quarterly-banking-profile/past-quarterly-banking-profiles) | insured US banks; not all finance |

These are source discovery candidates, not acquired or certified data. Before ingest, independently verify exact series IDs, scope, seasonal adjustment, units, reporting changes, revision lineage and permitted rights. EIA electricity table thousand MWh must be converted to MWh with documented exact scaling; no implicit unit conversions in calculator. Census nominal values retain nominal basis. FDIC quarterly ROA definition must be consistent; annual YTD series cannot substitute. Current revised series without historic release/vintage evidence must not be used as PIT records. For US not Korean or global industries; additional markets require separate definitions.

## Arithmetic and abstention
For each required series, select latest known release of each exact period as of UTC cutoff, and common target period = earliest of latest available periods. Both series require current and year-ago values and their 3-month-prior (quarterly: 1-quarter-prior) counterparts. Growth is year-over-year percent change for positive quantities, percentage-point change for rates. Acceleration is growth minus previous growth. If both indicators agree strictly on growth and acceleration signs, label expansion (+,+), slowdown (+,-), recovery (-,+), contraction (-,-). Otherwise MIXED_OR_FLAT. Labels describe activity proxy, not sector-price prediction or economic ground truth. Zero threshold and freshness bounds are heuristic not calibrated. Missing series/required dates/stale common periods or >one quarter mismatch block; monthly reference lag 3 months semiconductor, 4 other; quarterly 6 months banking. Do not silently impute or use old common periods to hide a missing current value. No score or cross-industry ranking. Output retains selected vintage evidence and period.
 
## Input and execution
JSON: {contractVersion:"QT-INDUSTRY-ACTIVITY-0.1",asOf:"...Z",series:[{id,frequency:"M" or "Q",unit,source,capturedAt,status:"VERIFIED",rights:"RESEARCH_ALLOWED",evidenceSha256,observations:[{period:"YYYY-MM" or "YYYY-Qn",value,knownAt,source,status,rights,evidenceSha256}]}]}. Series IDs/unit/source exactly as --contract; observation times must be after reference period end and no later than capture. Reject ambiguous duplicate period/knownAt; select newest known revision, ignore later revisions. Verified rights and evidence metadata are attestations, not authenticated by code. Private source bundle only; keep raw data and keys out of Git.
 
    node research/technical-lab/run_industry_activity.mjs --contract
    node research/technical-lab/run_industry_activity.mjs input.json <expected-sha256> output.json
    node research/technical-lab/test_industry_activity.mjs

Output writes exclusively and binds input, contract, and code hashes. No network, no scheduled live collection, no actual phase estimates from missing data. 
## Next gate
Get source-reviewed independent release/vintage observations via #138 Vault; calibrate neither thresholds nor series using current outcomes. Freeze independent industry-cycle ground truth, predeclare dates/hypotheses and coverage, then test stability/lead-lag against later official activity/profit data and market-relative returns. Add industry-specific inventories/orders/margins/capacity only with reviewed contract. Do not conflate the existing sector-price relative context with this descriptive activity phase. No production promotion.
