# QT-EVENTS-2026-SEMIS-001 — 2026 반도체 사건·시장반응·경로 연구

- 작성: 2026-10-17 KST / 관찰 종료: 미국 2026-10-16 정규장
- 상태: LITERATURE/EVENT INVENTORY COMPLETE v0.1; CAUSAL EVENT STUDY NOT RUN; NO LIVE TRADE AUTHORITY
- 상위 전략: [SOXL year-end rebound research](./2026-10-17_SOXL_YEAR_END_REVERSAL_RESEARCH_V0.md) / [Issue #129](https://github.com/ringoincidents/quantrade/issues/129)
- 공개 기록에 사용자의 투자 원금/보유수량/계좌 정보를 저장하지 않음.
- **Coverage limitation**: These are material *verified selected events*, NOT literally every news story. High-volume exhaustive extraction and deduplication remain research tasks.

## 1. Critical index distinction

SOXL's **official daily 3× target** is the *NYSE Semiconductor Index* (ICESEMIT). The PHLX Semiconductor Index (SOX), SOXX, Nasdaq and QQQ are secondary proxies, **not the actual SOXL underlier**. Do not use SOX × 3 as the reconstructed daily SOXL total return. Cite Direxion official fund page https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs and 2026 prospectus https://www.sec.gov/Archives/edgar/data/1424958/000119312526078540/d50601d497k.htm

## 2. Event taxonomy and channels

- DEMAND: AI hyperscaler capex, neocloud funding, AI revenue/payback, custom silicon, inference, memory HBM/DRAM.
- SUPPLY: foundry capacity, CoWoS/advanced packaging, lithography tools, helium/gases, electricity, shipping disruptions.
- RULES: US export licensing, tariffs, Dutch DUV restrictions, China approvals, CHIPS incentives.
- MACRO: US inflation, Treasury yields, interest-rate expectations, oil prices, USD, recession risk.
- POSITIONING: crowded AI momentum, leverage liquidation, multiple compression, credit spread / CDS, ETF flow.
- END-MARKETS: consumer electronics and auto industrial demand and price sensitivity.
- MEASUREMENT: stock/index reactions, announcement surprises vs expectations, comparison vs general Nasdaq/market.

### Verified event ledger — candidate main impacts

Each item records **source-reported contemporaneous fact**, not isolated causal estimate. Same-day returns only where explicitly reported.

| ID | Date / period | Event | Mechanism / potential sign | Observable report / limitation | Source |
|---|---|---|---|---|---|
| EV-01 | Jan 14–15 | TSMC record profit, $52–56bn 2026 capex and near 30% revenue growth outlook | demand/capacity + | Reuters reported US chip-share rebound Jan 15, non-isolated | https://www.reuters.com/world/china/tsmc-likely-post-fourth-quarter-profit-leap-driven-by-ai-boom-2026-01-14/ ; https://www.reuters.com/business/wall-st-futures-rise-tsmc-sparks-semiconductor-rally-financial-earnings-deck-2026-01-15/ |
| EV-02 | Jan 13–15 | BIS China exports changed to case-by-case eligibility, Presidential 25% duty on narrow AI-semiconductor products | trade compliance mixed; not blanket 25% on all chip imports | rule scope and exemptions important; no return attribution | https://www.reuters.com/legal/legalindustry/trade-rules-trump-administration-revises-export-restrictions-advanced--pracin-2026-03-13/ |
| EV-03 | Jan 29 | Samsung memory shortage report; higher prices squeeze smartphone makers; Apple warns | memory suppliers + margins; handset chip demand - | opposite sign across subsectors | https://www.investing.com/news/stock-market-news/samsung-sk-hynix-warn-of-squeezed-chip-supplies-for-pcs-phones-due-to-ai-boom-4472275 |
| EV-04 | Feb 4 | Nvidia H200 shipments to China stalled despite narrower license relief | Nvidia geographical access -; domestic Chinese alternative + | license is dynamic, not categorical | https://www.reuters.com/world/china/nvidia-ai-chip-sales-china-stalled-by-us-security-review-ft-reports-2026-02-04/ |
| EV-05 | Feb 25 | DeepSeek gave domestic chipmakers early AI model optimization access rather than Nvidia/AMD | design ecosystem competition, mixed sector | analysts disputed material impact | https://www.reuters.com/world/china/deepseek-withholds-latest-ai-model-us-chipmakers-including-nvidia-sources-say-2026-02-25/ |
| EV-06 | Feb 26 | Nvidia shares ~-4% after strong earnings/forecast | expectations/ROI/rich pricing dominate absolute result | negative surprise in price, despite positive fundamentals | https://www.reuters.com/business/nvidia-shares-open-firmer-frankfurt-higher-earnings-forecast-2026-02-26/ |
| EV-07 | Mar 2–9 | Iran conflict, energy/oil shock, equities whipsaw with geopolitical remarks | oil -> inflation -> yields -> AI discount rate; fuel/transport costs | Mar 9 reversal; crowded confounds | https://www.reuters.com/business/wall-st-futures-slump-iran-war-drags-oil-near-120-stokes-inflation-worries-2026-03-09/ |
| EV-08 | Mar 5–31 | Qatar natural gas/helium disruption, input risk in wafer fab | supply-chain cost / bottleneck, potential negative | Korean chip firms said inventories 4–6 months, no proven near-term production stop | https://www.reuters.com/business/retail-consumer/south-korean-chip-industry-worried-iran-crisis-affect-middle-east-data-center-2026-03-05/ ; https://www.reuters.com/world/asia-pacific/helium-shortage-has-started-impacting-tech-supply-chains-execs-say-2026-03-26/ ; https://www.reuters.com/business/energy/helium-stocks-south-koreas-chipmakers-last-until-june-sources-say-2026-03-31/ |
| EV-09 | Mar 30 | SOX trough later used as base for spring rally | risk-regime shift reference point, **retrospective** not live-entry signal | subsequent +64% by May 13 reported | https://www.reuters.com/business/sizzling-semiconductor-trade-risk-cooling-stalling-us-stocks-rally-2026-05-13/ |
| EV-10 | Apr 3 | US Match Act proposal: chip-equipment export restrictions | equipment China sales - / other regional capacity + | proposal, not enacted law; avoid mislabeling | https://www.reuters.com/world/china/us-targets-chinese-chipmaking-with-proposed-export-restrictions-asml-others-2026-04-03/ |
| EV-11 | Apr 16 | TSMC upgrades 2026 revenue/capex; Q1 record profit | semiconductor AI demand + | Middle East macro uncertainty remains | https://www.investing.com/news/stock-market-news/tsmc-lifts-revenue-forecast-pledges-more-capital-spending-to-meet-ai-chip-demand-4616954 |
| EV-12 | Apr 22 | ASML advanced lithography capacity, AI demand, China-rule concern | equipment orders +, licensing risk - | shipment bottleneck / lead times | https://www.reuters.com/business/asml-says-firm-will-not-be-chip-industrys-bottleneck-2026-04-22/ |
| EV-13 | Apr 27–28 | Korea/Taiwan chip-led record close and stronger Asian data | earnings rebound +, AI capex + | broad rally includes oil/diplomacy uncertainty | https://www.reuters.com/world/china/global-markets-view-europe-2026-04-27/ |
| EV-14 | May 13 | SOX +64% since Mar 30, stretched valuations warning | momentum/positioning; whipsaw potential | **cumulative SOX price change, not SOXL** | https://www.reuters.com/business/sizzling-semiconductor-trade-risk-cooling-stalling-us-stocks-rally-2026-05-13/ |
| EV-15 | May 20 | pre-Nvidia earnings chip rally, Nasdaq +1.55% | event anticipation / macro rates | pre-earnings expectation, not durable positive shock | https://www.reuters.com/business/us-stock-futures-climb-chip-stocks-rebound-ahead-nvidia-results-2026-05-20/ |
| EV-16 | May 31 / Jun 1 | US tightening of AI-chip shipment loophole for Chinese firms overseas | exports constraint | implemented guidance vs prospective regulations separate | https://www.reuters.com/world/china/us-takes-step-halt-nvidia-ai-chip-shipments-chinese-firms-outside-china-2026-05-31/ |
| EV-17 | Jun 24 | OpenAI announces Broadcom-designed custom inference chip | Broadcom/TSMC supply +; Nvidia share-of-wallet pressure | positive *chip-system* demand doesn't imply positive NVDA | https://www.reuters.com/world/asia-pacific/openai-unveils-custom-chip-it-designed-with-broadcom-boost-its-ai-infrastructure-2026-06-24/ |
| EV-18 | Jun 25 | Micron demand/contract commitments, global chip rebound | HBM/DRAM pricing + | Reuters SOX +3.2% same day; not causal attribution | https://www.reuters.com/world/asia-pacific/south-korean-chip-shares-rally-after-microns-upbeat-earnings-2026-06-25/ ; https://www.reuters.com/business/nasdaq-futures-jump-2-micron-qualcomm-forecasts-relieve-investors-2026-06-25/ |
| EV-19 | Jun late / Jul 17 | July chip pullback after June all-time high; Moonshot AI model and leveraged unwind | margin, momentum, AI ROI doubts - | SOX >20% off June high by Jul 17, weekly -~10%; multi-cause | https://www.reuters.com/world/asia-pacific/chipmakers-other-high-flying-stocks-slide-ai-trade-wobbles-2026-07-17/ |
| EV-20 | Jul 8–14 | China H200 partial approvals and initial Nvidia shipments | Nvidia export market mixed; Chinese substitution continues | policy changes can reverse; size initially limited | https://www.reuters.com/world/china/china-plans-let-top-ai-firms-buy-limited-amount-nvidia-h200-chips-information-2026-07-08/ ; https://www.reuters.com/world/china/us-official-says-shipments-h200-chips-china-have-begun-2026-07-14/ |
| EV-21 | Aug 6 (Jun data) | SIA sales: June $134.5bn, Q2 $403.3bn, AI demand boom | structural industry sales momentum + | SIA monthly data = 3-month moving average, slow and lagged vs share prices | https://www.semiconductors.org/global-semiconductor-sales-increase-35-1-from-q1-2026-to-q2-2026/ |
| EV-22 | Aug 18 | oil/bond yields rise, SOX ~-5% on day | rates/AI discount + financed capex cost - | contemporaneous news attribution, macro & sentiment confounded | https://www.reuters.com/business/us-stock-futures-drop-fading-iran-peace-hopes-lift-oil-bond-yields-2026-08-18/ |
| EV-23 | Aug 27 | Nvidia unusually long-dated forecast +70% next fiscal revenue, sector rally | credible long-horizon earnings guidance + | NVDA up strongly; optimistic shock can counter fear | https://www.reuters.com/business/nvidia-rises-after-signaling-longer-ai-spending-runway-2026-08-27/ |
| EV-24 | Sep 2 | Broadcom AI ASIC/network revenue outlook raised | AI spend broadens beyond GPU +; vendor dispersion | next-quarter guidance mixed; not guaranteed sector alpha | https://www.reuters.com/business/broadcom-forecasts-quarterly-revenue-below-estimates-2026-09-02/ |
| EV-25 | Sep 21 | AMD, Intel, Arm rallies; SOX +4.3% | rate/oil relief + and AI equity enthusiasm | one day, many correlated announcements | https://www.investing.com/news/stock-market-news/tech-leads-shares-higher-in-asia-oil-eases-4908206 |
| EV-26 | Sep 23 | Reuters regulatory review of ongoing BIS controls | evolving restrictions / governance risk | explain rule-by-rule, do not collapse into 'ban' | https://www.reuters.com/legal/legalindustry/whats-latest-with-semiconductor-export-controls--pracin-2026-09-23/ |
| EV-27 | Sep 30 | Micron Q4 earnings, forecast, customer commitments | memory supply/demand + | primary SEC filing, revenue forecast $61.5bn; check post-market timing before event-study event day | https://www.sec.gov/Archives/edgar/data/723125/000072312526000018/a2026q4ex991-pressrelease.htm |
| EV-28 | Oct 5 | SIA Aug sales $159.7bn, +8% MoM +144.3% YoY; 18th consecutive monthly growth | strong fundamentals + | backwards-looking, 3-month-average data; chips still sold off in Oct | https://www.semiconductors.org/year-to-date-global-semiconductor-sales-top-1-trillion-through-august/ |
| EV-29 | Oct 12 | Microsoft Maia 300 custom AI chip plan | custom design supply chain +; NVDA mix/substitution ambiguous | projected 2027 deployment, not proven shipped demand | https://www.reuters.com/business/microsoft-plans-huge-deployment-its-own-ai-chips-with-an-eye-saving-costs-2026-10-12/ |
| EV-30 | Oct 12 | Global smartphone Q3 units ~-20% on memory cost/shortage | consumer end market -; memory pricing suppliers + | 2-sided demand story, no uniform chip impact | https://www.reuters.com/business/retail-consumer/global-smartphone-shipments-record-worst-third-quarter-14-years-amid-memory-2026-10-12/ |
| EV-31 | Oct 13 | China CXMT memory technology progress reports; Micron/SK Hynix pressure | anticipated future supply competition - | viability/production scale unproven; not a mature HBM product | https://www.reuters.com/world/china/us-chip-stocks-extend-slide-china-memory-report-ai-spending-jitters-hit-sector-2026-10-13/ |
| EV-32 | Oct 13 | IDC China AI chips market-share report NVDA ~34% and Huawei growth | China-local substitution, export policy | H1 share observation versus worldwide demand; do not extrapolate immediately | https://www.reuters.com/business/retail-consumer/nvidias-china-ai-chip-share-falls-huawei-closes-gap-report-finds-2026-10-13/ |
| EV-33 | Oct 14 | ASML strong long-term order book despite market turmoil | capex still strong, equipment lead time risk | ASML bullish demand does not automatically support overall sector equity | https://www.reuters.com/business/asml-forecasts-q4-sales-above-expectations-ai-chip-demand-2026-10-14/ |
| EV-34 | Oct 15 | TSMC Q3 record earnings, cautious 2027 commentary | AI demand + but valuation and macro concern - | underlying TSMC strong while sector fell | https://www.reuters.com/world/asia-pacific/tsmc-expected-report-sixth-straight-quarter-record-profit-thanks-ai-boom-2026-10-14/ |
| EV-35 | Oct 13–16 | US inflation & yields, Iran energy disruption, CoreWeave/neocloud bond stress and AI capex ROI debate | **credit-funding** risk channel / broad repricing - | 10/16 Nasdaq SOX -3.83% by Nasdaq official index, broad multi-factor event; other sources differ if intraday and post-close | https://www.reuters.com/business/coreweave-shares-bonds-headed-steep-weekly-losses-ai-borrowing-concerns-mount-2026-10-16/ ; https://www.reuters.com/business/wall-st-futures-mixed-tech-wobbles-again-tesla-gains-2026-10-16/ ; https://indexes.nasdaq.com/Index/Overview/SOX |
| EV-36 | Oct 14–16 | Proposed US Match Act DUV export constraints, SK Hynix seeks license flexibility | capex geography and US tool sales mixed | proposal/negotiation, not final implementation | https://www.reuters.com/technology/asml-cfo-says-us-match-act-limiting-duv-sales-china-would-be-counterproductive-2026-10-14/ ; https://www.reuters.com/world/asia-pacific/sk-hynix-conditions-new-us-factory-more-us-chip-equipment-exports-china-sources-2026-10-15/ |

## 3. Relationships: qualitative evidence rank

| Candidate relationship | Mechanical rationale | Evidence status | Confound / contradictory observation |
|---|---|---|---|
| Unexpected sustained AI capex guidance vs semiconductor equity returns | improves future earnings expectations | Repeated directional examples (Jan 15, Apr 16, May rally, Aug 27), **not quantified statistically** | Feb 26 / Oct 15 good earnings met negative valuation response |
| Real yields/rate expectations / oil shock vs semiconductor returns | discount rates, project borrowing cost, demand outlook | Repeated negative concurrent selloffs Mar, Aug 18, Oct; **not tested conditional on Nasdaq** | falling yields during October bond flight did not necessarily rescue semiconductor shares |
| Neocloud corporate credit spreads vs semiconductor equity returns | AI demand chain depends on debt availability / monetization | strong economic mechanism, Oct 2026 contemporaneous evidence, **insufficient sample** | profitable hyperscalers may differ from debt-heavy neoclouds |
| Memory sales/prices vs MU/other DRAM equities | current revenue/gross margin | strong company-specific direct mechanism, June/Sep results | consumer end-markets hurt by expensive memory; index-level sign ambiguous |
| US China restrictions vs chip equities | addressable market change, rival development, equipment geo-diversion | specific company effects credible; market sign ambiguous | exemptions and case-by-case approvals; proposed bills not law |
| Geopolitical energy shock vs chip stocks | inflation/interest rates and helium supply | Mar 2026 detailed mechanism; contemporaneous | Taiwan/Korea inventory prevented immediate stoppage; oil and index change move together with many macro events |
| AI custom silicon uptake vs semiconductor industry stocks | alternatives to NVDA GPUs but demand for AVGO/TSMC/memory | industry-wide demand can rise while vendor share shifts | so no blanket sector sign |
| Market crowding/leverage/correction | forced selling nonlinear; cross-sector propagation | July 2026 report supports, qualitative | actual ETF flows/options open interest needed to prove mechanism |
| Industry revenue YoY vs near-term SOXL returns | sector-cycle health but valuation forward-looking | **2026 direct counterexample:** Aug semiconductor sales strong but Oct equity selloff | release lag; survival/valuation and macro |

**Status:** RELATIONSHIPS PLAUSIBLE OR OBSERVED IN NEWS, ZERO SIGNIFICANT CAUSAL/STATISTICAL RELATIONSHIPS CLAIMED.

## 4. Proper event-study methodology (next work, NOT yet performed)

Data requirements:
- Official ICESEMIT daily OHLCV (SOXL actual underlier), SOXL split/distribution-adjusted close/open, SOX (comparison only), SOXX, QQQ, SPY.
- High resolution (minute or timestamp-aligned) return data for market-moving reports; publication timestamp UTC/ET and surprise vs expectations, corporate earnings after hours mapped to **next tradable bar**.
- FRED DGS10, DGS2, TIPS real yield DFII10, Brent futures or BZ=F, HY option-adjusted spreads BAMLH0A0HYM2, VIX, SOXX/SOXL trade volume, dollar index, 10-year yields and liquidity.
- SIA/WSTS monthly releases as **availability-timestamped** and YoY/base effects controlled. Raw US industrial data and semis capex revisions via quarterly filings.
- Quarterly/weekly levels of hyperscaler capex guidance change versus consensus; neocloud credit spread, semis earnings surprise.
- Export rules coded as proposed/passed/effective/waived.
- Distinguish broad industry and different segments (GPU, foundry, HBM, analog, tools, networking).

Estimation:
- Event window [-1,+1], [0,+1], [+1,+5] trading sessions, each with at least 20–60 prior clean days for benchmark-model estimate, excluding overlapping event clusters. Include pre-market and after-market timing.
- Abnormal returns \(AR_{i,t}=R_{i,t}-(\alpha_i+\beta_i R_{market,t})\), plus factor controls; compare chip index return minus Nasdaq; quantify coefficient, standard error, p-value, CI, effect-size.
- Event labels and sign set **before** seeing returns; benchmark normal returns QQQ/SPY; random placebo dates, matched controls, bootstrap clustered by event date; multiple testing correction; no data mining.
- For policy and macro events with overlapping news, use narrative analysis and label MULTI-CAUSE rather than attribution from price alone.
- Aggregate surprising vs already priced-in information (forecast revision, rates surprise, event vs expected earnings).
- Consider causal direction risk (selloff -> negative news coverage) and reverse causality (bond yields move due to AI risk).
- Reproduce with time-cutoff freeze 2026-10-17; later data append separately.

Testing decision thresholds: No fixed 'positive correlation' or buy signal without reproducible event-study, rolling out-of-sample, cost and risk analysis. Research finding is not trade authorization.

## 5. Implications for SOXL October–December research

**Observations:** (1) semiconductor company demand remains objectively strong in 2026 (SIA, Micron/ASML/TSMC); (2) equity prices in July and October sold off despite strength; (3) oil/rates/credit conditions are often more important near-term than demand reports; (4) AI spending concerns and credit stress can dominate traditional earnings momentum; (5) high leverage can produce brutal false-bottom losses.

**Working conjunctive gating hypotheses to test, NOT SIGNALS:**
- Price: ICESEMIT closes above prior swing low and moving average with improving breadth (do not rely on SOX sole proxy).
- Macro: 10-year yield and inflation expectations stabilize (specify absolute or z-scored changes before testing).
- Credit: CoreWeave / AI infra financing spread and HY spreads stabilize or tighten (avoid noisy single-issuer data).
- Demand: TSMC/ASML/MU/AVGO earnings revisions do not materially deteriorate.
- Volatility: 20d realized volatility drops below historical extreme regime, no forced unwind signs.
- Calendar: year-end liquidation independently tested against trend exit; don't force entry in November if filters fail.

## 6. Source credibility, conflicting sources, known deficiencies

- Prefer SIA/WSTS official aggregates, SEC filings, Direxion/ICE NYSE underlier, BIS/U.S. announcements, TSMC/Micron investor filings. Reuters contemporary for event narratives; pundit pieces lower evidentiary tier.
- Beware Nasdaq / beta site intraday snapshots or stale cache with inconsistent latest SOX figures. For illustrative single-day use dated main page 10/16 -3.83% (confirm close in data feed before quantitative study).
- All media price claims are unadjusted unless stated; percentages may be premarket/intraday instead of close.
- No licensed daily OHLCV, actual ICESEMIT history, yield surprise history or trade blotter has been obtained and verified in this turn. **NO formal cross-correlation, hypothesis significance, event alpha, or causal estimate has been computed.**
- The list includes 36 *material source-supported event entries*, not all news globally. Further expansion requires primary-source feed, deduplication, and sector/geography sampling.

## 7. Next concrete deliverables

- [ ] Acquire timestamped official ICESEMIT and asset-price/yield datasets via legitimate accessible data providers.
- [ ] Normalize event ledger to CSV/JSON schema {id, announcement_time, publish_utc, last_knowable_time, type, status, region, affected_securities, surprise, source, prior_expectation, outcomes, classification, conflict_links}.
- [ ] Build reproducible event study and abnormal returns report with null/permutation tests. Classify 'statistically significant', 'not significant', 'unidentifiable' strictly by evidence.
- [ ] Backtest additional macro/credit filters nested with original E1–E4, avoid overfitting and pre-register tests.
- [ ] Check overlapping macro events in March, July and October for confounds. Persist negative evidence.
- [ ] Weekly observational updates append-only to Issue #129 and artifacts; private holdings never added.
