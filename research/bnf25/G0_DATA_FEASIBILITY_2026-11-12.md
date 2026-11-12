# QT-R001 — BNF25 G0 data feasibility review

**As-of:** 2026-11-12 KST  
**Status:** SOURCE_FEASIBLE / LICENSED_DATA_NOT_ACQUIRED / G0_BLOCKED  
**Authority:** RESEARCH ONLY / PAPER-ONLY / NO ORDER PERMISSION

## Decision
A 10-year, non-survivor-biased S&P 500 mean-reversion study is technically feasible with historical index constituents and delisted-stock data, but **there is no verified accessible licensed dataset snapshot yet**. A free current-constituents backtest must not be portrayed as scientific evidence. Avoid collecting client holdings/identifiable client data in this public branch.

## Vendor capability findings (documentation checked Nov 12, 2026)

| Route | Evidence | Required qualification | Disposition |
|---|---|---|---|
| Norgate Data US Stocks Platinum/Diamond | Historical $SPX membership indicated from March 1957, with historical constituent flags accessible to supported integration environments | Confirm license, US equities including delisted, membership as-of semantics, adjusted and raw OHLCV, Python/local runtime support | **Preferred source for official S&P 500 event study** |
| QuantConnect LEAN, ETF Universe('SPY') | Daily US ETF constituents since Jan 2015, equities and security master corporate-action feed | **SPY holdings proxy**, NOT official S&P 500 historical constituents; underlying equity data and local downloads have licensing/subscription conditions; ETF constituents may be **delayed up to one week** | PILOT ONLY, with observed-at timing and lag audit |
| WRDS/CRSP + separate point-in-time membership file | Permanent identifiers, delisting/merger returns and long history | Institutional data access, CRSP alone cannot establish historical S&P index membership; separate index membership needed | ALTERNATIVE if available |
| Current 2026 S&P 500 constituents + freely downloaded bars | Convenient for code prototyping | Retrospective survivor selection and often incomplete delisting recoveries | REJECT as inferential dataset |

Documentation:
- https://norgatedata.com/data-content-tables.php
- https://norgatedata.com/data-package-faq.php
- https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-etf-constituents
- https://www.quantconnect.com/docs/v2/lean-cli/datasets/quantconnect/us-etf-constituents
- https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-equity-security-master
- https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/etf-constituents-universes

## Data contract for the proposed engine

Input files must remain private when license requires:
- `manifest.json`: vendor, snapshot UTC, content hashes, PIT source kind, vendor's publication-time policy, split adjustment method, license provenance and delisting coverage.
- `prices.csv`: permanent security ID, NYSE session date, raw open/high/low/close/volume, causally split-adjusted signal close.
- `membership.csv`: permanent ID, `valid_from`, exclusive `valid_to`, independent `available_at` timestamp. Unknown observed-at times prohibit claiming point-in-time causal signals.
- `corporate_actions.csv`: splits, dividends, mergers, delisting cash payments, unresolved recovery events.
- `spy.csv`, `vix.csv`: market-matched benchmark and observed-at volatility regime.

At minimum cover 2016-11-11 to 2026-11-11 and ≥252 prior US trading sessions for indicators. Sample PIT membership audit dates: 2016-11-11, 2020-03-16, 2022-06-13, 2026-11-11. Cross-check historical deleted/delisted names and their actual recoveries. The first G0 check is schema/provenance/hash only; G1 then validates actual daily bars, corporate actions, universe availability and timing with independent examples.

**Critical risk:** The mere effective date of an index change is NOT a guarantee that a retrospective data file was available at the time. The QuantConnect dataset may lag by one week, so do not reuse same-day retrospective ETF holdings as known information. Never use future split/dividend factors to create tradable fill prices.

## Fixed research settings
- Primary pre-registered hypothesis: threshold -15% of SMA25, hold 3 NYSE sessions, compare net stock vs matched SPY, aggregate per signal date.
- Exploratory grid: thresholds -5/-10/-15/-20% × holds 1/3/5/10 sessions.
- Signal t close; entry t+1 regular open; exit t+h close.
- One-way fees/slippage 2/5/20bps; vendor corporate actions and delisting recovery required.
- Market trend SPY close versus SMA200; VIX under 20 / 20–25 / over 25.
- Discovery 2016–2022, validation 2023–2024, locked test 2025–2026.
- Research gate **does not imply trading authority**, per QUANTRADE_CANONICAL_VISION.md.

## Current gate and next actions

`SOURCE_FEASIBLE / G0_BLOCKED`: no licensed PIT member, price, merger/delisting-cashflow snapshot acquired or source-level independently checked. Obtain one authorized dataset route; run private data-contract checks, then G1 sample 5 random constituents and 5 delisting/merger events; only then implement/execute event study. The locally tested offline G0 validator and synthetic tests are separate downloadable working artifacts until reviewed and ported into the repository. **No real returns or strategy performance were calculated.**
