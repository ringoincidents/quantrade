# DARVAS-BOX-001 — Box breakout vs momentum/new-high controls

- Date: 2026-10-17 (Asia/Seoul)
- Owner: QuanTrade / Strategy Research (prototype single-model investigation)
- State: **EXPLORATORY / NOT VALIDATED**
- Classification: Price-Momentum → Breakout / Box-consolidation; **VARIANT** of preexisting price/volume indicator research, *new source observation*, no independent alpha evidence
- Execution eligibility: **false**. No orders, broker credentials, production worker, or automatic strategy promotion authorized.
- Reproducibility: `research/darvas_box_pilot.py`; offline deterministic regressions: `tests/test_darvas_box_pilot.py`
- Provenance: Nicolas Darvas, *How I Made $2,000,000 in the Stock Market* (1960); later mechanical three-session interpretations are **not** a unique original-source specification. https://thepatternsite.com/Darvas.html ; https://kagels-trading.com/blog/darvas-box-strategy/
- Comparison evidence: Historical QuanTrade negative indicator tests in `indicator_significance_report.json` (volume-related technical edge not established in previously tested scope), `backtest_report.json`, and LLM Holdings `docs/research/QUANTRADE_STRATEGY_MEMORY_HISTORICAL_AUDIT_2026-10-05.md`. Different hypotheses; do **not** import prior REJECTED status as proof about Darvas specifically.

## Falsifiable hypothesis

**H0:** A mechanical Darvas breakout contains no incremental predictive information beyond proximity to a 252-day high and positive trailing 60-day momentum.  
**H1:** Conditional on those features, a confirmed box breakout is followed by higher forward 20-trading-session returns than a comparable strong-momentum observation.

This investigation measures **future event returns**, not a realized stop-loss/pyramiding strategy. It cannot establish investment profitability, statistical significance, causality, or risk-adjusted performance.

## Dataset and integrity

Public `Pubmarks/datasets` daily OHLCV CSV; pinned Git commit `8d16e26815964c88306ec91bf6614e9c67fd89e4` and source path `data/stocks/{TICKER}/{YEAR}/ohlcv.csv`, 2023–2025. Six *present-day selected* tech/large-cap tickers: AAPL, MSFT, NVDA, TSLA, META, TSM. Each supplies 752 daily rows. 2023 is the 252-session warm-up. Only 2024 and 2025 events have full forward outcomes. Dataset description: https://github.com/Pubmarks/datasets . **This is NOT a point-in-time investable universe**: survivorship/selection and corporate-action handling must be audited before broader claims. Instrument classes and dividends are not modeled.

## Mechanical encoding (frozen for reproduction, NOT classical Darvas equivalence)

1. Search for an intraday high exceeding the **previous** 126-session high. Confirm that candidate high after three subsequent sessions whose highs remain strictly lower. If equal/higher, move the pivot.
2. Track the lowest intraday low since the top candidate; confirm a floor after three subsequent sessions with higher lows. If the top breaks before floor confirmation, restart the top search.
3. Only after top **and** floor are available, register a breakout if session **close** exceeds prior box top. If the same day's low breaches the floor, discard the ambiguous signal. Reset after breakout/floor failure.
4. Restrict to positive trailing 60-session *close* momentum and close >= 90% of the high over the **previous** 252 sessions; deduplicate with 20-session cooldown.
5. Entry proxy = next session open, outcome = open 20 sessions after entry / entry open - 1 (i.e. `open[t+21]/open[t+1]-1`). **No trading fees, gap-risk stops, spreads, taxes, dividends, leverage, capital constraints, risk sizing or P&L compounding.**
6. Comparator A = eligible strong-momentum *days* (highly overlapping observations, NOT independent trades). Comparator B = eligible fresh 252-session *closing* highs (20-session cooldown). Comparator C = matched controls among eligible days, same ticker/year, >=20 and <=63 trading sessions from signal, excluding +-19 trading sessions around all Darvas signals. Greedy one-to-one nearest feature match on momentum, 252-high proximity, volume ratio and temporal distance; no matching on future outcomes. Matched pairs are retrospective, may have latent calendar/regime differences, and are **NOT causal estimates**.
7. Secondary descriptive split = event-day volume >=1.25x prior 20-session average; this is an unvalidated extra rule. No parameter tuning between year outputs.

## Observations (actual fetched OHLCV, research probe 2026-10-17)

Reported values are **mean open-to-open forward 20-session returns, before costs**.

| Cohort / distinct event definition | 2024 n | 2024 mean | 2025 n | 2025 mean |
| --- | ---: | ---: | ---: | ---: |
| Eligible strong-momentum *days* (correlated rows, do not treat as independent events) | 884 | +4.35% | 638 | +1.42% |
| Fresh 252-session closing-high signals (20-day cooldown) | 24 | +5.83% | 13 | +3.25% |
| Darvas box breakout (20-day cooldown) | **11** | **−0.92%** | **5** | **+1.98%** |
| Darvas breakout + volume >=1.25x | 5 | −9.18% | 2 | +9.15% |
| Darvas less nearest matched control, paired excess | 11 | −15.34 percentage points | 4 | +8.72 percentage points |

The matched-control contrasts are particularly fragile: the comparator is selected retrospectively from a nearby but **different trading date**, the samples are tiny, and 2024/2025 market regimes differ. One 2025 event had no qualifying match. The large paired excess is not treated as meaningful alpha or an unbiased causal effect.

Per-symbol box signal counts during 2024–2025: AAPL 0, MSFT 4, NVDA 1, TSLA 1, META 6, TSM 4 (total 16). Thus very large companies and exceptional winners disproportionately shape the summary. A 2025 evaluation based on data already seen while designing this pilot is a **retrospective diagnostic**, **not** a prospectively preregistered clean out-of-sample test.

## Interpretation / review dissent

- **Research:** In this narrow pilot, no consistent incremental advantage of Darvas over a simple 252-day fresh-high comparator was found. Signal sample is far too small for hypothesis testing. Evidence status = INSUFFICIENT.
- **Counter-research (same-model simulated, not independent):** 126-day starting-high parameter, floor construction, start-date selection and survivorship can change the answer. Paired controls on non-identical days confound regime. The 20-session horizon excludes Darvas's actual rolling stop, so this is only a breakout-prediction study.
- **Risk:** Neither trailing-stop/gap execution nor realistic commissions/spreads were modeled; never attach this research to a broker.
- **Runtime:** Keep this as domain research rather than add another core Strategy Memory store or indicator to production. Future Strategy Memory registration should point at this document and remain non-authoritative.

## Next genuine falsification gate (not performed)

Freeze an expanded point-in-time universe including delisted securities and correct corporate actions, apply a fixed predeclared calendar split and transaction costs, require nonoverlapping events / block bootstrap clustered by ticker and date, vary box construction only in a preregistered sensitivity grid, compare equal-exposure portfolios with (a) momentum-only, (b) 252-day Donchian breakout, (c) randomized/blocked placebo dates, (d) Darvas. Analyze stop/pyramiding separately, with worst-case stop gaps and feasible position sizing. Only then judge edge.

## Organizational trace

```yaml
originating_actor: QuanTrade Strategy Research
mission_owner: QuanTrade Lab
execution_mode: single-model simulation; deterministic event-study computation
actor_boundaries:
  research: hypothesis and source intake
  experiment: fixed OHLCV signal and comparator code
  review: methodological dissent (simulated, not independent)
  risk: execution-eligibility denial
handoff:
  to: QuanTrade Strategy Memory / independent counter-research
  deliverables: this document, script, deterministic tests, explicit null/limitations
decision_authority: governed QuanTrade decision process; no Founder capital authorization inferred
execution_authority: none
live_execution_authorized: false
cost: no paid model or broker API
artifact_scope: QuanTrade-domain research; not Holdings-Core
```

Outcome: **WATCH / TEST FURTHER**, not ADOPT, VALIDATED or production enabled.