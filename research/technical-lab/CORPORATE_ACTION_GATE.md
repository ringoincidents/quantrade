# Corporate actions and terminal outcome gate — QT-MAR
Status: BLOCKED / research only. This contract is not a populated action ledger.
## Mandatory record
- stable security ID and vendor symbol with validity interval; source identity and immutable evidence URI/hash
- effective session, publication/known timestamp (with offset), extraction timestamp
- event kind: SPLIT, CASH_DIVIDEND, STOCK_DIVIDEND, SPINOFF, CASH_MERGER, STOCK_MERGER, MIXED_MERGER, DELISTING, VERIFIED_MARKET_MOVE, DATA_ERROR, UNKNOWN
- source price basis: RAW, SPLIT_ADJUSTED, TOTAL_RETURN_ADJUSTED, UNKNOWN
- split ratio or cash dividend per share/currency or successor ID, stock ratio and cash consideration, or terminal proceeds; absent fields explicitly unknown
- reviewer, evidence state: UNRESOLVED, VERIFIED, CONFLICT; method, independent source and timestamps; never infer from filename or extreme return alone.
## Fail-closed processing
1. Never overwrite original bytes. Corrections are separate versioned derived files and retain hashes/lineage.
2. Extreme move is not a diagnosis; classify only using contemporaneous evidence plus independently comparable raw prices and corporate action terms. Do not remove confirmed genuine declines. Do not admit unresolved discontinuities into confirmatory runs.
3. Never add dividends or apply split factors a second time to total-return/split-adjusted prices; current snapshot cannot reconstruct precise historical raw OHLC or share-level transactions.
4. Terminal cash or stock proceeds require independently verified effective date and consideration; stock conversion requires successor identity and valuation. Unknown delisting proceeds remain censored and are reported; sensitivity bounds are labelled assumptions, not realized returns. No implicit zero, last-price liquidation, or forward fill.
5. Exchange calendar, security mapping, missing sessions, PIT membership and known-time availability separately audited. Source member table is not announcement history. Exact-date SPY proxy not sector benchmark.
6. Separate holdout by immutable issuer ID, not ticker, before results; shared historic market regime means the current hash-based ticker sample is only a provisional security split. New temporal holdout must be frozen before exposure.
7. G0 remains blocked until independent evidence and end-to-end reconstruction are audited. Negative results preserved. No trading authority.
## Sources and missing fields
PlainBacktest baseline quality report: https://github.com/Sixian-Li/plain-backtest/blob/main/data/processed/universes/sp500/quality_report.md
Candidate review: https://github.com/Sixian-Li/plain-backtest/blob/main/data/processed/universes/sp500/pending_review/quality_report.md
Source explicitly lacks separate cash dividend and split event ledger, historical index weights, and member announcement timing. No independent corporate-action, sector history or terminal payout feed obtained in this session.
