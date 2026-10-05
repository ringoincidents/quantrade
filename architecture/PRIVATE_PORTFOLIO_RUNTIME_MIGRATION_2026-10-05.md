# Private Portfolio Runtime Migration — 2026-10-05

Status: **CURRENT IMPLEMENTATION BOUNDARY**

QuanTrade's scheduled real-account observation is migrating from public-repository persistence to the private LLM Holdings Runtime.

## Current target

```text
Toss Open API (read-only)
→ sync_real.yml
→ runtime_portfolio_sync.py
→ short-lived GitHub Actions OIDC
→ LLM Holdings private QuanTradePortfolioSnapshot
```

The workflow does not place orders.

## Public repository boundary

This public repository may retain:

- broker-provider code;
- schemas and tests;
- sanitized research/experiments;
- historical implementation code.

It must not be the current persistence layer for:

- real holdings snapshots;
- current valuation P&L history;
- current portfolio reports derived from private holdings;
- current post-trade review logs derived from private holdings.

TASK-101 removes those live artifacts from the current branch and ignores them going forward. This does **not** rewrite Git history.

## Retired scheduled consumers

The old weekly portfolio-report and daily post-trade-review workflows depended on `real_portfolio.json` being current in this repository.

They are retired from scheduled operation rather than silently consuming stale public data.

Their calculation code remains historical/research material until equivalent private Runtime-native Performance & Learning paths are implemented.

## Authentication

The Runtime accepts the sync only from the exact `sync_real.yml@main` GitHub Actions identity using audience:

`llm-holdings-quantrade-portfolio-sync`

The short-lived OIDC token is used only in transit and is never persisted.

## Authority

This migration changes storage/authentication only.

It grants no investment approval, order placement, broker mutation or capital movement.
