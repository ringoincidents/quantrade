# QT-LIVE-001 — Binance Paper Trading Lab

Date: 2026-10-03  
Status: EXPERIMENT / PAPER ONLY

## Mission

Use approximately USD 30 of notional paper capital to establish QuanTrade's first reusable live-market trading laboratory without authorizing real orders.

The experiment optimizes for **learning quality and durable institutional memory**, not short-term profit claims.

## Permanent design rule

> Knowledge may transfer across markets. Validation does not.

A result observed on Binance must never be promoted directly to Upbit, Toss Securities, or another venue/asset class. A transferred idea re-enters validation under the target market's own fees, liquidity, currency, session structure, microstructure, data quality, and execution constraints.

## Scope

Initial market:
- asset class: CRYPTO
- venue: BINANCE_SPOT
- symbols: BTCUSDT first; ETHUSDT may be added later
- mode: PAPER
- starting paper capital: USD 30
- leverage: none
- shorting: disabled
- authenticated trading API: disabled
- withdrawal permission: not applicable / never required

## Core durable objects

### StrategyPassport

A strategy hypothesis carries explicit validation scopes. It may be:
- EXPERIMENT_ONLY
- PAPER_VALIDATED
- MICRO_LIVE_VALIDATED
- REJECTED

Validation is tied to a MarketScope. A passport cannot treat a result from one scope as proof in another.

### MarketScope

Required fields:
- asset_class
- venue
- universe
- quote_currency
- timeframe
- period or observation boundary when applicable

### MarketTransferGate

Transfer classifications:
- SAME_SCOPE_REVALIDATE
- SAME_ASSET_CLASS_NEW_VENUE
- NEW_ASSET_CLASS_FULL_VALIDATION

Even SAME_SCOPE_REVALIDATE does not mean "already valid"; it only means the adaptation burden is lower.

### TradeEpisode

Every simulated or real execution episode preserves:
- strategy id
- scope / venue / symbol
- signal and decision timestamps
- decision price
- requested notional / quantity
- simulated fill
- fee assumption
- slippage assumption
- exit reason
- gross and net P&L when closed
- provenance

### TradingFloorSnapshot

A read model for the LLM Holdings QuanTrade Trading Floor. It is projection-only and never becomes execution authority.

## First baseline

The initial paper lab starts with:
1. a USD 30 cash account,
2. a buy-and-hold BTC benchmark seeded from a source-stamped observed market price,
3. an experimental trend-control strategy that remains unvalidated until enough bars exist,
4. no real order placement.

The first purpose is to prove the data -> decision -> episode -> snapshot -> later outcome loop.

## Binance adapter

The first provider uses Binance public Spot market-data endpoints only:
- `GET /api/v3/ticker/price`
- `GET /api/v3/klines`

No API key or account credential is required for this first slice. Authenticated account/order integration is explicitly deferred.

## Transfer policy examples

### Binance BTC/USDT -> Upbit BTC/KRW
Portable:
- hypothesis
- testing method
- logging schema
- position/risk methodology
- failure modes

Must be revalidated:
- signal performance
- fee/slippage assumptions
- KRW quote effects
- venue liquidity/microstructure
- minimum order / tick rules
- execution timing

### Binance crypto -> Toss US/KR equities
Only the hypothesis and research method transfer by default.

Full validation is required because sessions, corporate actions, gaps, fundamentals, FX, taxation, liquidity and execution mechanics differ materially.

## Acceptance criteria

- paper mode cannot place a real order
- Binance public market data is behind an adapter
- StrategyPassport records scope explicitly
- MarketTransferGate never auto-promotes validation across venues/asset classes
- benchmark and strategy state can be projected as a TradingFloorSnapshot
- TradeEpisode preserves execution assumptions
- initial USD 30 paper snapshot is source/provenance stamped
- deterministic tests pass
- no API key or secret is persisted

## Deferred

- authenticated Binance account balance/order API
- Binance Spot Testnet authenticated orders
- real-money micro-live capital
- Upbit adapter
- Toss adapter
- automatic strategy promotion
- unattended real trading
