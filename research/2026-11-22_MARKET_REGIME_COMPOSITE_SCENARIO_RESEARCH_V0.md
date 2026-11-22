# QT-MRI-2026-11-22 — Market Regime Composite & Conditional Scenario Forecast (Founder Idea Preservation)

> **RESTART ALERT — READ BEFORE REBUILDING MARKET TIMING, DASHBOARDS, REBOUND/BOTTOM DETECTORS OR FORECASTING**
>
> **잠깐! 기존 가격·뉴스 예측 기능을 다시 개발하거나, 새 대시보드를 만들거나, 지표 몇 개로 매수시점을 정하기 전에 반드시 이 기록과 연결된 GitHub Issue부터 확인할 것.**
> 여기에는 Founder가 2026-11-22 제시한 *'수많은 지표 → 하나의 시장 국면 지수 → 하나의 실제 선과 미래 확률 경로 → 클릭해서 개별 근거 확인'* 아이디어와 검증을 위한 반례·실험·미해결 질문이 보존되어 있다. 아직 지표나 예측 성과를 입증한 것은 아니다. 대화 요약만 읽고 이미 검증/구현됐다고 선언하지 마라.

- ID: `QT-MRI-2026-11-22`
- Recorded: 2026-11-22, Asia/Seoul.
- Type: Founder-originated research hypothesis / UX intent / Strategy Memory intake / future Mission candidate.
- Status: **OBSERVED → CANDIDATE; RESEARCH ONLY; NOT VALIDATED; NOT IMPLEMENTED; EXECUTION_ELIGIBLE=false**.
- Repository role: QuanTrade **Domain / Research**. Holdings OS Core 변경·Decision 승인·Task 승인·실거래 권한 아님.
- Canonical precedence: `QUANTRADE_CANONICAL_VISION.md` > this candidate. Read `CLAUDE.md` (v3.2 forecast disablement), `research/TRADING_OSS_RESEARCH_PROGRAM.md` and relevant Holdings Strategy Memory protocol before any adoption.
- Access/privacy: this file is in a **public repository**. No private holdings, quantities, cost bases, credentials, private account data, individual identity, or personal message transcripts.
- Evidence legend: **F** = Founder-supplied requirement; **S** = independently inspectable public source; **H** = plausible/contested hypothesis; **P** = prior assistant/conversation lead, not independently replicated in this research record; **D** = proposed design, not evidence; **B** = blocker.
- Linked issue: to be attached after issue creation; find issues by `QT-MRI-2026-11-22`.

## 0. Why this must survive the chat

[F] Founder described, over a series of November 2026 discussions, the desire to understand macro and cross-asset market cycles rather than trade on a video narrative. After an October/November selloff → December rally hypothesis, the Founder asked whether VIX, fear/greed, QQQ RSI, DXY, credit spreads, US yields, gold, Brent oil and Korean exports could jointly clarify market bottoms. Then the idea evolved into **ONE primary graph** for an independently calculated market index, with a differently colored future forecast line/fan; another view reveals each source indicator, provenance, history, and its contribution. A Claude/open-source skill remembered as doing 10,000 Monte Carlo scenarios was proposed as a mechanism, not chosen as a trustworthy provider.

[F] Crucial desired behavior on resumption: *"잠깐! 이거 먼저 해봐야지"* — recover the idea whenever work on market state, technical indicators, signal research, scenario analysis, a portfolio dashboard, a market-forecasting module, or capital deployment timing is restarted. The next agent should **recover this existing candidate before initiating a conflicting new project**, and should propose the smallest evidence-gathering step. This is a retrieval / prioritization prompt, **not** authority to execute or bypass governance.

## 1. Nonnegotiable product concept

1. **Single main chart**: an easily read, time-indexed proprietary `Market Regime / Opportunity Index` (semantic target must be fixed before fitting). Historical measured line and future probabilistic **fan chart** drawn with distinct visual treatments. The 50%, 80% or 90% intervals must be labeled, calibrated or clearly marked unvalidated. No fake probabilities.
2. **One clear top-level reading**: regime/state, last updated/timezone, forecast horizon (5/20/60 trading days or 1/3/6 months), model state (RESEARCH_ONLY / SHADOW / VALIDATED), freshness and confidence. UI cannot imply BUY/SELL unless separately justified and approved.
3. **Explainable drill-down**: select any historical date or forecast; reveal individual time series; release time vs economic reference time; data source; transformed feature; direction; weight/contribution; lag; missing-data flags; contradictory signals and regime-specific reliability.
4. **Historic forecasts preserved**: every forecast made at time t stays immutable; later revisions do not overwrite earlier forecasts. Support retrospective audits of error, calibration and drawdown.
5. **Two distinct outputs**: (a) the future distribution of the *composite index*, and (b) the conditional future distribution of **actual investable targets** (QQQ/SPY/KOSPI, perhaps underlying semiconductor index). Never convert 'index score +20' to '+20% stock return'.
6. **No opaque magical LLM forecast**: deterministic/statistical engine computes; LLM helps research, explanation and data/problem triage. External skill is not a validation authority.
7. **Minimal main interface, deep inspection available**: hide complexity in other views; Founder explicitly wants one chart as the default. Do not build dashboards first if research edge absent.

## 2. Founder-proposed numerical signals — all thresholds HYPOTHESES

| Candidate | Proposed trigger | Real question | Caveat / overlap |
| --- | --- | --- | --- |
| CNN Fear & Greed | <=10 | Extreme fear precedes favorable forward *risk-adjusted* returns? | Index already contains VIX, stock momentum, bond demand, put/call etc.; double-counting |
| Cboe VIX | >=30; separate 50–60 extreme | Are extreme implied-vol levels attractive for **what horizon** and with how much further drawdown? | Volatility ≠ price direction; VIX peak and stock trough can be months apart |
| QQQ daily RSI(14) | <=30 | Is oversold meaningful in uptrend vs bear-market regimes? | RSI can remain oversold through declines; technical transform of price |
| DXY | 108–110+ | Does absolute dollar level mark bottoms? | Threshold is regime/nonstationarity sensitive; use percentile, changes, trend reversal |
| US high-yield credit OAS | spread widened **then narrowed** | Does **change of spread trend** increase forward equity returns / reduce risk, and is it actually a leading signal? | Credit can follow stock prices; publication cadence; spread ≠ risk-free rate |
| Other rates | US 2Y/10Y yields, slope, **real** yield, policy expectations | Which monetary/shock component matters? | Same rate rise can mean growth or inflation shock |
| Korean exports | total, daily average, semiconductors, growth YoY | Does export data provide incremental KOSPI forecast information? | Market often anticipates exports; monthly vintage, release lags, base effects, prices vs volume |
| Gold, Brent oil, FX | cross-asset prices and shocks | Regime and contagion vs predictive contribution | Sign flips by shock/period; contract rolls in oil |

**Hard rule**: No numeric threshold above is approved as a trading rule or globally optimal cutoff. Freeze a provisional experiment grid and evaluate out-of-sample without selecting by November 2026 outcomes.

## 3. Additional indicators that must not be forgotten (candidate universe, NOT promise to ingest all)

- **Fear & equity breadth**: VIX spot and term structure (VIX vs VIX3M), VIX9D, VVIX, SPX/QQQ drawdown/volatility, percentage constituents above 50/200d MA, advance/decline, new highs/lows, equal-weight vs cap-weight relative performance, HY ETF vs Treasury relative strength, put/call (positioning with provenance), market liquidity.
- **Credit and funding**: ICE BofA US HY OAS (FRED `BAMLH0A0HYM2`), IG OAS, bank lending standards, EBP (not necessarily freely updated in real time), 3m funding stress where available, cross-currency basis if licensed, corporate issuance/refinancing, financial conditions `NFCI` / `ANFCI`.
- **Rates / liquidity**: DGS2, DGS10, 10y TIPS real yield `DFII10`, 10y–2y / 10y–3m spreads, Fed policy odds (verified timestamped source), SOFR, QT/QE/Fed balance sheet, Treasury issuance/cash management (avoid folklore 'liquidity' without definition).
- **FX/commodities**: broad USD dollar index vs ICE DXY distinction; USD/KRW, USD/JPY, Brent/WTI same-contract roll-safe series, gold and silver returns, copper/gold (not universal recession detector).
- **Real economy/earnings**: US claims, payrolls, CPI/PCE, ISM new orders, corporate earnings-revision breadth and forward EPS, valuation, S&P 500 profitability; Korean total and semiconductor exports *as-of published*, trade-day adjusted exports, USD/KRW and foreign investor flows.
- **Market target specificity**: separate US broad market, US growth/tech, Korea, and semiconductor markets; no single fixed factor weight assumed to fit all.
- **Negative-control/falsification features**: random or time-shuffled factors, publication-delayed factor, simple trend-only and buy-and-hold baselines. The study MUST test whether adding data makes prediction worse.

## 4. Evidence/claims ledger: what we know vs what we must test

| Claim | Status as of recording | Supported interpretation / missing proof |
| --- | --- | --- |
| Composite financial conditions indices exist | S | Chicago Fed NFCI is computed from 105 standardized financial indicators. This **does not establish stock-bottom forecasting**. https://www.chicagofed.org/research/data/nfci/about |
| VIX high levels correlate with subsequently high average 1Y returns | S, association only | Cboe study conditions historical S&P500 1Y returns on days when VIX above 30/35/40 etc. Overlapping dates, crisis clustering and interim drawdown matter. https://www.cboe.com/insights/posts/embracing-and-harnessing-volatility-feeling-confident-in-your-strategy |
| VIX 50–60 catches exact bottom | H / unproven | 2008 high VIX preceded 2009 bottom by months; 2020 episode differs. Cannot choose date from peak alone. |
| CNN <=10 predictive edge | H / unproven | Verify formula, vintage and historical access before calculating; avoid double-counting overlapping components. https://www.cnn.com/markets/fear-and-greed |
| RSI(14)<=30 gives profitable entry | H / unproven | Needs QQQ regime-conditioned, after-cost OOS backtest; RSI(6) research isn't RSI(14) proof. |
| DXY 108–110 is universal bottom level | H / contradicted by period variation | Dollars can rise for different reasons; prefer normalized level/trend/changes with regime. |
| HY OAS tightening *leads* price reversal | H, **priority falsification** | Mechanism plausible as risk stress falls; not universal lead—credit may also lag equity. Must test lead/lag on matched timestamps and sample/event-level evidence, not chart overlays. |
| 'Many indicators improve forecasts' | S in narrow other target, H in equity-timing target | Chicago Fed creates index; Federal Reserve research on yield curve+credit considers recession classification, **not stock bottoms**. https://www.federalreserve.gov/econres/notes/feds-notes/there-is-no-single-best-predictor-of-recessions-20190521.html |
| More predictors necessarily raise stock timing accuracy | Contradicted / not generally valid | Goyal, Welch & Zafirov, RFS 2024 shows formidable OOS equity-premium prediction difficulties. https://academic.oup.com/rfs/article/37/11/3490/7749383 |
| Korean exports correlate with KOSPI; export leads index | H / contested direction | Prior chat cited correlation ~0.63, other windows ~0.49/0.70 and anecdotal 2026 export surge, but **this record has NOT independently reproduced numbers or causal lead**. Separate contemporaneous correlation, predictive lead and reverse lead. Check Korea Customs/MOTIE, FRED/ECOS, daily-market timestamps and 3–4y 'cycle' claims. |
| 10,000 Monte Carlo draws improve market forecast validity | False as a standalone claim | More draws reduce Monte Carlo numerical error under assumptions, NOT model misspecification, tail underestimation, future-information leakage or overfit. |

### Historical research and organizational precedence
- `CLAUDE.md`: v3.2 disabled price and LLM news directional predictions after failing validation; **new model cannot silently bypass this gate**.
- `research/2026-10-17_SOXL_YEAR_END_REVERSAL_RESEARCH_V0.md`: related seasonal reversal, LETF path dependence, ex-ante thresholds, OOS gates and ICE NYSE Semiconductor Index identity.
- `research/2026-11-18_SOXL_IONQ_TE_INCREMENTAL_RISK_REVIEW.md`: unresolved vendor disagreement/benchmark identity; keep NO_TRADE where data/validation blocked.
- `research/TRADING_OSS_RESEARCH_PROGRAM.md`: external tools are replaceable adapters; do not equate library popularity with adoption.
- Holdings private `docs/research/QUANTRADE_STRATEGY_MEMORY_PROTOCOL_2026-10-05.md`: capture → reconcile → test → decision-time retrieval; historical failures are retained, not erased.
- Holdings `AGENTS.md` + `docs/research/TECHNOLOGY_ASSIMILATION_PROTOCOL_v0.1.md`: external technology assimilation and scope boundaries. No automatic change to Core.

## 5. Closest analogues / candidate technology intake

**This is a candidate/source list, NOT an endorsement or verified latest code/license. On resumption pin exact commit/release, license, maintainer activity and inspect actual implementation.**

| Candidate | Relevant mechanism | Relative fit and limits | Disposition |
| --- | --- | --- | --- |
| Chicago Fed NFCI/ANFCI | Standardized weighted composite of 105 financial conditions inputs | Reusable index-construction prior, not a predictive price target | STUDY / LEARN |
| BlackRock Aladdin Risk | Cross-asset stress/scenario/portfolio-risk analysis | Architecture analogy; commercial closed system, no claim public open-source access or alpha | OBSERVE |
| QuantLabs US Market Regime Dashboard | Public multi-factor indicators, regime scoring, possible forward-return displays | Compare feature engineering, leakage and evidence claims; any marketing backtests must be reproduced | WATCH |
| SecondOrderEdge Macro-Dashboard | FRED-based regime/recession models, separate component contributions, OOS analysis | Investigate code, exact version, license, reusability | REVIEW |
| Omkar-Terdal Claude-Trading-skill `trader-timemachine` | Historical intraday path resampling with ~10,000 simulated paths | Prior chat identified as closest to remembered skill; by itself resampling is **not predictive conditional simulation** | EXPERIMENT_ONLY |
| Anthropic Claude Cookbook `creating-financial-models` | Reproducible Monte Carlo finance modeling skill, simulation and uncertainty | Useful template discipline, not a validated stock-direction oracle | LEARN |
| `mkaavish/forecastClaudeSkill` | Time series model comparison, forecast intervals, validation workflow | Inspect exact implementation, license, robustness and pin commit | WATCH |
| Cboe VIX, FRED HY OAS, FRED DGS10, etc. | Primary time-series feeds | Data source candidates; source availability, legal terms and releases must be checked | DATA INTAKE |

Canonical URLs:
- https://www.chicagofed.org/research/data/nfci/about
- https://www.blackrock.com/aladdin/platforms/products/aladdin-risk
- https://stock.quant-labs.workers.dev/en/
- https://github.com/SecondOrderEdge/Macro-Dashboard
- https://github.com/Omkar-Terdal/Claude-Trading-skill/blob/main/trader-timemachine/SKILL.md
- https://github.com/anthropics/claude-cookbooks/blob/main/skills/custom_skills/creating-financial-models/SKILL.md
- https://github.com/mkaavish/forecastClaudeSkill
- https://fred.stlouisfed.org/series/VIXCLS
- https://fred.stlouisfed.org/series/BAMLH0A0HYM2
- https://fred.stlouisfed.org/series/DGS10
- https://fred.stlouisfed.org/series/DFII10
- https://fred.stlouisfed.org/series/NFCI
- https://www.cboe.com/insights/posts/embracing-and-harnessing-volatility-feeling-confident-in-your-strategy
- https://www.federalreserve.gov/econres/notes/feds-notes/there-is-no-single-best-predictor-of-recessions-20190521.html
- https://academic.oup.com/rfs/article/37/11/3490/7749383

**Provenance gap**: The exact screenshot/video link, exact Claude Skill that Founder recalled, exact code versions, factor release vintages, and numeric historical correlations from prior conversation are not deposited as independently verifiable artifacts here. These remain unresolved source checks—not Evidence.

## 6. Technical system sketch: separate truth, features, forecasts and decisions

```text
official/authorized feeds (price, credit, rates, exports, earnings, events)
  → source registry + license/quality + observed_at/released_at/vintage
  → point-in-time / as-of feature store (daily + weekly + monthly)
  → group scores: fear | credit | rates/liquidity | breadth | macro | earnings
       → A: interpretable latent/current Market Regime State
       → B: directional change / regime transitions / recovery
  → conditional forward-return distribution for selected target (QQQ/SPY/KOSPI)
  → scenario engine (historical block bootstrap / Markov regime /
                      conditional volatility / multivariate paths / ensemble)
  → immutable prediction snapshots + scoring/evaluation
  → one chart: history vs future fan; drilldown: factor attribution
  → Research result → independent Portfolio/Risk/Committee (NO ORDER)
```

Recommended dual-object model:
- `MarketStateIndex(t)`: explicitly defined score orientation. Do **not** call it return forecast or buy probability.
- `MarketForecast(target, asof, horizon)`: predictive distribution over target returns, maximum future drawdown, upside/downside events, and market-regime transitions. Each target-specific model includes no hidden implicit rebalance.
- `ModelEvaluation`: OOS accuracy, calibration, interval coverage, baseline-relative improvement, monitoring of drift and failed periods.
- `FactorSnapshot`: source, release timestamp, data age, raw/transformed value, orientation, inclusion, attribution and uncertainty.
- `ForecastRun`: model revision, training cutoff, random seed, scenario count, immutable forecasts and actual observed outcomes when available.
- `EventProvenance`: economic announcements distinguish value **as publicly released at t** from later revision and date of economic observation.

Potential pipeline: Python/Pandas/Polars + statsmodels/sklearn/conditional volatility packages as warranted; simple API or static JSON snapshot; lightweight mobile-first chart (fan plot, drilldown). Do not install complex ML infrastructure before proving data and baselines. No automatic orders, advice execution, default Runtime worker or Holdings Core schema changes.

## 7. Research protocol (pre-register BEFORE looking at final results)

### G0 — Data and causality hygiene (BLOCK until passed)
- Define target: (1) S&P500/SPY, (2) QQQ, (3) KOSPI; separate SOXX and SOXL proper underlying as applicable.
- Identify first available / later revised observation for each economic series, market close, timezone, publication lag and resampling rule. Market-close as-of signal only for next executable session.
- Historical point-in-time data (FRED/ALFRED vintages where relevant), delisted companies if using breadth/earnings, total-return-adjusted prices, splits/dividends, non-survivorship-biased components. State dataset/license limitations.
- Raw series for HY OAS vs other spread proxies must never be silently substituted. DXY/US broad index distinguish. Source quality and rights before use.
- Time period 2000–2025 for model development/testing where available; 2026 sealed prospective validation if genuinely unused. 2026 retrospective already discussed in chat, so **2026 is not an untouched holdout** for hypothesis generation.
- Explicit missing-data / macro-release alignments. No interpolation across future publications. Exact horizon/market holidays.

### G1 — One-variable edge (falsifiable)
For each candidate and threshold:
1. contemporaneous correlation with returns/levels and lagged correlations (+/- 1,5,20,60,120 trading days); **avoid spurious correlation in levels**;
2. compare conditional forward 5/20/60/126-day target returns, direction probability, max adverse excursion, drawdown, sample count and crisis-episode count;
3. avoid claiming 50 adjacent VIX>30 days are 50 independent signals; use event clustering/embargo and episode-level uncertainty;
4. quantile-thresholds, absolute thresholds, spread-level vs spread-first-derivative vs turn, regime partitions (QQQ above/below MA200; risk-off vs risk-on);
5. test HY-spread peak vs **S&P index trough** lag sign and conditional return when narrowing begins, including stock-leading-credit cases.
Baseline: unconditional forward returns, buy-hold and 200d trend filter; effect size with confidence intervals; costs for tradeable strategies.

### G2 — Combination improvement, not indicator explosion
- Compare single signals, VIX+HY spread, RSI+price trend, DXY+real yields, adding earnings/export, simple equal-weight, winsorized standardized score, PCA/dynamic factor, logistic/regularized ML. Do not use black box as first baseline.
- Factor families must be de-correlated or contribution-controlled: CNN already embeds VIX/credit/price; broad NFCI embeds multiple candidate inputs; VIX/RSi/price share market-derived information.
- Walk-forward expanding or rolling windows, purge/embargo overlapping labels, forward-only hyperparameter tuning, multiple-testing correction/probability of backtest overfitting, crisis leave-one-out, block bootstrap.
- Report lift over best **simple benchmark** on held-out windows, across assets and decades; report negative/null results.

### G3 — Conditional forecast and Monte Carlo
- Competing scenario generators: historical block resampling, regime-dependent bootstrap/transition model, volatility-tails (GARCH/t-style where appropriate), multivariate dynamic correlation. Use a simple nonconditional bootstrap and historical distribution as baselines.
- Simulation draws = e.g. 10,000 **for numerical precision only**; grid 1k/10k/100k checks numerical stability but never call it predictive evidence.
- Outputs: median, 50/90% prediction bands, P(positive by horizon), P(drawdown worse than X before horizon), worst-tail scenario; **not just one pretty predicted line**.
- Calibration: rolling probability bins and reliability diagram; Brier / log score for event probabilities, CRPS/pinball for distributions/quantiles, 50/90% empirical interval coverage, Kupiec-style tail checks as appropriate.
- Challenger benchmark: no-predictability random walk + observed volatility, unconditional historical returns, plain trend/volatility, cheap linear model. Report absolute AND incremental predictive power.
- Immutable daily `ForecastRun`; later actual outcomes tracked against original predictions, including failure cases and time-to-thesis-break. No hindsight revision.
- Research to shadow to action only through formal QuanTrade gates; NO BUY/SELL/confidence live signals or capital decisions by this record.

### Minimal preregistered candidate tests
A VIX>=30; B RSI(14)<=30; C spread peaks then narrows for N verified observations; D VIX+RSI; E VIX+HY narrowing; F DXY+real-yield+credit; G add macro/exports; H regime+technical confirmation; I all with isolated-source ablations. Predefine trigger frequency, hysteresis (avoid repeated dates) and strict temporal availability. Dates, calibration and ranges are suggestions; **freeze before use** and evaluate separate holdout.

## 8. Foundational failure modes, guardrails, and what not to do

- **Leakage**: using month-end exports on dates before the release, macro revisions as originally known, same-bar prices for execution, lookahead constituents.
- **Overfitting**: many indicators, dozens of thresholds, sequential model selection on 2026 crash, leakage through overlapping returns and tuning on holdout.
- **False certainty**: interpreting "10,000 simulations" as "10,000 independent predictions" or an error bar as calibrated probability.
- **Nonstationarity**: DXY 108/110 and VIX 30 behavior differs by era; different inflation/rate regime changes cross-asset relationships.
- **Redundancy**: CNN fear/greed, VIX, option positioning, breadth, NFCI, credit partly overlap; weights without diagnostics create phantom confirmations.
- **Misaligned targets**: NFCI predicts financial stress; Fed recession AUROC ≠ equity bottom alpha; return forecasting ≠ worst-path drawdown forecasting.
- **Behavioral/execution mismatch**: highest expected 6m return might still experience unacceptable -30% interim drawdown; include utility/risk mandates, costs, and "hold cash" opportunity costs.
- **Hidden producer bias**: data from screenshots/blog charts, unsourced correlation `0.63`, 3–4y export cycle, 'spread leads' slogan, examples from previous conversation are leads unless replicated.
- **Model/AI governance**: never let LLM silently estimate numeric probability, invent market data or alter a trading mandate; Core/domain authority remains separate.

## 9. Product acceptance criteria and suggested milestones

**Research artifact first (no UI-first work)**:
1. `indicator_registry.yaml`: 20–30 candidate inputs with source URI, update/release frequency, timestamp availability, vintage policy, adjustment convention, licensing and nulls.
2. `asof_market_state_dataset`: reproducible daily panel + QA report and missing-data counts, plus raw to feature lineage.
3. `G1_signal_study.md`: per-feature contemporaneous and forward relations, event-vs-date samples, crisis behavior, counterexamples and effect size.
4. `G2_composite_ablation.md`: pair/group comparisons, cross-validated improvement over baselines, de-duplication / overlap analysis.
5. `G3_forecast_calibration.md`: probabilistic metrics, model complexity/cost, intervals and proper tail behavior; honest fail/insufficient-data labels.
6. `forecast_snapshot_schema.json`: ready for immutable prospective results (store data/model revision, asof, seed, source versions).
7. Only then, `one_chart_mobile_mock` with historical composite + future prediction fan and drilldown explainability. A mock may be shown early as UX research **but without implying validated forecast or allocating resources to production dashboards**.

**Success metrics**: quality of data lineage; statistically material OOS lift vs baselines; interval coverage; meaningful incremental utility net of costs; reproducibility and no hindsight. **Kill/hold criteria**: baseline not beaten on sealed holdout, too few independent crises, highly unstable signs, unaffordable data/license, uncalibrated tails. If fail, retain as descriptive macro state/risk dashboard but **remove predicted-return language**.

## 10. Step-by-step continuation script for any future worker

When asked about **QuanTrade**, market timing, market bottom, VIX/credit indicators, export-driven KOSPI, a one-chart trading dashboard, a 10k Monte Carlo skill, or when existing alpha research is BLOCKED:

1. **STOP and RETRIEVE** `QT-MRI-2026-11-22` and its GitHub issue; inspect current canonical vision, `CLAUDE.md`, recent strategy-memories and competing active PRs/issues.
2. Restate founder's actual requested end state in one sentence and the status truth: *candidate only, no verified alpha, no implemented chart*.
3. Reconcile already researched/tested indicators, relevant failed price/news alphas, existing SOXL year-end thesis, and domain authority. Ask whether newer evidence supersedes the idea; don't overwrite its origin.
4. Identify **the earliest failed or unattempted gate** among G0→G1→G2→G3→UI. Prefer one reproducible dataset and one simple falsifiable test; don't launch a large refactor or build an unvalidated predictor.
5. Propose and, only within assigned authority, perform a bounded experiment with tests and a reproducible artifact; attach outcomes (positive, negative or blocked) to the issue and an append-only record.
6. For a **specific prompt** to present to the Founder on resumption, use:
   > "잠깐! 2026-11-22에 논의한 시장 국면 복합지수와 확률 예측선 연구(QT-MRI-2026-11-22)가 있습니다. VIX·신용스프레드·금리·달러·수출 데이터를 묶기 전에 G0 데이터 검증과 G1 선행성 검증부터 하기로 했고, 아직 매매 예측력은 입증되지 않았습니다. 이번 작업에서 가장 먼저 해당 연구의 미해결 G0/G1 단계부터 재개할까요?"
7. This is a **reminder and research prioritization suggestion**, not a standing mandate to execute or a claim a notification has been scheduled.
8. When G1/G2/G3 fail, record why, stop promotion, and consider only descriptive risk-intelligence UI; when succeed, request governed approval before portfolio/execution use.

## 11. Explicit unanswered questions (keep unresolved until tested)

- Is an interpretable single risk/opportunity index statistically preferable to showing 4 component axes? What score semantic produces calibrated future returns, and can it support US and Korean markets with different parameters?
- Can we access **actual historical** CNN fear/greed series with constituent methodology and timestamp? If not, avoid unverifiable replication.
- Does VIX>30 outperform a simple 200d trend and buying after -20% drawdowns **out of sample** after costs and with max adverse excursion constraints?
- Does high-yield spread contraction **precede** stock bottom, coincide, or lag, after correcting for release timing? Which degree of contraction / persistence matters?
- Can US dollar changes and 10y real rate changes explain apparently contradictory episodes? Can we separate demand/oil-supply/rate shocks?
- Are Korean exports leading, coincident or lagging **once vintages and release lag** are honored? Does semiconductor export volume give distinct information beyond earnings revisions?
- Are gold, oil, copper and yield-curve variables incremental rather than redundant?
- Which of baseline, regime-switching, bootstrap, quantile regression and conditional multivariate forecast remain calibrated through stress regimes?
- What happens to the calibrated probability and measured return when missing indicators or delayed macro releases force graceful degradation?
- Can a one-chart screen communicate uncertainty faithfully without becoming a pseudo-precise BUY/SELL indicator?
- Which skill implementation was the Founder recalling, exactly? Verify before assigning any OSS provider.
- Is asset-level prediction useful to QuanTrade's investment decision/risk process without violating separation-of-duties?

## 12. Current handoff / change of watch (2026-11-22)

**DONE**: captured founder intent; reconciled canonical QuanTrade vision and historical alpha failures; inventoried candidate indicators, evidence, counterexamples, related precedents, OSS leads, technical architecture, validation protocol, gates and UX contract in one discoverable record.

**NOT DONE**: no source dataset downloaded or compiled; no numeric historical regression/reproduction performed here; no independently validated future-return threshold; no Monte Carlo engine built/run; no outcome backtest, no calibration, no composite index, no mobile dashboard, no real-money trading. Do not claim otherwise.

**NEXT ACTION**: create a bounded, approved research task for G0: select source-vintage-safe VIX/HY-OAS/DGS10/QQQ/SPY panel with exact date-time conventions, pre-register one VIX+credit narrowing experiment and baseline for 2000–2025. Then G1. Link the issue from progress records.

**BLOCKERS**: data availability/licenses, OAS release/vintage delays, exact underlying SOXL index if testing that asset, leakage-safe Korean export release history, unseen Claude Skill version, unapproved strategy prediction path.

**AUTHORITY**: research documentation and experiment candidate only; no production change, no forecast reactivation, no portfolio instruction, no trading approval. Owner/mandate to be assigned per canonical project process.

**Trigger for review**: resuming an alpha, market-regime, macro intelligence, investment-timing, forecast simulation, or one-chart UI project; evidence of stronger OOS models; new data rights; a founder-authorized validation task; after G0/G1 blocker resolution.

---

_Append future corrections or supersession with date, source and links; do not erase negative results or represent this intake as a canonical validated strategy._
