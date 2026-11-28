# QT-PIO-2026-11-27 — Portfolio research archive & automation handoff

Status: RESEARCH ONLY / NO_TRADE / NO_PRODUCTION_CHANGE. Source: founder's portfolio research conversation, 2026-11-25–27 (Research 01–05, portfolio V1.3–V2.4), plus existing research index. Historical conversation outputs below are transcribed, NOT independently reproduced or validated in this handoff. Raw datasets, source URLs, code hashes and exact execution artifacts for chat calculations are not present here; no numerical result may become live policy merely by appearing in this archive. No personal balances, orders, holdings quantities or account identifiers in this public repository.

## Founder intent and decisions to preserve
- Small seed accumulation before later capital expansion; long-term goal sustainable monthly distributions and financial independence. Growth and total return first; avoid prematurely maximizing distribution yield. Reinvest distributions in accumulation; separately model after-tax income phase.
- US and Korea balanced by opportunity and economic risk, not mechanical 50:50. Japan/global equity and currency exposures, cash/short bills/gold as candidate diversifiers. Domestic listing does not imply domestic economic exposure; energy equity is not oil hedge.
- Seek opportunities broadly across sectors, not just existing watchlist; intrinsic value, technical timing, business prospects, macro, risk, and opportunity cost. Buy in whole shares, no fractional orders. Reduce overvalued/invalidated theses, not every winner. Avoid reflexively buying every dip or selling every rally. Manual decision/approval, no broker action authorized.
- Numerical report and actionable research/decision list rather than elaborate dashboard. Keep rejected ideas, uncertainty and missed opportunities. Separate daily market updates from event-driven financial updates; program calculates, LLM interprets. Do not re-search unchanged evidence every day.
- Proposed neutral allocations (not optimized): core market ETFs 35%, quality growth/value 30%, tactical 10%, income 10%, cash/hedge 15%. Earlier defensive cash 20–25%; proposed dynamic range 5–40% not approved or validated. Long horizon allocation and tactical sleeve distinct. Growth phase vs income phase; cash required for life needs outside investment mandate.
- Valuation entry hypothesis: 15% safety margin starter, 20% regular, 30% stronger; wider for speculative/uncertain assets. No threshold overrides impaired fundamentals, stale evidence, pending orders or position limit. ETF periodic allocation separate from individual equity DCF. Scores are subjective, not probability or expected return. Suggested six-component weights 25/20/20/15/10/10 (value, quality, growth, technical, macro, fit); historical reports used other weights too; must version and calibrate, never retrofit.

## Research history and evidence status
| ID | Work | Reported result / lesson | Status and next step |
|---|---|---|---|
| R01A | JEPI/JEPQ vs SPY/QQQ/SCHD 2022-05-04–2026-09-18 | reported total returns +37.99/+91.78/+88.56/+124.72/+49.85%; upside trade-off, distribution != return | CHAT_REPORTED; reproduce adjusted NAV/price, dividends, fees and Korean taxes; check same-day inception and currency |
| R01B | ETF look-through VT/JEPI/JEPQ/XLP/XLV | Alphabet direct plus indirect, overlapping tech, XLP/XLV tilts rather than new exposure | PARTIAL; obtain dated full holdings, class mapping, derivatives/ELN delta, coverage residual |
| R01C | 2016–25 annual US/Korea/gold/bonds/cash allocation | reported CAGR SPY 14.72%, SPY75/EWY25 14.01%, SPY60/EWY20/GLD10/IEF10 12.94%, replace IEF with zero cash 12.87%; Korea not guaranteed hedge | CHAT_REPORTED; reconcile annual prices vs total return, KRW and monthly/daily drawdown |
| R02A | 2016–25 monthly S&P price returns; 100% / 85% fixed / defensive / contrarian | reported CAGR 12.86/11.00/10.16/11.42%; equal exposure comparison contrarian +0.17pp, defensive -0.51pp | CHAT_REPORTED; rerun exact rules/costs, holdout |
| R03A | 2025 monthly HY OAS 4pp threshold | reported 100% 16.35%, fixed 13.83%, dip 14.38%, credit filter 12.33%; filter triggered once and missed rebound | EXPLORATORY_CHAT; HY history constraints, no inference from one event |
| R05A | 2000–25 312 monthly S&P price returns | reported CAGR 100% 6.12%, fixed85 5.33%, dip 5.56%, defensive 4.85%; month-end MDD -52.57/-46.65/-51.52/-38%; matched exposure dip 5.69%, defensive 4.77% | CHAT_REPORTED; rounded input, no dividends/FX/cash yield, not independently reproduced |
| R05B | Baa minus Treasury monthly (BAA10YM), lag 2 months | reported absolute 3.5pp trigger 15 months CAGR5.50%; 3m widening>=0.5pp 19 months CAGR5.44%; both 7 months CAGR5.86%, matched fixed5.65% | EXPLORATORY_CHAT; small trigger sample, vintage/OOS/daily not done; Baa is not HY OAS |
| R05C | public screens KR/US | reported external counts 2772/899, ~5510/214; not independent full-universe scan | CANDIDATE_DISCOVERY_ONLY; obtain point-in-time universe and licensed fundamentals |
| R05D | decision tracking | 1/5/20/60/120 sessions total return, benchmark excess, MAE/MFE, drawdown; include rejected cases | DESIGN_ONLY; immutable records, no retroactive dates or selective logging |

Monthly experiments: weights from prior month-end drawdown, next period returns, 0.1% traded notional, zero cash yield; fixed 85%; dip 95% at -8%, 100% at -15%; defensive 75/60%. 2025 pilot used -5/-10% thresholds, not same model. Baa overlay equity 65% when rule fires; observed monthly Baa two months lag, not proof of true historical availability. Reported results must be rerun; no OOS significance claimed. Equal-exposure benchmark is ex-post diagnostic, not live alternative. Extend existing QT-MRI #135 and Data Vault #137/#138; BNF25 #133 remains G0 BLOCKED. Do not conflate market timing with cross-sectional stock selection.

## Historical company case ledger (USD except KRW rows)
All prices/values are reported November 2026 research snapshots, NOT current verified market data or live targets. Model assumptions and input artifacts incomplete; rederive before publishing actionable report. Safety margin = 1-price/value. Values are not comparable without model-type and confidence metadata.

| Asset | Reported reference price | Base value / model | Case-specific evidence and blockers |
|---|---:|---:|---|
| GOOGL | 273.10 | 272.28 / FCFF scenario | cloud growth, search resilience; capex 9m 132B vs OCF127B, dilution, debt; model FCFF recovery and avoid double counting investments |
| MNST | 42.60 | 27.89 / DCF | strong brand, low capex; margins and FCF lag revenue; reverse DCF; split adjustment check |
| 196170 Alteogen | 185779 approx | 190400 prior whole-company hypothesis | MSD SC sales and milestone; residual MSD contract base 20090/share reported; no double count milestone and royalty, royalties after contractual milestones, other pipelines not modeled; whole value UNVALIDATED |
| 000270 Kia | 93700 | 120127 / normalized CF; EPS alternative112000 | cyclicality, tariff, margins, EV; separate NCI/net financing/cash |
| 005380 Hyundai Motor | 259000 | 272000 / EPS multiple | finance segment separate SOTP, production disruptions, overlapping auto risk |
| 033780 KT&G | 179500 | 178226 / CF | overseas growth, distributions, working capital normalization, tobacco regulation |
| V | 424.39 | 303.47 / CF | strong cash margin, incentives, litigation, valuation/whole-share size |
| 021240 Coway | 99700 | BLOCKED | finance lease receivables, cohort cash recovery, financing cost; accounting OCF may misrepresent expansion economics |
| SEIC | 102.96 | 94.31 / CF | AUM cyclicality, affiliate distributions, SBC, differing source prices |
| ACN | 240.49 | 210.79 / CF | AI disruption vs adoption, SBC, recurring acquisitions vs growth spending |
| 105560 KB | 145300 | 154377 / justified P/B | normalized ROE10.5%, Ke11%, g3%; penalty correction, CET1 |
| 055550 Shinhan | 84700 | 106285 / justified P/B | ROE10%; CET1, credit costs and latest BPS |
| 086790 Hana | 119200 | 133881 / justified P/B | ROE9.5%; credit and FX |
| 086280 Glovis | 202500 | 214805 / CF after lease principal | auto correlation, freight, fuel, lease and ship costs |
| 383220 F&F | 60400 | 73021 / stand-alone CF | TaylorMade acquisition economics and financing unknown; value not acquisition-adjusted |
| ICE | 177.81 | 161.10 / CF | exchange moat, mortgage segment, acquisition debt; deal assumptions verify |
| TSM | 342.34 | 189.76 / CF per ADR | ADR 5 shares, TWD FX, capex, geopolitics; verify EPS/DCF reconciliation |
| TDC | 37.42 | 29.44 / normalized CF | settlement inflates FCF, recurring growth low, SBC normalization |
| GAP | 23.21 | 23.15 / adjusted EPS multiple | tariff refund, normalized EPS, apparel cyclicality |
| HRMY | 35.26 | BLOCKED | WAKIX concentration, generic entry around 2030; finite patent-life rNPV |
| 310200 Aniplus | 2020 | 1500 / normalized EPS | falling margins, content rights amortization/cash capex, Laftel integration |
| 037440 Heerim | 3330 | 2970 / normalized EPS | receivables, negative operating CF, low margins, backlog conversion |
| CMCSA | 25.73 | 28 / EPS multiple | broadband competition, spin-off perimeter and debt |
| PG | 173.23 | 154 / EPS multiple | slow growth, input costs |
| REGN | 981.87 | 960 / EPS multiple | partnership one-offs, patent/pipeline, whole share size |
| SK Gas / VST / Samsung Fire | separate legacy targets | unverified | debt refinancing, power hedges & growth capex, insurance capital/ROE; refresh model |
| VT/XLP/XLV/AVUV/IJR/TOPIX | ETF | allocation/earnings multiple scenarios, not single-firm DCF | full holdings, tracking, valuations and FX; AVUV factor/risk comparison |
| SGOV/BIL/KOFR/KRX gold/GLDM | cash & diversifiers | yield/FX/fees/tax | KRW historical total returns and liquidity; no automatic hedge claim |

New candidate discovery (not validated): NICE Information Service 030190 (not NICE Holdings), Korea Ratings, Cheil Worldwide, SOOP, Samsung E&A, Classys, BGF Retail, Hylok Korea, Kukbo Design, i-Scream Media, ANIP, RNG; broader sectors payment MA/V, data SPGI/MCO, exchanges CME/ICE, industrial automation ROK/ABB/Keyence, TSM/ASML/Samsung Electronics, medical devices ISRG/ABT/SYK, waste WM/RSG, water MWA/VLTO/AWK, aerospace/defense, logistics UNP/Glovis. NICE/Korea Ratings next research, not buy recommendations.

Legacy 24 watch universe: Samsung Fire, COR, MWA, CB, EOG, FN, POWL, CME, VLTO, MNST, SK Gas, VST, LNG, HD Hyundai Electric, Hyosung Heavy Industries, VRT, VT, XLV, XLE, XLP, REGN, PG, CMCSA, HMM. Keep watch universe independent of recommendation ledger. Do not overwrite existing automation thresholds or issue history.

## Remaining work and acceptance gates
1. Reuse Data Vault P0 and existing feature-provider seam; no duplicate production provider. Data provenance/rights, local raw archive, PIT versions, corporate actions, backup/restore before real backtests. Existing PC-access deferral remains; no paid storage or scheduled jobs enabled.
2. Financial statements normalized by issuer, period, currency, restatement and publication date; source links, raw hashes and line-item mapping; prove reconciliations, industry-specific exceptions.
3. Reproduce all historical experiments from frozen inputs; immutable config/code hash, signal timing, costs, cash yield, tax/FX scenarios; matched risk/exposure benchmarks and walk-forward OOS. Include delisted names and true historical constituents before full-universe alpha claims.
4. Full ETF holdings snapshots, derivative look-through or explicit unknown exposure; KRW total return panel for hedges; compare cash vs short bills net of friction.
5. Biotech rNPV (Alteogen, HRMY), F&F deal, Coway lease cohort, NICE/Korea Ratings; no unsupported contractual or probability assumptions promoted.
6. Decision journal and future outcomes, including rejected/held/unfilled orders; no fabricated entry. Private account data and actual trades outside public repo.
7. See AUTOMATION_SPEC_2026-11-27.md and research config draft. Research only; governance and independent risk approval required before any operational adoption.

Security identity correction: Aniplus 310200 verified in KRX filing https://kind.krx.co.kr/external/2026/05/08/000185/20260508000437/00634.htm ; remaining case identifiers require master-data verification before ingestion.
