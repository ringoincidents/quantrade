# P1 official source pilot: US Treasury 2Y/10Y, 2008·2020·2025

- Research issue: [Market Data Vault #137](https://github.com/ringoincidents/quantrade/issues/137)
- Draft PR: [#138](https://github.com/ringoincidents/quantrade/pull/138)
- Run (GitHub Actions): https://github.com/ringoincidents/quantrade/actions/runs/45163278028
- Observed: 2026-11-23 11:13–11:14 UTC (2026-11-23 20:13–20:14 KST)
- Official upstream: https://home.treasury.gov/treasury-daily-interest-rate-xml-feed
- Explicit request contract: `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=YYYY`
- Program: `research/market_data_vault/treasury_pilot.py`
- Software tests: **29 / 29 PASS**, as observed in same GitHub Actions run.
- Live official-source pilot: **SUCCESS**, 3 year-specific requests, no authentication, no holdings or orders involved.

## 1. Actual measured ingestion output

| Requested calendar year | UST par 2Y count | UST par 10Y count | First and last returned sessions | Official raw XML SHA256 |
| --- | ---: | ---: | --- | --- |
| 2008 | 251 | 251 | 2008-01-02 — 2008-12-31 | `f6b9f1b731d33616f1ec263a0afde51933ee8e3af9b0061b5fa1a46427712f1d` |
| 2020 | 251 | 251 | 2020-01-02 — 2020-12-31 | `df9c67fdf0399d7adc7127bdaad854147978196f8547f938fc97291433056db5` |
| 2025 | 249 | 249 | 2025-01-02 — 2025-12-31 | `f5fc47ccf34b71ad7101d9796d312a8d176be380698ba5efcb91e1ebd9859abe` |
| TOTAL | **751** | **751** | Three disjoint historical years | Three independently identified versioned source XML payloads |

These are **observations from official source history, not forecast predictions**. There are 1,502 maturity/date pairs, with two maturity points per each of 751 dates; do not confuse this with independent predictive episodes.

## 2. Private archive and disaster recovery pilot

The source files were written to the GitHub runner's **temporary private directory** (outside Git), with:
- source bytes named by SHA-256;
- matching immutable JSON metadata manifest (year, source_url, first collector capture timestamp, hash and byte size);
- a local SQLite catalog indexing both 2Y and 10Y series by observation day and collector timestamp;
- all historical original-publication timestamps **NULL / NOT VERIFIED**.

The CI test then removed only the **temporary** SQLite index and called `restore_private_index` to reconstruct it exclusively from the hashed XML files and sidecar manifests.

**Observed result:** `{"restored_batches": 3, "index_path": ...}`; successful pipeline conclusion.

What this proves: actual upstream download → schema parse → source archive → snapshot index → delete ephemeral index → hash-verified restore can work, on this three-year sample.

What this DOES NOT prove:
- The source snapshots remain available after the runner's lifetime. **No permanent private storage is connected.** Source manifest and hashes are stored in this summary only; raw data was not committed or uploaded to any long-term repository.
- We have independently reconstructed the **first historical time each 2008/2020/2025 rate was publicly available**. These are archive downloads from 2026; a backtest treating observation date itself as real release instant would leak data.
- We possess intraday Treasury observations, real-time quotes, corporate actions, SPY/QQQ ETF bars or KRX licensed data.
- Numeric forward-return prediction, alpha validation, 10,000 Monte Carlo scenarios or trading permissions.

## 3. Tool behavior and safeguards

- Only official `home.treasury.gov` HTTPS endpoint and redirect host accepted; non-official redirect rejected.
- One year explicitly requested per call; reads capped at 4 MB; missing maturity skipped (not zero-filled), duplicate observation date errors, invalid dates or implausible yields cause failure.
- No private client identifiers or KRX key used. Raw third-party price data never enters public Git.
- Original-source rights/price source legal terms are not modified by caching technology.
- 29 synthetic unit tests validate licensing/no-lookahead/indicator formula and Treasury source parsing/recovery. This is software correctness evidence only.

## 4. Next tasks: do not confuse completed slice with a durable data lake

**Completed:** three real Treasury official-year data source connections and ephemeral raw+database restoration; validated code in draft PR.

**Required next:**
1. Choose **persistent private storage**, encryption/key management as appropriate, and at least two independent backups; demonstrate restore from a different environment. No permanent storage selected or paid for.
2. Obtain an authorized **US ETF EOD raw/split/dividend history** with clear vendor contracts; QQQ/SPY 2000+ and corporate actions. ETF price history and Treasury rates are different data types; do not force Treasury rate values into an OHLCV schema.
3. Obtain KRX approved API key and data-use authorization for KOSPI after reviewing official terms. Never place key in GitHub/source.
4. Confirm first-publication time, revisions, disclosure and backtest-ready as-of-vintage for each source. For historical Treasury values, collector-date capture is **NOT** original PIT.
5. Complete source quality checks across gaps, market calendars, price adjustments, rollback and repeat-year checksum differences. Then, if warranted, full 2000–2025 backfill using rate-limited annual requests after storage is ready.

## 5. Reproducibility command (private local PC/runner only)

```bash
python -m unittest discover -s research/market_data_vault -p 'test_*.py' -v
python research/market_data_vault/treasury_pilot.py --year 2008 --private-dir /PRIVATE/qt-vault
python research/market_data_vault/treasury_pilot.py --year 2020 --private-dir /PRIVATE/qt-vault
python research/market_data_vault/treasury_pilot.py --year 2025 --private-dir /PRIVATE/qt-vault
# Only if the private SQLite index is ABSENT, do not overwrite:
python research/market_data_vault/treasury_pilot.py --restore-private-dir /PRIVATE/qt-vault
```

All path examples are placeholders. Do not put the private directory under a public repository. The restore command intentionally refuses an existing SQLite DB.

## 6. Source-verification and target identity

Treasury's **daily par yield curve** is not necessarily the same publication as every intraday quoted Treasury yield or 10-year futures. `UST_PAR_10Y` and `UST_PAR_2Y` are the explicitly named source series; do not silently equate the output to generic `DGS10` or an ETF's returns.

This record is an append-only provenance for future research, not a claim of statistical market-edge discovery.
