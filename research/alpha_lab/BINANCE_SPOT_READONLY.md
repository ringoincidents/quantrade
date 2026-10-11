# QuanTrade Binance Spot Read-Only Connector — 2026-10-11

**Status:** SANDBOX / no order authority / not deployed to user's account.
**Budget:** initial 10 USD experiment (actual account asset not verified).
**Scope:** Binance crypto Spot, not Binance Stocks or equity derivatives.
**Owner:** QuanTrade Alpha Lab. No changes to Holdings, approval or execution policy.

## Exact fixed endpoints

Public origin: https://data-api.binance.vision
- GET /api/v3/time
- GET /api/v3/exchangeInfo
- GET /api/v3/ticker/bookTicker
- GET /api/v3/klines

Private origin: https://api.binance.com (requires HMAC key/secret from environment)
- GET /sapi/v1/account/apiRestrictions
- GET /api/v3/account

Every call is GET; the implementation has no order endpoint. Private requests add HMAC SHA256 signature over the exact timestamp/recvWindow query. The account adapter checks for read-only permissions before fetching balances and refuses a key with detected write privileges. HTTP errors must not expose signed URLs or credentials. The client has fixed origins, explicit path allowlist, 8-second timeout, 2MB response cap and strict symbol/interval validation.

## Founder's next secure action

1. Sign in to Binance's own app or website and open Profile/Account > API Management (API).
2. Create a new **System-generated HMAC API key** named QuanTrade-ReadOnly. Complete 2FA in Binance only.
3. Keep **Enable Reading** only. Leave Spot & Margin Trading, Futures, Withdrawals and every other write option **disabled**. Restrict source IP when a stable and verified egress IP exists. Never bypass regional restrictions.
4. Do not paste API key or Secret into ChatGPT, issues, GitHub source, screenshots or chat logs. Put them only into a dedicated private QuanTrade runtime's secret manager as:
    QUANTRADE_BINANCE_API_KEY
    QUANTRADE_BINANCE_API_SECRET
5. On that trusted runtime, execute from the repository root:
    python -m quantrade.connectors.binance_spot_readonly --symbol BTCUSDT
    python -m quantrade.connectors.binance_spot_readonly --symbol BTCUSDT --private

The first command accesses keyless public data. The second checks API permission and prints **non-zero Spot wallet balances** when authentication is genuinely successful. Funds in Binance Stocks, funding wallet or Futures may not appear in the Spot balance response.

## Evidence and limitations

- Binance Spot official docs: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- Public data-only domain: https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
- Official API key creation and security: https://www.binance.com/en/support/faq/detail/360002502072
- On 2026-10-11 public exchangeInfo for BTCUSDT returned status TRADING, NOTIONAL.minNotional=5.00 USDT. This says **nothing** about account eligibility, fill ability, trading fees, or private API connectivity.
- Local automated tests passed for exact GET-only requests, read-only key permission rejection, HMAC, fail-closed argument checks and secret-safe errors. CI uses fixtures, not Binance network.
- The current execution environment cannot itself complete a Binance public network call by Python; online market metadata was verified separately using public documentation access.
- No live credentials supplied, no live exchange account calls, no deployment and **no trade executed**.

## Next gates

Account authenticated GET with user-owned key + controlled hosting; truthful per-symbol minimum order requirements and current fees; auditable historical OHLCV and complete bar semantics; trade-cost-inclusive backtest; paper trading; deterministic stop and persistent reconciliation; and only subsequently an explicit separate live-trading authorization.
