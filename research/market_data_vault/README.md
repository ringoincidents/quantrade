# QuanTrade Market Data Vault — P0 Offline Research Prototype

**Status:** SANDBOX / OFFICIAL TREASURY LIVE PILOT SUCCESS (3 years, 751 sessions each maturity) / NO PERSISTENT LICENSED DATA STORE / NO VALIDATED SIGNAL / NO LIVE TRADING

- Tracking: [Issue #137](https://github.com/ringoincidents/quantrade/issues/137)
- Canonical project vision: [QUANTRADE_CANONICAL_VISION.md](../../QUANTRADE_CANONICAL_VISION.md)
- [Architecture, provenance, licensing and future plan](ARCHITECTURE_RFC_2026-11-23.md)
- Future consumer: [QT-MRI #135](https://github.com/ringoincidents/quantrade/issues/135)

## Why

Market research was repeatedly blocked by needing to fetch prices/indicators again. Keep the **authorized original source**, recorded hashes and verified historical availability, then calculate versioned indicators locally, without rebuilding API integration for every project.

## What P0 actually has

- `vault.py`: append-only local SQLite research index for registered **RAW_OHLCV** CSV source batches, SHA-256 checksums, rights attestation and exact verified availability timestamps; as-of snapshots preserve separately published revisions. No remote fetching or corporate-action adjustments yet.
- `indicators.py`: pure deterministic SMA, SMA-seeded EMA, Wilder RSI, Wilder ATR with version and explicit warmup/fallback semantics.
- `cli.py`: offline register/ingest/snapshot commands; no API access, no broker connectivity.
- `test_vault.py`: synthetic tests for licensing fail-closed, no lookahead, revision history, duplicate handling, invalid OHLCV, cross-series isolation and deterministic indicator semantics.
- `ARCHITECTURE_RFC_2026-11-23.md`: P0–P3 plan and differences from existing feature calculations.
- `treasury_pilot.py`: official annual US Treasury XML 2Y/10Y parser; optional private immutable source XML+SHA and sidecar manifest; collector-time index (NOT original historical release time); no-overwrite restore.
- `test_treasury_pilot.py`: additional source parsing, anti-revision, exact-date, SHA-corruption, no-fabricated-PIT and restore tests.
- [2026-11-23 official source result](P1_TREASURY_PILOT_RESULT_2026-11-23.md): GitHub Actions downloaded 2008/2020/2025, **751 observations per maturity** in total and restored 3 temporary archive batches after deleting an ephemeral SQLite database. **29/29 synthetic unit tests PASS**. The raw files were not kept after the CI job.

**No market-history CSV files or bulk third-party copyrighted data belong in this public Git repository.** Keep dataset and SQLite database in a private directory and back it up. Source license rights and first-available timestamps must be established from official evidence; the CLI flags record operator attestations, not independent verification.

## Run tests (Python 3.10+, stdlib only)

```bash
python -m unittest discover -s research/market_data_vault -p 'test_*.py' -v
```

## Example — synthetic/local authorized source ONLY

Place a **lawfully retained private** CSV outside this repository:

```csv
session,open,high,low,close,volume,first_available_at_utc
2026-10-01,100,110,90,105,1000,2026-10-01T21:00:00Z
```

This data is synthetic; market prices above are fabricated purely for software demonstration.

```bash
python research/market_data_vault/cli.py --db /private/path/qt-research.db register \
  --id US:ETF:XYZ:RAW --asset US:ETF:XYZ \
  --provider VerifiedProvider --currency USD --rights-note "local research permission verified"

python research/market_data_vault/cli.py --db /private/path/qt-research.db ingest \
  --id US:ETF:XYZ:RAW --csv /private/path/synthetic.csv \
  --source-uri "local://synthetic" --rights-confirmed \
  --first-availability-verified

python research/market_data_vault/cli.py --db /private/path/qt-research.db snapshot \
  --id US:ETF:XYZ:RAW --asof 2026-10-02T00:00:00Z
```

`--first-availability-verified` may only be set when there is **independent evidence** for first market availability; the example is a fabricated and known mock. Do not use either flag to override a real vendor's license or missing publication metadata.

## Critical restrictions

1. **No long-history factor research before corporate-action/version/quality verification**; the P0 store allows RAW_OHLCV only and split adjustment is not implemented.
2. **No creating VIX from stock closes**, HY OAS from stock closes, or relabeling IG credit spreads as HY.
3. **No importing into production `market_indicators.py` or turning on `PREDICTION_ENABLED`**. That path is explicitly gated under the project's existing vision/code.
4. **No scheduling live collectors**, production deployments or changing trading policy in P0.
5. SHA of imported file is recorded, **but the raw CSV itself must be stored separately**; P0 is not yet a fully recoverable private data lake.
6. Revisions are traceable by first-known timestamp; unknown times are quarantined from verified-only snapshots.

## Official Treasury annual pilot (public UST data; private storage only)

```bash
# First, decide where YOUR persistent private files live and back them up.
python research/market_data_vault/treasury_pilot.py --year 2025 --private-dir /PRIVATE/qt-vault
# To reconstruct a MISSING SQLite index from immutable raw files/sidecars:
python research/market_data_vault/treasury_pilot.py --restore-private-dir /PRIVATE/qt-vault
```

The GitHub Actions pilot uses a temporary runner directory. Its successful download and recovery DOES NOT populate a long-term vault. Historic publication timestamps remain UNKNOWN, so the archived rates cannot be treated as point-in-time verified strategy features until release/vintage validation.

## Next concrete validation

1. Review research PR and synthetic tests (CI), confirm no operational files changed.
2. Obtain legally sourced price history for one market/ETF with corporate-action metadata; verify rights, first known dates, update frequency and checksum stability.
3. Implement immutable raw object snapshots + private backup/restore, then Parquet/DuckDB read path.
4. Reconcile sandbox SMA/EMA/RSI/ATR formulas with existing `FeatureProvider`; preserve old outputs and label calculation differences.
5. Once G0 data source quality passes, reuse in QT-MRI #135 VIX/credit correlation/lead-lag tests.

**Resumption cue:** Before solving another API/historical-price blocker manually, search Issue #137 and the dataset/provider catalog; add missing inputs to the durable vault once, not to a one-off strategy script.
