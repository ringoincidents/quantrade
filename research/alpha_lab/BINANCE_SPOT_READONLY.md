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


## Railway provisioning attempt and free fallback (2026-10-11 KST)

The Founder approved a dedicated Railway QuanTrade read-only worker. The actual `create_project(name="quantrade-alpha-readonly")` call was **blocked by Railway** with:

`Free plan resource provision limit exceeded. Please upgrade to provision more resources!`

Therefore **no new Railway project or service exists** and no additional Railway deployment costs were incurred. Existing Holdings services remain unchanged. Do not imply the Founder has a deployed Binance worker.

**Free, reversible fallback: GitHub Actions manual read-only probe.** A workflow `.github/workflows/binance_spot_manual_connection.yml` has been added on the **draft PR branch only**, with `workflow_dispatch` and GitHub repository secrets. No private keys are supplied or stored by the assistant. It needs review/merge to the default branch before manual UI dispatch is available.

Only after manual PR approval and merge:
1. Open `https://github.com/ringoincidents/quantrade/settings/secrets/actions` while signed in as repository administrator.
2. Add two **Actions repository secrets** named `QUANTRADE_BINANCE_API_KEY` and `QUANTRADE_BINANCE_API_SECRET` using the dedicated read-only Binance key. Do not put them in GitHub Variables, chat, commits or issue text.
3. Open repository **Actions**, choose **QuanTrade Binance Spot Manual Read-Only Connection Check**, click **Run workflow**.
4. The workflow prints **only** `public_data: OK/FAILED`, `private_account: VERIFIED_READ_ONLY/FAILED` and `orders_enabled: false`; it does not print asset balances, API keys or signatures. It never creates orders.
5. Failure may result from Binance jurisdiction/account eligibility, GitHub-hosted runner IP restrictions or clock/network drift. Never evade Binance location/IP restrictions as a fix.

This fallback is **not an always-on bot** and does **not** provide a fixed public IP for trading permissions. If the Founder specifically wants dedicated Railway execution, they must authorize a paid Railway plan or wait for resources to be freed; no upgrade has been performed.
