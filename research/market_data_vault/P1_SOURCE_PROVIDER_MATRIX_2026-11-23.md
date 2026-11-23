# Market Data Vault P1 — external source shortlist and licensing decisions (2026-11-23)

**Read with** [Issue #137](https://github.com/ringoincidents/quantrade/issues/137), [P1 Treasury test](P1_TREASURY_PILOT_RESULT_2026-11-23.md) and [QT-MRI Issue #135](https://github.com/ringoincidents/quantrade/issues/135). This is source diligence, NOT a paid subscription or ongoing data-service activation.

## Core finding

A sustainable historical store can own its *ingestion, storage and indicator calculations*; it cannot create market data rights or fabricate official volatility, bond option-adjusted spreads, ex-dates, delistings or point-in-time economic publication vintages.

Publicly viewable **historical files are not automatically reusable, redistributable, or backtest-safe**. Provider source and license must be per-dataset records with a private retained copy only where permitted. Model generated features in a public repo must not permit recovery of copyrighted underlying prices.

## Source decision matrix

| Purpose | Source and link | Availability/benefits verified from provider | Blocking risk / disposition |
|---|---|---|---|
| US 2Y/10Y historical par-yield | [US Treasury official feed](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed) | Official daily par series listed since **1990**. Live 2008/2020/2025 feed+archive+restore pilot **PASSED**, 751 sessions per maturity | **P1 CONNECTED / PERSISTENCE NOT YET DEPLOYED**. Original publication timestamps/vintages still unverified. Par-yield is NOT bond price or all intraday quotes. |
| US implied volatility VIX | [Cboe official historical index page](https://www.cboe.com/tradable_products/vix/vix_historical_data) | VIX EOD series **1990–present** updated daily | **WATCH / LICENSING + RELEASE CLOCK**. Official index values do not entitle reconstruction of VIX from stock closes, nor unrestricted redistribution. Verify personal archive permission. |
| US broad economic series | [FRED/ALFRED API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html) | Rates, many macro series, real-time/vintage endpoints | **WATCH**. Per-series rights, data available from which date vs first release; rolling third-party history truncation (e.g. ICE HY OAS) is a known issue. |
| KOSPI/KOSDAQ/individual KRX cash shares | [KRX OPEN API catalog](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd) and [official API terms](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp) | Official catalog: daily index, stock and ETF from **2010-01-04**. Terms as of 2025-12-26 restrict to **non-commercial use**, prohibit third-party data supply and require attribution; access key application/approval needed, 10k requests/day limit, key term renewal. | **BLOCKED — KEY + TERMS / RETENTION**. No key configured. No automatic collection until access/rights/retention/end of contract reviewed. |
| Alternate Korean index API | [FSC financial-index API at data.go.kr](https://www.data.go.kr/en/data/15094807/openapi.do) | Index dataset starting **2020-01-01**. Provider states next business day after **13:00 KST**, not same-day close; attribution + NC + no derivatives and no third-party data redistribution. | **WATCH** for supplementary KOSPI; less history than KRX and publisher delay. Don't blend this update clock with KRX's separate API. |
| US QQQ/SPY adjusted ETF bars | [Tiingo official EOD API](https://www.tiingo.com/documentation/end-of-day), [terms](https://www.tiingo.com/tos/) | Provider documents both raw and adjusted OHLCV, `adjClose`, `divCash`, `splitFactor`; long history potential | **CANDIDATE / LICENSE + PLAN**. Personal/internal use restrictions, retention and Derived Product/predictive model conditions, generative model/redistribution terms require approval review. Verify actual SPY/QQQ listing start date and access tier. No key/subscription yet. |
| Lower-cost bulk US ETF history | [MarketParquet official pricing](https://marketparquet.com/pricing), [methodology](https://marketparquet.com/data-quality), [license](https://marketparquet.com/ko/license) | Vendor advertises full daily split-adjusted US stock/ETF history since 2000 for **$79 one time** (as checked 2026-11-23) and daily recent free samples | **CANDIDATE / NOT PURCHASED / INDEPENDENT QA REQUIRED**. Self-reported licensed price origin, complex revisions and missing dividend adjustment; requires split/dividend action source and sample-vs-other-vendor parity. Clarify whether future updates and archive retention included. |
| Alpha Vantage adjusted ETF daily bars | [official docs](https://www.alphavantage.co/documentation/) | API offers adjusted time series but `TIME_SERIES_DAILY_ADJUSTED` is labeled **Premium** | **WATCH** if bundled plan needed; no claim free 25-year adjusted daily series. |
| Stooq daily CSV | [Stooq website](https://stooq.com/) | Downloadable EOD for many tickers | **DO NOT USE AS UNVERIFIED PRIMARY**. Automated access limits, adjustment and redistribution rights require audit; not a reliable point-in-time fund total-return source without actions. |

## Prioritized choice without PC or paid subscriptions

**Already green:** build on official US Treasury historical feed and proven private archive/restore method.

**Next unlock (no purchase now):**
- US QQQ/SPY: trial one approved long-history **raw + split/dividend adjusted** provider. Compare Tiingo vs one-time archive vendor with full product/sample data, contract rights, extent and update cost. Do not optimize on missing/delisted names.
- Korean market: individual owner must request and obtain **their own KRX OPEN API key and approval**, or choose a separately licensed provider. Never check any API key into GitHub; encrypt credentials in private secret store only.
- VIX: official Cboe posted daily CSV is ideal source discovery but Cboe license/terms must permit intended private research and retention.
- High-yield OAS: preserve as *licensed*, not reconstructible from ETF bars alone; long 2000–2025 history cannot be silently replaced with Baa credit index.

## Costs / persistence design

Start with private local disk + independently verified backup/restore and low-cost storage where contract allows. Evaluate an encrypted private object store only after byte count and data renewal plan are known. Do **not** provision any paid Railway/R2/S3/Vultr resource without a specific budget and explicit authorization. GitHub PR/Actions' ephemeral runner is not the forever market database; public GitHub should hold only code, hashes, scripts, QA records and explicitly permitted synthetic fixtures.

## Time semantics and labels

For each observation persist:
- market or macro observation timestamp and original event timezone;
- source published time (when substantiated);
- first **collector** observed time (independent of publisher timestamp);
- version/vintage ID and corporate actions;
- source and terms/license scope/expiry;
- adjustment basis and price-versus-total-return identity;
- code version, parameters, input SHA, and data QA.
When historic first publication cannot be proved, **original PIT status = UNKNOWN** and do not claim backtest is fully point-in-time.

## Completion truth

- US Treasury historical connection and disaster-recovery **technical pilot succeeded** for three years, no market forecast/alpha validated.
- A permanent private data lake, long ETF price coverage, Korea API and Cboe license clearance are still **NOT DONE**.
- No orders, deployment, paid purchases or scheduled collectors made.

*Source snapshots are documented leads from official providers where possible; plans/terms and availability can change, so pin and re-check before spending or ingesting.*
