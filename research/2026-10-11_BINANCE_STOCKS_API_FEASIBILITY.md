# QuanTrade Alpha Lab — Binance Stocks API Feasibility & 500,000 KRW Pilot

- Record ID: QT-RSCH-2026-10-11-BINANCE-EQUITY-001
- Date: 2026-10-11 (Asia/Seoul)
- Status: RESEARCH / PREFLIGHT ONLY / NOT VALIDATED / NOT DEPLOYED
- Priority: Phase 0 precondition for Alpha Bot v0.1
- Supersession: Alters initial Korean-equity broker assumption for this experiment, but does not supersede `QUANTRADE_CANONICAL_VISION.md`
- Source: Founder requests Binance API instead of prioritizing KIS; initial experiment capital 500,000 KRW, ultimate objective conditional fully automated intraday trading; current stage research/backtest/paper only.
- Authority: Research; no keys, no live orders, no permission change, no leverage.

## 1. Verified product routes (official Binance documentation, checked 2026-10-11)

1. **Binance Stocks (traditional US equities/ETFs)**: Binance announced US stocks trading via REST API on 2026-07-20. Nest Trading Limited introduces, with Alpaca Securities LLC as clearing/execution/custody. Binance official FAQ states users are beneficial owners of stock held with partner broker. Eligible locations/account status only. The documented endpoint `GET /sapi/v1/equity/market/exchangeInfo` queries tradable US equities; quote `GET /sapi/v1/equity/market/... ` can be used for quote discovery; order placement `POST /sapi/v1/equity/order/place` is signed and disallowed in Phase 0/1/2. Stocks API order lifecycle acknowledgements are not equivalent to filled orders.
2. **bStocks**: Binance spot lists e.g. AAPLB/USDT; bStocks are certificates referencing underlying shares, not direct ownership. Its legal issuer and jurisdiction restrictions differ from Binance Stocks. Do not mislabel bStocks as common stock nor infer that product access follows from ordinary Spot permission.
3. **Equity perpetuals**: AAPLUSDT, TSLAUSDT etc are derivatives with leverage/funding/liquidation features, not stock ownership. **Excluded from the 500k-KRW pilot**.
4. **Crypto Spot**: possible fallback research market for testing the research/simulation platform, but no automatic transfer of alpha/validation to the equity domain.

Official primary sources:
- Binance Stocks API announcement: https://www.binance.com/en/support/announcement/detail/95d746cb2b5e4d179c50d0026dd7dfbe
- Binance Stocks FAQ, updated 2026-10-05: https://www.binance.com/en/support/faq/detail/a7469c7703524024b5bc2d492b03639d
- Binance Stocks market data API: https://developers.binance.com/en/docs/catalog/advanced-trading-stocks-trading/api/rest-api/market-data
- Binance Stocks trade API: https://developers.binance.com/en/docs/catalog/advanced-trading-stocks-trading/api/rest-api/trade
- bStocks example / ownership restrictions: https://www.binance.com/en/support/announcement/detail/fd3c0f17a7504eb5be1cb1911c6da0cd
- Equity perpetuals example: https://www.binance.com/en/support/announcement/detail/4cde981dc32d4268b7645e9d16e8d63a

## 2. Critical constraints for small-capital intraday trading

### Account/jurisdiction gate

- Official docs warn Binance Stocks is not available to all jurisdictions; availability for THIS Korea-based user's verified account is **unconfirmed**.
- Only user can confirm `Trade > Stocks` in app or supported account eligibility, terms, and relevant jurisdiction. No VPN/identity/geofence workaround.
- Even public market-data endpoints can require an API key. No API key is needed to complete research documentation. Avoid requesting or exposing credentials in chats or GitHub.

### Transaction costs

Official Binance Stocks FAQ as of 2026-10-05:
- Up to and including **350 USD notional per order**, minimum **0.35 USD platform fee per order**.
- Above 350 USD, described **0.1% spread** (rounded to 2 decimals) in place of minimum platform fee; other costs may apply.
- Illustrative **100 USDC buy + 100 USDC sell** cost floor: `0.35+0.35=0.70 USDC`, approximately **0.7% of a 100 USDC round-trip position** before any market spread, slippage, conversion, taxes and other costs.
- At 175 USDC trade value, minimum platform fee pair = 0.70 USDC ≈ 0.4% of notional. This makes high-frequency small-ticket scalp strategies structurally challenging.
- Fees can change: query/display current checkout fee and effective spreads; use actual orders' fee records when available.

### Market hours / execution

- Binance Stocks has up-to-24/5 eligible US equities, NOT a universal 24/7 spot-stock market. Market orders only actively execute during US regular trading hours; extended/overnight supported on select stocks with order type/session rules.
- Stocks trading API has instrument tradability/session/fractional/min-notional fields.
- Stock prices, stock tokens, crypto, equity futures use different trading calendars, data definitions and risk models. Keep adapters split.

### Data gap

- The reviewed official `Stocks Trading REST API > Market Data` reference enumerates `exchangeInfo`, `tokenized-assets`, `Latest Quote`; a native historical 1m/5m OHLCV interface was **not confirmed** in this category. Stock app visually showing candles does not prove third-party API historical data access. Before backtesting, find legitimately licensed historical intraday US stock OHLCV + corporate actions + sessions and bar adjustment semantics from a valid data provider.
- For 5-minute models, quote-only historical data is inadequate; no fabricated candles.

## 3. Plan and success/failure gates

### Phase 0: zero-order feasibility, **BLOCKING**

1. Verify available Binance Stocks product and eligibility on user account (no assumption of KR eligibility).
2. Confirm relevant asset universe, order types, typical quote spread, 5m market data history availability, API rate limits, and permitted data use.
3. Implement deterministic round-trip fee floor model and compare expected edge; reject strategies whose target profit cannot plausibly beat floor + spread/slippage/taxes.
4. Specify read-only credentials and least-privilege deployment/IP allowlisting if actually needed later; never use live trading permissions during preflight.

### Phase 1: replayable research harness

- `MarketDataProvider`: timestamped OHLCV + optional NBBO bid/ask; adjusted vs raw and session source documented.
- `FeatureProvider`: reuse `quantrade/capabilities/features.py` seam; do not use indicator observations as evidence or capital authority.
- `SignalStrategy`: deterministic and versioned. Start with trend breakout, VWAP mean reversion, MTF confirmation hypotheses; **comparison only**.
- `BacktestSimulator`: next executable event, no same-bar fills, fee floor per order, realistic spread/slippage, cash/pending-orders, market session gate, non-tradable/unfilled constraints, corporate actions.
- Metrics: trades, gross/net, turnover, hit-rate, profit factor, exposure/time, max DD, cost attribution, walk-forward OOS, regime splits, bootstrap interval, comparison versus buy&hold/flat/matched events.
- No evidence of alpha yet; prior failed `indicator_significance_report.json` (including RSI divergence) is an explicit precedent.

### Phase 2: paper-only execution loop

- Simulated USD/USDC account equivalent of starting 500,000 KRW; FX marked explicitly, no promise fixed USD notional.
- Defined market session; risk sandbox proposed cap 250,000 KRW notional per trade, 1 position, 2,500 KRW planned per-trade risk and 5,000 KRW daily stop **not guaranteed losses**.
- Durable events, idempotent `clientOrderId`, order lifecycle, partial fills, network-failure injection, kill switch, mobile read-only status.
- Production API `POST /sapi/v1/equity/order/place` inaccessible in this phase.

### Phase 3: committee/risk/Founder decision only

- No automatic promotion. Review large enough untouched forward results, paper performance over multiple regimes, fee sensitivity, connectivity/restart recovery, legal eligibility, reconciliation, worst-case loss.
- Failure => abandon/modify hypothesis with append-only record. Success => propose micro-live; new explicit approval + new limited-scope keys needed.
- Live fully automated execution may occur only after independent risk/authorization and operations tests pass.

## 4. Decisions and no-go items

- `Binance Stocks` is **candidate provider, not approved live broker**.
- `bStocks` and `Equity Perpetuals` are **not an interchangeable fallback** when Stocks unavailable.
- Blocking question to Founder: Does `Trade > Stocks` actually appear, and can product detail be accessed on verified Binance account from their jurisdiction?
- No live API keys, no orders, no margin, no tokenized equity purchases, no capital movement authorized by this report.

## 5. Architecture

```text
Binance Stocks official API (eligible account only)
    -> StocksMarketDataAdapter (read-only)
Licensed 1m/5m OHLCV Provider (if distinct)
    -> NormalizedBarStore (with provenance/session semantics)
    -> Native FeatureProvider and versioned strategy candidates
    -> Fee-aware ReplaySimulator -> OOS evaluation -> Paper simulator
    -> Research report / Risk opinion / Founder approval gate
    -> (future ONLY) separate credentialed ExecutionAdapter
```

Under no circumstance use classic crypto spot `/api/v3/order` as a substitute for Binance Stocks equity `/sapi/v1/equity/order/place`; nor mistake bStocks trading pair tickers for traditional stock symbols.
