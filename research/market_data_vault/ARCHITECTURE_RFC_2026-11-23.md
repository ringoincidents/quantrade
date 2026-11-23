# Market Data Vault / Indicator Library — research foundation RFC v0.1

- Date: 2026-11-23 KST
- Founder request: Preserve historical market data once and reuse verified, versioned indicator computations across future QuanTrade projects.
- Work tracker: [Issue #137](https://github.com/ringoincidents/quantrade/issues/137)
- Related signal study: [Issue #135](https://github.com/ringoincidents/quantrade/issues/135), [PR #136](https://github.com/ringoincidents/quantrade/pull/136)
- Status: **RESEARCH / SANDBOX — not production infrastructure, not populated with actual licensed market history**
- Scope: QuanTrade Domain Research, NOT Holdings Core, NOT Trading Execution. No ongoing collectors are enabled.

## 1. Root problem

Every research attempt rediscovers the same data/API obstacles: historical availability, source restrictions, adjustment and corporate-action conventions, release timing, and fragile vendor-specific scripts. A source file fetched once is lost or changed without a reproducible snapshot; rolling indicators are reimplemented with incompatible seeding; a successful experiment cannot be repeated from its precise source vintages.

The durable solution is **not** to treat an online data API as a permanent database. It is to put a stable QuanTrade-owned contract between providers and research, with an append-only local/private record of legally acquired source payloads, explicit transform versions and a well-defined point-in-time selector.

## 2. Scope reconciliation (avoid duplicate architecture)

Existing reusable capability:
- `quantrade/capabilities/features.py`: `FeatureProvider`, `NativeFeatureProvider`, metadata and deterministic return/SMA/vol computations.
- `indicator_significance_test.py`: historical rolling SMA, RSI and ATR variants (Alpha Lab quarantined).
- `analyze_lib.py`: additional technical indicator functions. Some have different seeding/interpretation.
- `market_indicators.py`: existing v3.2 **forbids** composite market regime scores/trading labels in active outputs.
- `architecture/TRADING_CAPABILITY_PROVIDER_CONTRACT.md`: existing `MarketDataProvider` and `FeatureProvider` seams and strict authority boundaries.
- `research/2026-11-22_MARKET_REGIME_COMPOSITE_SCENARIO_RESEARCH_V0.md`: the first high-value consumer of long-term market data and point-in-time factors.

**Do not create competing capital-decision authority or another production market provider.** The P0 code here is standalone and read-only from QuanTrade's perspective. Later adapter reconciliation must choose canonical parity/semantics and pass deterministic regression and governance gates.

## 3. Architecture

```text
Authorized vendor/API imports or user-provided licensed source files
     -> source registry (symbol identity, venue, provider, terms, release clock)
     -> immutable raw snapshots + SHA-256 manifests [PRIVATE/CONTROLLED STORAGE]
     -> schema + corporate action + PIT consistency and QA gates
     -> normalized raw bars / macro vintages [no mixed series definitions]
     -> queryable historical market store with as-of time semantics
     -> deterministic versioned technical factor library
     -> cached factor snapshots keyed by inputs + code version + parameters
     -> research lab/backtest/scenario engines, with immutable experiment IDs
     -> only via approved Research/Risk/Committee: production investment workflow
```

**Storage evolution**:
- **P0 offline (this PR)**: Python stdlib SQLite `datasets/batches/bars` with append-only data revisions, explicit first-public timestamp, SHA, rights attestation and verified-only historical view. No network, authentication, auto-collector, scheduled job, broker or private client data.
- **P1**: immutable licensed raw payloads in private local storage or private object store with SHA & backups; normalized price history as Parquet (partition sensibly by market/provider/asset/year); DuckDB analytics reads Parquet; SQLite/DuckDB registry/index per workload. Pick after data size, storage costs and restore test; vendor redistribution restrictions take precedence.
- **P2**: optional privately hosted S3-compatible object store (R2/S3) with encryption, access control, retention and periodic checksums. Never use public GitHub for licensed bulk data. GitHub tracks only **code, manifests without private credentials/data, mock fixtures, report summaries permitted by license**.
- **P3**: stable `MarketDataProvider` adapters for approved providers. On a source outage retain last verified snapshot; mark stale and route to allowed fallback without silently mixing price conventions. Catchup jobs with gap checks/retries; schedule is *not* a realtime trading guarantee.

## 4. Data contracts and invariants

A dataset's canonical identity must encode at least: stable `asset_id` (not ticker-only), exchange/calendar, source, adjustment basis, currency, frequency, bars/total return price conventions, acquisition rights and retention. `dataset_id` is unique within this research vault; two vendors or raw vs adjusted bars must **never be indistinguishable**.

The P0 CSV requires:
`session,open,high,low,close,volume,first_available_at_utc`
where first_available_at is **verified time the row/version could actually be accessed**, not the OHLCV session date or the date someone downloaded the file. Timestamp carries a timezone offset. All price and OHLC values must be finite/positive and consistent, volume nonnegative. Duplicate same-day rows in the same file are rejected. Revisions at a later available-at time remain append-only.

`ingest_csv` requires an explicit assertion that local retention is lawful; this is **NOT license verification**, and a user who does not know the license must leave it false and investigate. Availability verification is a separate boolean; unknown publication times/uncertain claims are excluded from default PIT query. A source's CSV *assertion* alone is not independently verified evidence — preserve source release records or manual audit proof.

**P0 intentionally accepts RAW_OHLCV only.** Raw series may contain stock splits and extraordinary distributions. They **must not** be used to compare long-horizon returns or indicators across corporate actions until adjustment series and as-of corporate action logic are validated. Later addition of dividend-adjusted bars and point-in-time survivorship data must be versioned and audited.

The present SQLite design keeps a dataset definition, hashes each complete CSV batch and stores historical revisions rather than destructive overwrite; an `asof` query chooses the last **verified available** version known at the decision timestamp. It does not prove that the provider's historical backfill contains all actual vintages (a future API/manifest audit is needed). It is **not** a raw-payload archive yet: the researcher must maintain original CSV privately alongside SHA until the P1 raw snapshot layer is built.

Other field families require distinct schemas:
- Option-implied **VIX** cannot be calculated from QQQ/SPY OHLCV alone: requires actual SPX option market quotes + Cboe methodology and data rights (or published licensed VIX values).
- **High-yield OAS** requires bond/pricing/option-adjustment inputs or source time series. Moody's BAA10Y is an alternative *different factor*, not substitute data.
- **DXY** is a currency basket with specific source conventions; cannot silently replace with FRB broad dollar index.
- **CNN Fear & Greed** has source methodology/components; an in-house approximate replica must be separately named.
- **US macro / Korean exports** require observation period, vintage, original published time, revisions and release calendars; do not convert monthly to daily on the observation date (lookahead).
- **OHLCV-derived SMA/EMA/RSI/ATR** can be computed deterministically from properly sourced adjusted/raw inputs with explicit warmup, smoothing and versions.

## 5. Indicator reuse & formula-version contract

`research/market_data_vault/indicators.py` contains sandbox-only:
- SMA: N-period trailing arithmetic mean; warmup N-1.
- EMA: alpha=2/(N+1), seed at N-period SMA.
- RSI: Wilder smoothing, seed on N daily changes, warmup N, flat=50, rise-only=100, fall-only=0.
- ATR: Wilder true-range smooth, seed average of first N true ranges.

**PARITY WARNING:** existing `indicator_significance_test.py` defines RSI flat=100, and existing `rolling_atr` uses SMA of true range rather than Wilder ATR. **Identical names do not imply identical values**. Preserve old results and implement explicit parity/migration tests before replacing any production or past research output. New implementations may remain independent for experimental purposes; after passing parity/approval, converge on one approved `FeatureProvider` interface rather than keeping divergent duplicated algorithms forever.

Each factor value in the future must expose: `name, version, params, asset_id, dataset_id, input_sha, session, asof, lookback, value, status, produced_at`; cached values invalidated or versioned after data revisions, code/seed/parameter updates.

## 6. Data acquisition research shortlist (2026-11-23; sources must be verified per version)

| Source | Suitable for | Important limits |
|---|---|---|
| [KRX Data Marketplace OPEN API](https://openapi.krx.co.kr/) | Korean prices, indices and metadata where product permits | Key/application, historical endpoints and use/redistribution terms vary; commercial products may require separate contract |
| [FRED / ALFRED](https://fred.stlouisfed.org/docs/api/fred/series_observations.html) | Rates, inflation, employment, some credit and commodities | Third-party series rights, vintage vs original-release-time, history truncation; ICE BofA HY OAS currently short history |
| [Cboe VIX](https://www.cboe.com/tradable_products/vix/vix_historical_data) | Historical volatility index | Indicator vs licensed underlying option quotes distinction, legal use verification |
| Direct licensed ETF/stock EOD feed | US adjusted/raw OHLCV, distributions and corporate actions | Vendor selection unresolved; free demo feeds may be limited history. Official iShares/Invesco/SSGA pages are not guaranteed full adjusted OHLCV APIs |
| [DuckDB + Parquet](https://duckdb.org/docs/data/parquet) | Queryable local analytical lake | Storage/query tool, **not** an entitlement to stock data or historical price feed |

Potential source adapters may use vendor SDK, HTTP or CSV behind the existing MarketDataProvider seam; never hardcode private API keys, and do not build a crawler that bypasses terms or rate limits.

## 7. Sustainability: how new research becomes cheaper

When researchers need VIX / SOXX / QQQ 20-day RSI:
1. Query the catalog for the exact series+timespan+license+adjustment.
2. If already present, query the immutable dataset/vintage and compute versioned factors without re-downloading.
3. If missing, open one provider/source acquisition task (not an ad-hoc script inside each research).
4. Store raw+hash+quality report with a stable dataset snapshot ID.
5. Research references **only dataset snapshot ID, factor library commit, parameter set and as-of rule**.
6. Audit a new provider/algorithm against existing reference tests before adoption.
7. Cache derived factors but recompute deterministically if source/parameters change.
8. Back up the data vault and periodically perform an actual restore test; storage without recoverability is not sustainable.

The Data Vault is also a single place to record **unavailable** sources: price data rights, histories, signal lags, known gaps, and previous failed acquisition routes.

## 8. Delivery phases / rejection gates

**P0 (this PR, design + synthetic-only code)**: reproducible offline CSV→validated database→asof snapshot, SHA-256, rights and verification gates; pure indicator routines/tests. No real data, no claimed forecast performance, no deployed storage. Verify local synthetic test results separately.

**P1 (source proof)**: approved QQQ and SPY source plus 1 Korean series, VIX + Treasury yields; real import, splits/dividends & as-of QA, docs of license. Must prove complete range, no silent gaps and re-download yields same hash or auditable vendor revision. If not, mark blocked.

**P2 (durability)**: private raw snapshot store, Parquet query layer, repeatable historical ingest/incremental update/backup restore, running cost/limits and provider failover. Show sample benchmark with actual dataset and traceable manifest.

**P3 (research consumers)**: convert the blocked [QT-MRI #135](https://github.com/ringoincidents/quantrade/issues/135) VIX+credit test into a reproducible research job. Maintain chronological OOS validation; no new market index/AI forecast status without passing existing gates.

**STOP conditions**: source rights unresolved, first-known timestamps fabricated, corporate-action values unavailable for intended return calculations, corrupted source, provider switching without audit, cross-market calendar mismatch, license breach risk, repo-sized raw-data commit, no recoverable backups.

## 9. Honest known limitations of the P0 prototype

The prototype is deliberately small and **is not yet the durable object-store product**:
- SQLite contains rows and batch hashes, but original raw source files must be separately preserved securely; this PR does not automatically archive them.
- 'availability_verified=True' records an operator assertion, not independent third-party proof; the evidence reference should be expanded in P1.
- No adjustments, split histories, FX normalization, macro vintages, delisted-universe members, archive/encryption, provider API clients, online updater, cache invalidation, query SLAs or CI/runtime integration.
- Valid OHLC rows do not prove quality. Extreme prices, stale feeds, holiday issues and mismatched vendors require P1 QA.
- Tests use **synthetic price files only** and cannot establish real market predictive edge, lawful access or operational continuity.

## 10. When resuming future research

> "잠깐! 이 데이터를 예전에 확보했을 수 있어. 먼저 Market Data Vault Issue #137의 데이터 카탈로그·출처·히스토리·데이터 품질·지표 버전을 확인해. 없을 때만 새로운 API를 조사하고, 확보한 데이터와 지표는 재사용 가능한 저장소에 등록하자. 만약 QT-MRI #135가 막혔다면 이 기반시설을 먼저 통과시켜라."

No automatic order, live signal, production workflow or changes to Holdings Runtime are authorized by this RFC.
