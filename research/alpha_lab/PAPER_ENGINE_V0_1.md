# Alpha Lab paper engine v0.1 (isolated proof-of-concept)

- **Status:** `SANDBOX / NO-NETWORK / NO-ORDERS`.
- **Owner:** QuanTrade Alpha Lab; subordinate to `QUANTRADE_CANONICAL_VISION.md`.
- **Scope:** 2026-10-11 Binance Stocks preliminary feasibility, **not** evidence of trade eligibility or profit.
- **Approval:** No live trading permission or credential request; not integrated with existing QuanTrade execution, portfolio, risk or Holdings.
- **Observation:** User's Binance app displays NVDA `Buy`/`Sell` `Market`/`Preview`, `Mkt Closed`, `Min 5.17 USDC`, zero USDC, no orders. This proves order UI only; no account permission or API access confirmed. Screenshot remains private to the chat.

## Purpose

A tiny deterministic simulator to test **friction and fill assumptions** before collecting live-equity data or designing a strategy. Implemented entirely with Python standard library and `Decimal` arithmetic under `quantrade/alpha_lab/paper.py`. Uses no broker credentials, network calls or order submission APIs.

Simulator charges the documented <=350 USD minimum platform fee **0.35 per simulated order** and fills a requested BUY at the best ask, SELL at the best bid, plus a configured slippage stress factor. It rejects closed-session quotes, stale (>5s) quotes, orders below a configured per-symbol minimum notional, orders beyond the fee model tier, unavailable cash and short-selling. Strict client-order-id idempotence works **within the current process only**.

The initial `min_order_notional=5` is a **test fixture**, not NVDA's permanent live minimum. The screenshot happened to show 5.17 USDC; exchange metadata must define live per-symbol minimum and tradability before any live operation. The current model also uses a simple fully-filled-or-rejected assumption — missing real queue placement, partial fill, holiday calendars, corporate actions, margin and order mechanics. This simulator does **not** prove realistic actual brokerage fills or a winning strategy.

## Reproduce

From repository root:

```shell
python -m unittest discover -s tests/alpha_lab -p 'test_*.py' -v
```

Offline unit tests include: round trip 0.70 fee floor plus bid-ask spread, session check, min-notional/cash checks, no shorts, deterministic idempotency, stale quote rejection, unsupported fee tier, input validation and configurable symbol minimum/slippage.

## Prior experiment relation

- Historic `indicator_significance_report.json` identified **no approved alpha**; previous RSI divergence did not survive multiple-test correction.
- Prior [MTF divergence observation](../observations/2026-10-11_MTF_DIVERGENCE_MOMENTUM_HYPOTHESIS.md) is `NOT_VALIDATED`.
- Prior [Binance Stocks feasibility](../2026-10-11_BINANCE_STOCKS_API_FEASIBILITY.md) holds the current product/fee/API constraints.
- This PR creates infrastructure only, not a signal or a production trading system.

## Required follow-up gates

1. Confirm brokerage/jurisdiction eligibility and read-only API access without placing or funding an order.
2. Acquire lawful licensed timestamped intraday US equity historical OHLCV (Binance Stocks documented Market Data API gives exchange info/quotes, not proven downloadable historical bars). Verify time zones, primary/extended session and adjustments.
3. Add `MarketDataProvider` adapter, immutable fixtures, raw provenance and current fee schedule with parameterization per symbol/order type, including spread, slippage and any additional statutory charges.
4. Build a **replay** backtester with no same-bar execution, walk-forward and untouched holdout; compare all three hypotheses with baseline models and costs.
5. Add append-only durable ledger, snapshot/recovery, order state reconciliation, unfilled/partial fills, session calendar, independent risk policy, daily loss stops, failure injection and immediate kill switch **before** a cloud paper worker.
6. Paper-trade long enough to observe varied sessions, monitor discrepancies and costs. Independent risk/committee/human review is a separate decision, not the result of passing unit tests.
7. Only after distinct explicit authorization could a future live adapter be built; **this PR has no such functionality**.

No automatic transfer of this sandbox to live execution is permitted. Never store Binance API keys in GitHub source, docs or test artifacts.
