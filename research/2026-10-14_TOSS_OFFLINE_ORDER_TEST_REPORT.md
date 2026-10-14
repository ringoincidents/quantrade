# QuanTrade: Toss Securities offline order-contract test (14 October 2026)

- Record ID: QT-TEST-2026-10-14-TOSS-OFFLINE-001
- Status: **LOCAL TEST PASS / PR VALIDATION PENDING / ZERO BROKER ORDERS**
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
