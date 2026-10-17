# QT-STRAT-2026-10-17-SOXL-YEAR-END-001 — SOXL year-end semiconductor rebound research

- Record date: 2026-10-17 (Asia/Seoul)
- Type: EXPERIMENT / Research Case / Strategy Memory candidate
- Status: PROPOSED — NOT VALIDATED — NO LIVE ORDER AUTHORITY
- Scope: October–December 2026 tactical entry/exit research; reusable framework for future years
- Independence: Research proposes hypotheses only. Portfolio, independent Risk, Committee, and Execution remain separate per QUANTRADE_CANONICAL_VISION.md.
- Privacy: This public record contains no client balances, holdings, trading credentials, or personal mandate details.

## Origin and falsifiable thesis

Hypothesis supplied by the Client: Following a steep semiconductor selloff in October, confirmation of a bottom and a subsequent November–December rally may allow a concentrated tactical long position in SOXL, liquidated before January 2027.

Research correction: true bottoms cannot be identified contemporaneously. What can be tested is whether **observable at-time-t reversal / trend / volatility signals** have positive *out-of-sample after-cost* value.

The thesis is NOT a trade recommendation or evidence of positive expected returns.

## Claim ledger (separate evidence from extrapolation)

| Claim | Evidence | Counter-evidence / transfer limit | Status |
|---|---|---|---|
| H1 November–April has historically been stronger than May–October | Bouman & Jacobsen (2002); Jacobsen et al. (2021) global historical research | Dichtl & Drobetz (2015) found seasonal edge weakened/disappeared in investable periods with bootstrap controls; November–April != SOXL October–December | CONTESTED; SOXL-specific evidence NOT VERIFIED |
| H2 sharp falls can lead to short-term reversals | Lehmann (1990), weekly individual equities | Moskowitz, Ooi & Pedersen (2012) document medium-term futures time-series momentum; time horizons and assets differ | PLAUSIBLE, untested for SOXL |
| H3 leverage helps in smooth persistent trends, can suffer in oscillating paths | Avellaneda & Zhang (2010); Direxion 2026 prospectus | LETF performance is path-dependent and leverage can lead to very large/total loss; 2025 preprint emphasizes autocorrelation nuance | STRUCTURAL, not entry alpha |
| H4 volatility-adaptive sizing can improve risk-adjusted outcomes | Moreira & Muir (2017) factor-volatility management | Evidence is not a direct SOXL signal or proof that larger absolute exposure is optimal | RESEARCH CANDIDATE |
| H5 trailing / state-based stop exits beat fixed year-end liquidation | Kaminski & Lo (2014) show stop benefit depends on underlying dynamics | Stop rules can reduce expected returns in random walk settings; gaps/slippage matter | CONTESTED, must test |

## Source library: primary and adversarial

1. Bouman, S. & Jacobsen, B. (2002). The Halloween Indicator, 'Sell in May and Go Away': Another Puzzle. American Economic Review. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=300700
2. Jacobsen et al. (2021). The Halloween indicator: Everywhere and all the time. Journal of International Money and Finance. https://doi.org/10.1016/j.jimonfin.2020.102268
3. Dichtl, H. & Drobetz, W. (2015). Sell in May and Go Away: Still good advice for investors? International Review of Financial Analysis. https://doi.org/10.1016/j.irfa.2014.09.007 (adversarial)
4. Lehmann, B. (1990). Fads, Martingales, and Market Efficiency. QJE. https://doi.org/10.2307/2937816
5. Moskowitz, T., Ooi, Y. & Pedersen, L. (2012). Time series momentum. JFE. https://doi.org/10.1016/j.jfineco.2011.11.003
6. Avellaneda, M. & Zhang, S. (2010). Path-Dependence of Leveraged ETF Returns. SIAM J Financial Mathematics. https://doi.org/10.1137/090760805
7. Hsieh, C.-H., Chang, J.-R. & Chen, H. H. (2025). Compounding Effects in Leveraged ETFs: Beyond the Volatility Drag Paradigm. PREPRINT, not peer-reviewed validation. https://arxiv.org/abs/2504.20116
8. Moreira, A. & Muir, T. (2017). Volatility-Managed Portfolios. Journal of Finance. https://www.nber.org/papers/w22208
9. Kaminski, K. & Lo, A. (2014). When do stop-loss rules stop losses? Journal of Financial Markets. https://doi.org/10.1016/j.finmar.2013.07.001
10. Bailey et al. (2015). The Probability of Backtest Overfitting. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
11. Lo, A., Mamaysky, H. & Wang, J. (2000). Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation. https://www.nber.org/papers/w7613
12. Direxion (2026-02-27). SOXL summary prospectus (target = 3x **daily** return on NYSE Semiconductor Index). https://www.sec.gov/Archives/edgar/data/1424958/000119312526078540/d50601d497k.htm
13. SEMI (2026-07-14). Mid-year semiconductor equipment forecast; this is a sector-demand context source, not an ETF price-timing predictor. https://www.semi.org/en/semi-press-release/global-semiconductor-equipment-sales-forecast-to-reach-a-record-229-billion-dollars-in-2028-semi-reports
14. Reuters (2026-10-16). AI financing, rates, and chip sector selloff: contemporaneous competing explanations. https://www.reuters.com/business/wall-st-futures-mixed-tech-wobbles-again-tesla-gains-2026-10-16/
15. Daniel, K. & Moskowitz, T. (2016). Momentum crashes. JFE. https://doi.org/10.1016/j.jfineco.2015.12.002 (adverse regime stress test)

## Pre-registered candidate experiments (not fitted thresholds)

Benchmark A: SOXL close of last October session -> close of last December session each year.
Benchmark B: unlevered NYSE Semiconductor Index proxy and cash/flat benchmark over same window.
Benchmark C: baseline full-period SOXL buy/hold without entry filter.

Experiment E1 (reversal): after >= 3% drop in sector index over five sessions, require at least 2 closed sessions without a lower close, then close above prior five-session high. Signals measured only from completed daily bars. Execute at next available regular-session open. Parameters **provisional**, sensitivity analysis required.
Experiment E2 (trend): sector index close > SMA20 for two consecutive sessions AND SMA20 slope positive (today SMA20 > SMA20 five sessions ago); execute next open. Test against E1 and E1+E2.
Experiment E3 (risk-managed): E2 plus 20-session realized volatility below its rolling 252-day 75th percentile; position size constrained by ex-ante client loss budget and independent Risk gate.
Experiment E4 (exits): compare (a) fixed December final-session close; (b) prior 10-session lowest close break, next open exit; (c) time stop 15 trading sessions; and (d) earliest of trend break/fixed December close. Avoid intraday fills simulated using same-day closing information.

Do **not** automatically select the best threshold based on the 2026 outcome. Register threshold variants (3, 5, 10 days, etc.) in advance and correct for multiple testing.

## Data / reproducibility / failure controls

Required fields:
- SOXL split and distribution-adjusted daily OHLCV, corporate actions, source and retrieval timestamp;
- exact underlying NYSE Semiconductor Index series, composition and licensing details (SOXX/SOX are imperfect comparators);
- trading-calendar mapping and market timezone; period definition in NY time;
- contemporaneous close-based indicator computation; signal at t, next-session open execution at t+1;
- executable bid/ask spread model, slippage, fees, FX spread, KRW/USD conversion if client mandate requires, dividend/tax assumptions stated;
- unavailable or inconsistent index data => report UNKNOWN / NO_TEST, never synthesize an unverified performance claim.

Validation:
- train/develop: 2010–2020; holdout: 2021–2025; sealed prospective: post-2026-10-17;
- compare years with strong trends, whipsaw, and crashes (including 2018, 2020, 2022, 2024, 2025);
- leave-one-year-out, walk-forward, bootstrap uncertainty; record all parameter trials;
- stress overnight gaps, halted sessions, stop fill worse than trigger, volatility expansion;
- report number of trades, net CAGR/return, max peak-to-trough drawdown, worst trade, median, profit factor, turnover, Sharpe with caution, fees and miss rates;
- report year-by-year and worst-decile outcomes; do not declare superiority on five observations;
- keep negative experiments and null signals append-only.

Historical figures mentioned in previous chat about 2010–2025 SOXL year-end results are **UNVERIFIED until source files and adjustment convention are independently reproduced**. Do not cite those numbers as validated evidence.

## Portfolio and execution gates

- Research evidence does not authorize concentrating the client's wealth or selling any existing holding.
- Compare fixed full allocation against smaller controlled exposure and cash reserve; estimate portfolio-level drawdown with existing correlated assets.
- Independent Risk veto if client mandate / liquidity need / max loss not supplied, market data stale, price gaps exceed loss budget, or concentration limit violated.
- Fractional and conditional order support must be verified in the actual brokerage; stop/OCO trigger does NOT guarantee a fill at trigger price.
- Real orders and broker credentials out of scope.
- Development path: data quality -> research -> verified historical backtest -> blind holdout -> shadow trading -> committee / independent Risk review -> explicit client authorization.

## Monitoring record protocol (future updates append-only)

At each weekly review and whenever the entry state changes, capture:
- as-of timestamp in New York time;
- exact prices / bars / source; sector-index close vs SMA20/50; high/low sequence; realized volatility; QQQ and SOXL reference;
- macro & semiconductor catalysts tagged FACT / ANALYST VIEW / HYPOTHESIS;
- signal state = NO_SIGNAL / CANDIDATE / TRIGGERED / INVALIDATED / STALE;
- observations that would falsify the thesis;
- expected date/time of next review, next experiment required;
- explicit NO_ACTION when insufficient evidence.

Never silently change parameters, backfill as-of facts with later knowledge, or call a research hypothesis a verified trading edge.

## Next actions

- [ ] Acquire versioned split-adjusted historical daily data and verify official index series
- [ ] Recompute 2010–2025 October–December seasonal statistics with transparent adjustments
- [ ] Implement cost-aware E1/E2/E3/E4 and locked OOS comparison
- [ ] Independently replay false-bottom episodes and gap-loss scenarios
- [ ] Check for overlap / contradiction with existing QuanTrade Strategy Memory and old failed technical signals
- [ ] Prepare a reproducible signed run manifest and REJECT / INCONCLUSIVE / PAPER_CANDIDATE decision
- [ ] Weekly review with append-only observation artifacts; research only, not order scheduling

Status remains PROPOSED until all necessary evidence gates pass.
