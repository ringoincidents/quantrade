# QuanTrade: Toss Securities offline order-contract test (14 October 2026)

- Record ID: QT-TEST-2026-10-14-TOSS-OFFLINE-001
- Status: **PR CI VERIFIED (20 / 20) / REAL READ-ONLY API PREFLIGHT VERIFIED / ZERO BROKER ORDERS**
- Scope: isolated Research/Paper provider, NOT autoexec.py production execution
- Precedent: [Toss order/API proxy audit](2026-10-14_TOSS_ORDER_API_AND_PROXY_CONNECTIVITY_AUDIT.md), [QuanTrade canonical vision](../QUANTRADE_CANONICAL_VISION.md), [Execution Capability Provider contract](../architecture/TRADING_CAPABILITY_PROVIDER_CONTRACT.md), issue #126.

## Distinguish three claims

1. API capability: Toss publishes POST /api/v1/orders for KR/US equity order creation. This is a real capital-moving endpoint, **not invoked by this implementation**. Official index: https://developers.tossinvest.com/ . Earlier full fields were sourced from a third-party v1.2.9 mirror in 토스_주문API_스펙조사_2026-08-05.md, so request-body fields must be cross-checked with current first-party schema before any production adapter.
2. Read-only connectivity: following a Founder Vultr restart, GitHub Actions workflow run #38515068936 (2026-10-14 20:38 KST) confirmed fixed IP, OAuth/GET and private Holdings Runtime ingestion. This does **not** prove order-scoped permission, live fill or trading reliability.
3. Order testing: quantrade/capabilities/toss_order_dryrun.py constructs order-shaped payloads and **only** simulates in-memory lifecycle; it does not import network libraries or account helpers and cannot send POST. Fictional test inputs are not real instruments or balances.

## Test record

Local interpreter Python 3.13.5: python -m unittest discover -s tests/capabilities -p 'test_toss_order_dryrun.py' -v → **14 passed, 0 failed**. GitHub CI proof must be attached to PR before any merge/verification claim; no assumption that local tests imply deployment readiness.

Tested: body mapping, KR & US ticker convention, LIMIT/MARKET, malformed/negative/NaN/fractional quantity rejection, kill switch, simulated approval requirement, market closed and quote stale/future rejection, synthetic buying-power/holding/cap checks, preview with no effect, client order ID idempotency and conflict, PARTIAL_FILLED/FILLED/CANCELED transitions and filled quantity retention, rejected overfill, code static no-network guard.

## Limitations and stop conditions

- 100% **synthetic** account, cash and prices; tests do not call Toss or the fixed-IP proxy.
- No real OAuth token, account header, buy/sell/order history POST, or websocket used.
- Not a tradable strategy. It does not compute executable live prices, real bid/ask, spread, slippage, order fee/tax or timezone-specific session eligibility.
- No persistent ledger; in-memory idempotency resets on crash; a Toss idempotency window is not a substitute for durable reconciliation.
- No real risk approval, authority signature, loss-stop enforcement, disaster restart proof or order state recovery.
- autoexec.place_sell_order remains intentionally unimplemented/fail-closed. No live-enable switch is added.

## Next gated work

1. Verify official current order request/response schema and user-specific trade eligibility without submitting a broker POST. Existing GET-only order-history probe can be rerun when useful.
2. Add durable paper ledger, matched order lifecycle/fees, restarts, mock ambiguous timeout handling and broker-neutral backtester; reuse relevant components of PR #124 without copying Binance fees.
3. Separate actual execution process from public GitHub Actions; add independent Risk + Founder-governed order authority and persistent kill switch, holdings reconciliation, and fail-closed outage handling.
4. Seek a new explicit narrow live-order authorization for a named instrument, side, quantity, order type, limit price, maximum loss/budget and allowed window only after prior safety gates pass. Do not interpret "test" as blanket capital movement approval.


## 2026-10-15 first-party fractional order reconciliation + live GET verification

- Source-of-truth: Toss Securities official server-owned OpenAPI 3.1 spec **v1.2.24**, https://openapi.tossinvest.com/openapi-docs/latest/openapi.json (retrieved 2026-10-15). OrderCreateQuantityBased expressly permits `quantity` with **up to six decimal places** exclusively for `US + MARKET + SELL`. Fractional quantity orders are accepted only from the opening of US regular hours until one hour before the regular close. No fractional BUY quantity / LIMIT sell. Source example uses AAPL, SELL, MARKET, quantity 0.5.
- Previous text and code incorrectly stated **all fractional quantities unsupported**; corrected the standalone offline contract, not `autoexec.py`.
- Public test scenarios use **fictional AAPL fractional quantities**; real client position size and account identifiers are not stored in GitHub.
- Tests now cover fractional SELL, scale >6 rejection, MARKET-only, SELL-only, US-only, seasonal New York clock boundary, insufficient synthetic inventory and full paper fill. **20 / 20 passed** independently in GitHub Actions (see PR #127 workflow results).
- User authorized safe feasibility experiment. We additionally executed a **read-only actual-account diagnostic** using the previously configured GitHub Actions → Vultr fixed-egress proxy → Toss OAuth + `GET /api/v1/accounts`, `GET /api/v1/holdings`, `GET /api/v1/sellable-quantity?symbol=AAPL`, `GET /api/v1/orders?status=OPEN`. Workflow run https://github.com/ringoincidents/quantrade/actions/runs/38712284664 **SUCCESS** (2026-10-15T09:21:19Z), coarse-grained outcome: AAPL fractional holding within supported precision exists, available quantity covers the position, no pending AAPL SELL order.
- Read-only evidence makes account/access feasibility stronger but **does not prove live order POST entitlement or execution/settlement**. No SELL was submitted and no order scheduled.
- Gate outcome: `OFFLINE_CONTRACT_PASS`, `LIVE_GET_PASS`, `LIVE_POST_NOT_ATTEMPTED`, `LIVE_ORDER_NOT_AUTHORIZED_BY_THIS_STUDY`.
- Next test must be a separately guarded live execution path, with live account state recheck, max-size cap, day/session validation, broker acknowledgement handling, idempotency >10-minute replay safety, timeout/fill reconciliation, durable audit, kill switch and explicit narrow order authorization; no CI success promotes capital permission.
