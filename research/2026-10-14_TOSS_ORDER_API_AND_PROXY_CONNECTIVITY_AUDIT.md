# QuanTrade — Toss Invest Order API & Current Proxy Connectivity Audit

- Audit ID: QT-OPS-2026-10-14-TOSS-ORDER-001
- Date: 2026-10-14 Asia/Seoul
- Type: Broker capability and read-only operational audit
- Status: **ORDER API CONFIRMED BY PRIMARY DOCUMENTATION / LIVE CONNECTIVITY BLOCKED / NO ORDERS PLACED**
- Scope: Public official API specs, main-branch implementation, past GET probe evidence, latest scheduled job summary and error log. No credentials, account metadata, balance, actual broker POST or simulated entitlement claims.
- Domain: QuanTrade / Execution feasibility; does not supersede canonical Private Investment Office vision.

## 1. Answer in one sentence

Toss Securities officially supports **domestic and US equity BUY/SELL order creation, modification, cancellation, order history, buying power, sellable quantity, conditional orders and live order-event WebSocket**, but the current QuanTrade main branch **cannot place any live order** because its order adapter is deliberately unimplemented; **today's portfolio sync is additionally blocked by upstream fixed-IP proxy connection timeout**, before any Toss API call.

## 2. Primary current provider evidence

- Toss official product: https://home.tossinvest.com/ko/open-api
- Toss official OpenAPI guide (observed version v1.2.24, 2026-10-14): https://developers.tossinvest.com/
- Toss Order API reference: https://developers.tossinvest.com/docs/order
- Toss Order Event documentation: https://developers.tossinvest.com/docs/order-event
- Toss official launch announcement (2026-08-26): https://p.tossinvest.com/ko/news-room/detail?id=52615

Official functions:
- `POST /api/v1/orders`: BUY/SELL; LIMIT/MARKET; Korean or US securities; **actual capital-moving operation**.
- `POST /api/v1/orders/{orderId}/modify`, `POST /api/v1/orders/{orderId}/cancel`.
- `GET /api/v1/orders`, `GET /api/v1/orders/{orderId}`, `GET /api/v1/buying-power`, `GET /api/v1/sellable-quantity`, `GET /api/v1/commissions`.
- `POST /api/v1/conditional-orders`: SINGLE / OCO / OTO; conditional triggers still create real orders.
- `personal:order` event channel through `wss://openapi-ws.tossinvest.com/ws/v1`; reconnect requires REST order reconciliation.

Authentication: OAuth2 bearer token, and account-scoped requests also require `X-Tossinvest-Account`. **Toss also requires an allowlisted egress IP**, for REST and WebSocket; non-allowlisted access is 403. Existing Vultr proxy was designed for this purpose.

Official posted fee reference: Korean stock KRX 0.015% (NXT 0.014%), US stocks 0.1% per executed value; US orders with total executed value up to $10 per order have no trading commission, other fees/taxes and currency costs still apply. Never hard-code current economic assumptions without inspecting current fees/venue.

## 3. Existing code audit (main branch)

- `real_portfolio_sync.py`: `PROXY_URL` and Toss Client Credentials via GitHub Secrets; authenticates then GETs accounts, holdings, KRW/USD buying power and currency rate. **Read-only**.
- `runtime_portfolio_sync.py`: checks expected fixed-egress IP, then synchronizes a minimized portfolio snapshot to private Holdings Runtime via GitHub Actions OIDC. **Read-only; not a trading service**.
- `toss_order_endpoint_probe.py`: GET-only orders and sellable quantity diagnostics. Its corresponding historical 2026-08-08/09 report states both returned 200 through the proxy. That does **not** establish order submission permissions.
- `autoexec.py`: `place_sell_order()` raises `OrderLayerUnavailable` unconditionally; `execute()` only allows `sell` and calls that unimplemented seam. No BUY executor. Existing approval handling alone does not result in broker execution. Do not assume main code is ready from historic design texts.
- `.github/workflows/sync_real.yml`: scheduled sync uses `PROXY_URL`, `TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET`; no order POST.

## 4. Current live failure evidence

Two most recent inspected relevant scheduled runs:
- 2026-10-14T05:08:46Z: https://github.com/ringoincidents/quantrade/actions/runs/38515068936 — **failure**
- 2026-10-13T15:10:59Z: https://github.com/ringoincidents/quantrade/actions/runs/38419828557 — **failure**

Verified from job logs: `runtime_portfolio_sync.py -> check_proxy_ip() -> HTTPS GET api.ipify.org through configured Vultr proxy` failed after ~10 seconds with `ConnectTimeoutError` reaching proxy port 3128, cascading to `requests.exceptions.ProxyError`. This is a **proxy reachability failure prior to Toss API authentication**, not evidence of order-endpoint rejection, Toss credentials invalidity, or IP allowlist rejection. Credential status and Toss API responsiveness are unknown until proxy is restored and a fresh read-only probe succeeds.

Potential causes (not proven): server down, proxy daemon stopped/not listening, inbound firewall, route/egress/NAT or credential-protocol configuration. This source does not diagnose Vultr account billing/status.

## 5. Required zero-order recovery checks

1. Check Vultr VM power/billing/status and whether the reserved public IP remained unchanged. Do not post console credentials.
2. Inspect process/service health and listening port; inspect server/host firewall and allowed inbound sources; distinguish timeout vs auth failure. Avoid making an open proxy or removing access controls.
3. Restore fixed-IP path with secrets remaining in GitHub Actions only; test public egress IP from **the same execution environment** and compare against Toss allowlist.
4. Rerun **read-only** `runtime_portfolio_sync.py` or narrower auth/account/order-history GET probe. Verify OAuth, account, GET order history and buying power; record only outcome codes, timestamps, and non-sensitive diagnostics. **No POST order/modify/cancel/conditional order as a connectivity test.**
5. Only after current read-only success, design a standalone `TossExecutionAdapter` behind a disabled feature gate, with typed `OrderIntent`, immutable authorization, max-notional/position limits, broker-side order-state reconciliation, idempotency and timeout handling, stop/cancel propagation, test harness without broker POST.
6. Keep `autoexec.py` fail-closed until separate Risk/Founder/governance approval, end-to-end paper/forward validation, and system operations proof.

## 6. Strategy and product consequences

- Toss Securities is the **preferred evaluation candidate** over Binance for the KR/US equity route because a working historical Toss API integration and an existing proxy are documented. This is a research priority recommendation, **not a broker approval or live-trade mandate**.
- 2026-10-14 Binance research remains historical; never equate Binance stock-product commission economics with Toss.
- Strategy discovery, robust net fee/slippage/tax P&L and paper trading remain necessary; possessing a live order endpoint is not a profitability edge.
- Reconcile with issue #126 (after-cost simulator) and open draft PR #124 (Binance paper simulator) **before** starting overlapping implementation; reuse broker-neutral paper-ledger components but not Binance-specific fees or exchange semantics.
- No live order was attempted, created, cancelled or modified in this audit.

## 7. Live recovery attempt (2026-10-14 ~20:30 KST)

- Authorized scope: re-run existing `Real Portfolio Sync` (GET-only brokerage and OIDC private portfolio snapshot); **no order, no credential rotation, no proxy firewall change, no VM modification**.
- Action actually taken: GitHub `rerun_failed_workflow_run_jobs` succeeded for `run_id=38515068936`.
- New attempt: job `115828335613` **completed FAILURE**. Logs show `urllib3.exceptions.ConnectTimeoutError` to existing Vultr proxy `141.164.41.178:3128` after 10 seconds; `requests.exceptions.ProxyError` raised while fetching `https://api.ipify.org`. OAuth/account/portfolio phase never began.
- Evidence: https://github.com/ringoincidents/quantrade/actions/runs/38515068936
- Observed root boundary: GitHub execution is healthy, external proxy endpoint unreachable. Cannot yet determine whether Vultr VM is powered down, service stopped, firewall blocks inbound, or route/hostname/credentials changed. A connection timeout is **not** proof of a specific root cause.
- Access limitation: Current connected control tools permit GitHub & Railway operations but do **not** expose the user's Vultr instance management or SSH. No attempt to reconstruct credentials, expose secrets or bypass the allowlist is authorized.

### Founder-side minimal unblock (requires Vultr account console)

1. In Vultr's web portal: **Products > Compute**, locate the existing instance matching the configured fixed IP. Check **Running/Stopped**, IPv4 and server/network status.
2. If stopped: start the instance; if running but unresponsive, consider **Server Restart** after confirming the instance is not hosting unrelated critical services. **Do not click Reinstall** (destroys contents). Official references: https://docs.vultr.com/products/compute/instances/cloud-compute/management/restart-instance and https://docs.vultr.com/products/compute/instances/cloud-compute/connection/vultr-console.
3. If still failing, use **View Console** (web-based, works without SSH) to inspect proxy listener/service and local host firewall. Determine actual daemon name before any service restart; TCP port 3128 alone does not prove Squid is installed. Do not expose an unauthenticated open proxy.
4. Once restored, rerun the **GET-only** GitHub Actions `sync_real.yml`; it must verify exact fixed egress IP and successful private-runtime ingestion. Then re-run GET-only order/sellable-quantity probe if needed. **Neither authorizes POST /api/v1/orders.**

### Follow-up criterion

Incident remains **BLOCKED: EXTERNAL VPS ACCESS REQUIRED**, not RESOLVED, until one fresh GET-only sync succeeds and source-of-truth Runtime reflects the new snapshot. No automated retry loop, live order enablement, or fabricated verification.
