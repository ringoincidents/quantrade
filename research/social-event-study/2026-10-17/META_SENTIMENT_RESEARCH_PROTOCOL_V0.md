# QuanTrade QT-META-2026-001 — 2차 여론 / 역지표 주장 / 자기참조적 투자심리 연구

- 작성 및 기준일: **2026-10-17 KST**
- 상태: **CURATED CASE STUDY + DESIGN; NO VERIFIED FORWARD SIGNAL, NO LIVE ORDER AUTHORITY**
- 연결: [SOXL study #129](https://github.com/ringoincidents/quantrade/issues/129), [news/social sentiment #130](https://github.com/ringoincidents/quantrade/issues/130)
- 이 문서는 **상업/연구용 플랫폼 데이터 라이선스를 확보하지 않았으며** 무단 자동 크롤러를 배포하지 않음.
- 원문과 작성자명/익명 사용자ID를 공개 기록에 대량 저장하지 않음.

## 최초 검증 가능한 근거

1. [미국주식갤러리 2026-07-04 16:31](https://gall.dcinside.com/mgallery/board/view/?id=stockus&no=16682249): 집단이 상승 시 고위험 레버리지 추격, 하락 시 지수투자/숏으로 전환한다는 글, 갤 반대 매매 가설. 저자의 서술이지 실제 모집단 분석 결과가 아님.
2. [r/wallstreetbets 2026-05-26](https://www.reddit.com/r/wallstreetbets/comments/1toknrb/the_market_will_continue_being_bullish_as_long_as/): 게시판 비관론을 상승 신호라 보는 원글 + 반대 의견을 또 반대로 적용하자는 댓글, 자기참조 역설.
3. [r/SOXL 2026-07-30](https://www.reddit.com/r/soxl/comments/1vay6w3/good_thing_i_held_a_bit_longer/): 한국 투자자들이 청산했다는 믿음을 상승의 근거로 사용하는 댓글. 청산 여부 및 규모는 확인되지 않음.
4. [r/SOXL 2026-07-27](https://www.reddit.com/r/soxl/comments/1v828iu/its_time_to_admit_it_flaky_was_right/): 하락 이후 예측자의 과거 평가가 바뀌는 글. 사후 평판 재구성 가능성.
5. [r/SOXL 2026-10-02](https://www.reddit.com/r/soxl/comments/1wvx45p/just_went_all_in/): 돌파 후 전액매수 호소에 대해 군중 추격의 위험을 직접 비판하는 댓글.
6. [Stocktwits SOXL 2026-10-16](https://stocktwits.com/symbol/SOXL): 분석가들이 SOXL 개별 가격선만 보는 것을 비판하는 글; 저자의 '3x SOXX' 설명도 사실과 다름. SOXL 공식 기초는 **NYSE Semiconductor Index**, SOXX가 아님.
7. [Stocktwits SOXL 2026-10-16](https://stocktwits.com/symbol/SOXL): 지난 뉴스가 현재 신규 뉴스인 것처럼 재공유된다는 비판. 원 게시자의 개별 주장으로서 독립 검증 필요.
8. [Stocktwits SOXL 2026-10-16 snapshot](https://stocktwits.com/symbol/SOXL): SOXL 당일 종가 $93.67 (-12.74%)와 홈페이지 심리지수 84/100 'Extremely Bullish'가 동시에 표시됨. 24시간 rolling 심리지수 + 가격 표시시각이 완전히 동일하지 않으므로 사건적 **괴리 관찰**만 허용. 분모/표본/조작 가능성을 확인하기 전 매수 신호로 취급 금지.

실제 사례 목록 (첫째 시점 검증 안 됨): [meta_sentiment_cases_v0.csv](./meta_sentiment_cases_v0.csv). **14개 선별 사례 중 예측에 쓰일 수 있는 과거 first_seen timestamp 검증 자료는 0건.** 개별 평가(직접 분석/2차 반응/둘 다)와 유효 표본 여부를 별도 보존함.

## 핵심 구분: 1차 / 2차 / 3차 (재귀)

- **L1 first-order**: 'SOXL 상승/하락 예상', '매수/매도'.
- **L2 second-order**: '사람들이 SOXL 상승을 예상하므로/물타기를 하므로 XX가 일어날 것이다', '갤이 확신하니 조심', '다들 포기했으니 바닥이다'.
- **L3 recursive/third-order**: '다수가 역지표라고 생각하기 때문에 역지표가 더는 작동하지 않을 것이다'.
- **Information-quality meta**: '속보라며 2일 전 뉴스 재전파', '기초지수 혼동', '이미 가격 반영된 정보'.
- **Authority meta**: 예측자가 맞거나 틀린 뒤 상대 평가·팔로워 반응 변화.

### 새 라벨과 독립 축

`stance_target`: SOXL/underlier/individual stock/community/unknown
`discourse_layer`: direct / meta / mixed / unknown
`meta_type`: inverse_crowd_forum, recursive_inversion, capitulation_exhaustion, reputation_revision, herd_warning, information_quality, epistemic_uncertainty, anticipated_herd_flows, crowd_following, signal_saturation, etc.
`implied_direction`: bullish / bearish / neutral / ambiguous / conditional
`claims_population_size`: yes/no; `claim_evidence`: published independent dataset / self-report / hearsay / satire / unsubstantiated.
`emotional_tone` and `own_position` are **separate** from *predicted future market direction*. Irony, sarcasm, bots and deletions are nullable/unknown by default.
`link_parent` (reply target thread/message) and `rumor_root` (verified origin of referenced claim) only when allowed and reliably timestamped. Preserve pseudonymity; avoid author tracking or deanonymization.
`score_asof`: votes/reactions and their observation timestamp, **never final future score backfilled as event-time popularity**.

## Event/source scope and staged volumes

### Exploration only (no bulk forum scraper)
- Assets: SOXL first, then SOXX, SOXS, NVDA, AMD, MU, TSM, AVGO; control on sector-unrelated ETF and QQQ.
- Communities: DC stockus/krstock/tenbagger, other SOXL mentions as separately flagged; Reddit r/soxl / r/LETFs / r/wallstreetbets; Stocktwits; Korean stock boards; licensed news and official filings as controls.
- Search vocabulary: SOXL, 속슬, 속쓸, 속쓰, 속슬이, 속스, 갤반꿀, 인간지표, 구조대, 물타기, 손절, 아직 희망, 번지대, 데드캣, 다들 산다, 다들 판다, 이제 끝, 갤 분위기, 디시 역지표, inverse reddit, inverse WSB, everyone bearish/bullish, retail capitulation, contrarian indicator.
- Search index results are **nonexhaustive** and cannot support 'x% bullish' or normalised posting volume.
- Source availability and rate limits: Stocktwits developers page currently says new API registrations suspended; Reddit research-only extraction requires RFR eligibility / formal review (university email + ethics approval); DC/네이버 broad automated access authorization unresolved. Public search result indexing != permission for bulk collection. Confirm rights prior to any API or persistent corpus.

### After authorization + stable collector
- Sample stable registered platforms at a constant cadence, target **one snapshot every 60 minutes** (platform permitting); explicit `published_at`, `first_seen_at`, `retrieved_at`, `edited_at` and `score_asof`.
- Desired valid sample: at least **8–12 weeks** spanning volatile and calm sessions, 20 independent large-move clusters up / down with matched non-event controls; not statistical power guarantee.
- Each platform hour: counts for all authorized relevant hits, random 5–20 source records to blinded annotation when population frame known; not recommendations-sorted posts only. If a platform is blocked/unknown, record missing, don't fill with search-engine guesses.
- Dedup by platform+post id, **not only text**; quote/repost edge distinct; record deletion and downstream link dependence.

## Experiment designs (preregister before outcome)

E0: **reaction** — prior 1h / 1d SOXL and underlying return -> subsequent direct and meta discourse count, category and share. Baseline explanation.

E1: **directional leading** — incremental reduction in next-session return Brier/logloss over price/vol/news/credit baseline when adding L1 text sentiment, then L2 features, then L3; compare the *same verified sessions* and no future timestamps. Also check SOXL actual daily leverage path.

E2: **risk leading** — changes in meta disagreement, 'crowd is wrong' claims and capitulation claims -> next 1d/3d/5d volatility / drawdown, after controls. Predefine horizons and correct multiple tests.

E3: **discussion propagation** — original factual news at t0 -> reactions t1 -> meta commentary t2; test delay & multiplicity of quoted source; do not treat duplicate reposts as independent findings.

E4: **anti-signal** — signals generated from inverse-crowd/real-time 'all-in is a sign of top' claims versus randomly-shifted placebo; no trader's own ex-post 'called it' hindsight incorporated.

E5: **disagreement** — do meta-sentiment reversals add more than 1st-order stance alone? Model C0 (prices) vs C1 (+news) vs C2 (+L1) vs C3 (+L2) vs C4 (+L3).

- Controls: timestamp-verified original news, QQQ/SPY price, exact NYSE Semiconductor Index as SOXL underlier, bond yields/credit when available, day/time, volatility, platform access status. SOXX is *not* official SOXL underlying.
- `published_at_utc` AND `first_seen_at_utc` must be verified. At decision cutoff only values observed at least 15 min earlier; after-the-fact indexed articles never create historical signals. Never use final upvote count after study cutoff.
- Plots: event-aligned first/second/meta rate & volatility; lag-lead exploratory checks; separate bearish, bullish, neutral. Significance: event-cluster block bootstrap, multiple-testing corrections, strict heldout periods, after-cost portfolio stress; no causal interpretation from association alone.
- No live stock execution, no trade approval.

## Pipeline / code

```
rights-verified source adapters (not yet installed)
       |
time/version validation, raw-text retention policy, source citation
       |
L1/L2/L3 multi-label review + rumor/correction link graph
       |
event-time bucketing: premarket / NYSE session / after hours / overnight
       |
read-only retrospective dataset + strictly prospective features
       |
price and news baseline comparison / out-of-sample test
       |
reproducible experiment result / negative evidence
```

[Validator](../scripts/meta_sentiment_validator.py) and [test suite](../scripts/test_meta_sentiment_validator.py) check date-only, first-seen chronology, permissions, pre-registered complete sampling frames and retrospective-source exclusion. **Code is a manual-data validation prototype, not a collector or trained classifier.**

## Status at this cutoff

- Discovery: source-linked *illustrative* L2/L3 examples: **YES**.
- Automated authorized high-rate collection: **NO**.
- Valid representative platform sampling: **NO**.
- Historical meta-claim predictive correctness: **UNTESTED**.
- Stocktwits 84 score as-of: **SINGLE SNAPSHOT**, not a trend and not a buy signal.
- Practical hourly review task: *potentially* scheduled; scheduled search review is NOT a true stream or guaranteed archival of every post.

**Recommendation for research workflow**: Preserve both confirmation and disconfirmation of every meta-signal; abstain (NO_SIGNAL) on missing rights, missing timestamps, missing raw source, or inaccessible historical data. Do not turn the Client's SOXL buy scenario into a post-hoc justification.
