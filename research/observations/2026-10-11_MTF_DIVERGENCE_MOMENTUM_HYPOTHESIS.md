# QuanTrade Research Observation — 다중 시간봉 다이버전스·모멘텀 감쇠 가설

- **Record ID:** QT-OBS-2026-10-11-MTF-DIVERGENCE-001
- **Date / timezone:** 2026-10-11 / Asia/Seoul
- **Class:** `EXPERIMENT` (검증 전 관찰/가설, 실험을 수행했다는 의미 아님)
- **Status:** `OBSERVED_ONLY / NOT_VALIDATED / NOT_DEPLOYED`
- **Direction classification:** `REFERENCE_ONLY + SIMILAR_VARIANT + PROPOSED_EXPERIMENT`
- **Owner:** QuanTrade Research / Technical & Quant
- **Authority:** Research hypothesis only. No portfolio allocation, risk waiver, committee decision, order or strategy adoption rights.
- **Provenance:** 사용자가 2026-10-11 대화에 제출한 외부 대화 스크린샷 다섯 장. 외부 화자·원문 URL·원차트·원자료·매매기록은 미확인. 이미지 원본은 본 GitHub 기록에 복제하지 않았음.
- **Related:** [Canonical vision](../../QUANTRADE_CANONICAL_VISION.md); [2026-10-08 알루코 1분봉 관찰](2026-10-08_ALUKO_1M_MA60_RSI_BB_VOLUME.md); [기존 지표 유의성 보고서](../../indicator_significance_report.json).

## 1. 원 주장과 연구 가능한 주장 분리

외부 대화의 주장은 다음과 같다(직접적 전략 성과 증거 아님).
- 시간규모(1초, 1분, 5분, 1시간, 일, 주, 월, 년) 간의 계층 구조가 있으며 상위 다이버전스 확정 후 하위 구조에서 신호가 실제로 전파되는지 검토할 수 있다.
- MACD 히스토그램·이동평균 이격도·PVO 같은 계산 가능한 지표에서 가격 상승 전의 모멘텀 약화/변화를 관찰할 수 있다.
- 상위 방향 가설과 하위 방향이 충돌하면 상위 예측을 무효로 보아야 한다고 주장한다.
- '에너지 고갈'·'큰 폭발 전 압력'은 외부 화자의 비유로, 검증된 경제물리학 법칙이나 직접 측정된 잠재 에너지가 아니다.

**연구 가능한 핵심 질문:** `P(future reversal | higher-TF divergence, lower-TF confirmation, trend/volatility regime)`가 단일 다이버전스 및 추세·모멘텀 기준선보다 표본 외에서 유의하게 나아지는가?

단위 시간봉을 바꾸면 동일 원자료에서 계산한 상관된 지표가 중첩되어 관찰된다. '하위 시간봉이 상위를 만들고 예고한다', '하위 반대 다이버전스는 상위를 무효화한다'는 주장은 필연적 법칙으로 두지 않고 반증 가능한 가설로 둔다.

## 2. 구성 요소와 계산상의 정확한 의미

- MACD(12,26) = EMA12(close) - EMA26(close)
- Signal(9) = EMA9(MACD), Histogram = MACD - Signal.
- 히스토그램 변화는 MACD와 평활 신호선 간 편차의 변화를 말할 뿐, 가격의 물리적 에너지 또는 미래 가격의 독립 관측이 아니다. 히스토그램은 같은 가격을 이용해 만든 후행/평활 신호다.
- Moving-average distance = (close - EMA_n(close)) / EMA_n(close) 또는 ATR 기준 거리. 가격 단위 그대로 지표 비교 금지.
- PVO = 100 × (EMA_fast(volume) - EMA_slow(volume)) / EMA_slow(volume) (분모 양수일 때). 거래량의 추세·변동 지표이지 매수·매도 주체나 방향의 확정 증거가 아님.
- 서로 다른 세 지표 모두 같은 OHLCV를 변환하므로 지표 개수를 독립 증거 수로 계산하지 않는다.

## 3. 과거 QuanTrade 실험과 연결

2026-08-09 기준 `indicator_significance_report.json`:
- 7종류 신호에 대한 비교, `instruments_used=110`; RSI 다이버전스 분석의 학습 구간 기기 수 `train_n_instruments=109`.
- RSI 다이버전스 `train_p_raw=0.00787`, `train_p_corrected=0.05511`; 보정 후 0.05를 넘었으며 `verdict="우위 없음(폐기)"`. 표본 외 채택 검증 결과도 없음.
- 해당 보고서의 방법론·데이터·시장·기간 제약으로 이번 다중 시간봉 접근의 직접적 반증은 아님. 동시에 이전 실패를 누락하고 새 전략의 '우수함'을 가정하면 안 됨.
- 2026-10-08 알루코 1분봉 MA60/RSI/볼린저/거래량 기록과는 `SIMILAR_VARIANT`; 둘 다 '지표의 변화가 원인이 아니라 관측된 상태'라는 주의가 필요.

## 4. 문헌과 정확한 지지 범위

1. Lo, Mamaysky & Wang (2000), *Foundations of Technical Analysis*, J. Finance. DOI https://doi.org/10.1111/0022-1082.00265 — 기술 패턴을 객관적 연산 규칙으로 전환하고 조건부 수익률 분포 분석. 정확한 MTF 다이버전스 규칙의 성공 입증은 아님.
2. Brock, Lakonishok & LeBaron (1992), *Simple Technical Trading Rules and the Stochastic Properties of Stock Returns*, J. Finance. DOI https://doi.org/10.1111/j.1540-6261.1992.tb04681.x — 이동평균/돌파의 역사적 증거. 이번 규칙 직접 검증 아님.
3. Chong & Ng (2008), *Technical analysis and the London stock exchange: testing the MACD and RSI rules using the FT30*, Applied Economics Letters. DOI https://doi.org/10.1080/13504850600993598 — 특정 지수 역사 표본에서 MACD/RSI 룰 성과. MTF 다이버전스 증거 아님.
4. Chong 외 (2014), *Revisiting the Performance of MACD and RSI Oscillators*, J. Risk Financial Management. DOI https://doi.org/10.3390/jrfm7010001 — 시장 간 외적 타당성과 특정 조건 의존성을 연구. MTF 가설 증거 아님.
5. Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, J. Financial Economics. DOI https://doi.org/10.1016/j.jfineco.2011.11.003 — 58개 유동성 높은 선물의 1~12개월 모멘텀과 장기 부분 반전. 분봉 전략으로 외삽 금지.
6. Park & Irwin (2007), *What Do We Know About the Profitability of Technical Analysis?*, J. Economic Surveys. DOI https://doi.org/10.1111/j.1467-6419.2007.00519.x — 여러 연구의 혼재된 결과와 검증 위험.
7. Sullivan, Timmermann & White (1999), *Data-Snooping, Technical Trading Rule Performance, and the Bootstrap*, J. Finance. DOI https://doi.org/10.1111/0022-1082.00163 — 대규모 매개변수/룰 탐색의 다중검정·데이터 스누핑 위험.

**문헌 판정:** 구성 재료에 근접한 선행 연구는 있음. 사용자 이미지의 특정 '상위 다이버전스→하위 확정/무효화→대변동' 법칙을 직접 증명하는 논문이나 표본 외 성과는 여기서 확보하지 못함. 문헌의 수익 사례를 본 가설의 실증 결과로 둔갑시키지 말 것.

## 5. 사전등록 최소 실험 (아직 실행하지 않음)

### 5.1 종목·데이터

- 먼저 유동성 있는 한국 주식의 5분·1시간 **마감 OHLCV**를 동일한 원천 1분 데이터로 일관되게 집계. 원시 데이터 접근 가능 여부를 선행 확인.
- 세션(정규/애프터), 거래정지, 기업행동, 수정주가, 타임존 및 생존편향 기록. 1분 세부 신호는 추가 데이터 품질 확인 시 2차 실험에만 투입.
- 미래 시간봉의 고가/저가/마감 시각을 현재 데이터에 누출하는 다중 시간봉 병합 금지.

### 5.2 이벤트 정의

- 상위(H=60m) 약세 다이버전스 예시: 가격 고점 2개가 상승하고 같은 확정된 두 고점의 MACD 히스토그램 고점이 낮아진 경우. pivot 확인에 미래 우측 봉 r개가 필요하면 **이벤트 유효시각은 두 번째 고점의 t가 아닌 t+r 이후**.
- 하위(L=5m) 확인 예시: 상위 이벤트 인지 후 최근 확정 5분봉에서 모멘텀 둔화 + 미리 정한 구조적 지지/스윙 저점 이탈.
- 상위 가설의 무효화는 **사전 지정한 가격 장벽·시간 만료·재확률화 기준**으로 한다. '하위 반대 다이버전스 = 자동 무효'는 대안 실험 후보일 뿐.
- 거래는 모든 필요한 봉이 닫힌 이후 다음 실현 가능한 호가/봉에서만 가능하다고 가정.
- 적은 수의 시간봉 쌍/지표/임계값을 사전 확정하고, 전략 탐색 전체를 다중검정 대상으로 기록한다.

### 5.3 비교군과 평가

- B0: 동시간대 무작위 매칭 사건 및 무작위 신호
- B1: 단독 RSI 또는 MACD 다이버전스
- B2: 상위 추세 단독 (예: EMA 방향)
- B3: 상위 추세 + 하위 MACD 모멘텀 단독
- T: 상위 다이버전스 + 하위 확인 + 사전 정의된 무효화

지표:
- 이벤트 다음 5/15/30/60/120분의 **순방향·역방향 수익률 분포**, 큰 변동 발생률 및 **방향 조건부 확률**을 따로 보고. 변동성 예측과 방향 예측을 혼동하지 말 것.
- Precision/Recall, calibrated probability, MFE/MAE, 보유시간, 건수, 중앙값/분위수, bootstrap confidence intervals.
- 실제 거래 전략으로 연구 확장 시 turnover, fees, spread, slippage, partial fills, gross/net PnL, max drawdown, exposure-adjusted benchmark 평가.
- Walk-forward / untouched holdout, 장세·종목·세션별 반례, 다중검정 보정; signal bar open 체결 및 pivot backdating 금지.
- 지표 추가가 단일/기준 신호보다 실질적으로 나아지는 **증분 가치**를 검증. 실패한 조건도 기록.

## 6. QuanTrade 내의 적절한 위치와 권한

가장 먼저 시도할 쓰임새는 `Market State Compiler → Research/Decision Management`에서의 **조건부 재검토 트리거 또는 실행 타이밍 보조**이다. '새 alpha 발견' '매매 자동화' '위험관리 우회'로 승격 금지.

- Data / FeatureProvider: 시간봉 병합 및 지표 재현성
- Research: 명시적 가설과 반가설
- Backtest: 무작위 대조군, bias, 비용·체결·레짐
- Risk & Compliance: 무효화·손실 보호와 검증
- Decision Management: 기존 승인된 투자 결정을 언제 실행할지의 한 요소로만 검토
- Performance & Learning: 과거 RSI 다이버전스 실패와 연결하여 재현 결과 기록

**현재 판정:** `RESEARCH_ONLY / PROPOSE_EXPERIMENT / NO_ALPHA_CLAIM`. 실증 자료 없음. 코드 변경·백테스트·시뮬레이션·주문·자본배분·자동 채택은 이 기록으로 실행/허가되지 않는다. 결과가 나오면 원 기록을 덮어쓰기보다 추가 후속 기록으로 연결한다.
