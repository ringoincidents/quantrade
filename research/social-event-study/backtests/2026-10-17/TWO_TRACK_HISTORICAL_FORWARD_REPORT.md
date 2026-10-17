# QuanTrade — SOXL 커뮤니티 여론 2개 트랙 연구 (2026-10-17)

**상태: 과거 사후 탐색적 검산 완료 + 전향 감시/장부 동결 완료. 과거의 실전 검증된 초과수익/신호: 없음. 전향 검증의 최종 예측성능: 향후 가격·적법한 표본 미확보로 미완료. 자동 주문 없음.**

## A. 과거 사례 검산 결과

- 신규 공개 Reddit 출처는 2023~2025년, 기존 QuanTrade의 Reddit/디시/Stocktwits 사례는 2026년. 2022년 사례 1건은 맥락 전용이며 해당 주가 자료 결측으로 평가하지 않았다.
- 기존 37개 수동 선별 2026년 발언 + 신규 **31개** 2022~2025년 발언 = **68개 발언**. 이를 플랫폼·스레드·게시일·1차/2차 의견별로 묶으면 **35개 관찰 단위**다. 모두 사후 발견한 비무작위 표본이다. 같은 사건에 서로 다른 의견이 있을 수 있고, 서로 독립적인 표본으로 취급하지 않는다.
- 실제 종가를 수작업으로 검증한 부분 시계열 **86개 NYSE 거래일**(2023년 2월/2025년 6·8·9월/2026년 7~10월). 빠진 날짜를 이전 종가로 채우거나 다른 해의 가격을 붙이지 않았다.
- **1차 투자 방향** (스레드/게시일 묶음) 부호 일치: 1거래일 **5/15**, 3거래일 **6/14**, 5거래일 **7/14**. 특정 스레드 안 상충 의견은 중립(0)으로 취급하거나 합의 부호로 묶었으며, 이는 모집단 여론율이 아니다.
- **2차 여론 (메타 의견)** (스레드/게시일 묶음) 부호 일치: 1거래일 **4/4**, 3거래일 **3/4**, 5거래일 **2/3**. 1일 변동폭이 예측 방향으로 1% 이상이어야 한다면 **2/4**. 전부 기존 2026년 선별 표본에서 나온 것이고, 특정 발언은 사후 예측자 평판 평가라 엄격한 선행 예측이 아니다.
- 2023-02-01 Reddit 연말 낙관론: 일자만 알려져 있어 다음 거래일 **2023-02-02 종가 $17.54**를 가상 기준으로 사용. 그 이후 5거래일 **2023-02-09 $16.22 (-7.53%)**. 이는 단기 수익률이면서 원글의 연말 $100 주장을 판정하는 것은 아니다.
- 2025-06-10 Reddit FOMO 질문 및 반대 조언: 다음 정규장 **6/11 종가 $21.64**, 그 뒤 5거래일 **6/18 종가 $21.61(-0.14%)**. 동일 스레드의 낙관·경계가 상충하므로 여론지수로 단순 집계하면 안 된다.
- 2025-08-05 관세 뉴스 리스크, 매도·대기와 회복 기대 공존: 가상 기준 8/06 종가 **$23.99**, 5거래일 이후 8/13 종가 **$29.27(+22.01%)**. 하락 경계만 골라 보면 틀린 사례를 제외하게 된다.
- 2024-08-05 공포성 글·물타기·반론: 일별 가격 부족으로 **주간 비교**만. 8/09 $30.65 → 8/16 $39.26 **+28.09%**, →8/23 $39.93 **+30.28%**. 이 수치로 8/05 게시물 다음 날 성패를 판정하지 말 것.
- 2024-09-05 저점 확인/회복 낙관과 우려: 9/06 주말 직전 종가 $25.66 → 9/13 $33.04 **+28.76%**, 주 단위 사례일 뿐 정확한 당시 진입수익 아님.
- 2025-04-04~05 바닥 vs 추가 추락 논쟁: 4/04 주간종가 $8.18 →4/11 $10.23 **+25.06%**. 4/17은 $9.20로 되돌림. 무조건 상승이 지속되는 근거 아님. 4월 말 논쟁도 같은 방식으로 별도 주간 근거 기록.

**편향과 한계:** 게시물 사후 선택, 게시시각은 대체로 날짜만 존재, 게시물 *최초 관측시각* 부재, 2024 가격은 주간 종가만, 2026 데이터는 재검증된 제한 시계열, 커뮤니티/이벤트 표본 크기 부족, SOXL 일간 3배 레버리지의 실제 기초지수 ICESEMIT 미확보, 수수료/스프레드/환전/갭 손실 미포함, 가격/뉴스 기준선 대비 추가정보량 미검증. **통계적 유의성·인과·실전 수익 우위 주장을 하지 않는다.**

## B. 전향적 검증의 실제 상태

- 2026-10-17 UTC 07:52의 관찰을 *즉시 동결*해 수정 불가능한 이름 및 SHA-256을 부여한 JSON 2건으로 저장함. 주가: ChartExchange 기준 2026-10-16 SOXL $93.69. Stocktwits 공개 웹페이지의 sentiment 83/100(24시간 rolling, 공개 표본 분모/정확한 관측 창 미확보). **관찰 시점이 가격 결정 시점과 달라 인과/괴리 매수 신호로 사용하지 않는다.**
- 현재 주가 미래수익 및 실제 커뮤니티 모집단이 없는 상태이므로 **NO_SIGNAL**. 10/19 첫 정규장 결과는 아직 미래 데이터. 이 장부에는 미래 결과를 오늘 기입할 수 없음.
- [사전등록 조건](prospective/pre_registered_protocol.json): 게시/최초 관측시각 모두 확보, 15분 이상의 선행 버퍼, 법적 수집 허용, 사전 표본틀, 1차 방향 vs 2차 역지표 분리, 가격·뉴스 기준선 대비 추가 개선, 최소 20개의 서로 다른 변동 사건군과 60개의 미사용 세션 이후 평가 (목표치이지 통계 검정력 보장 아님).
- [Python 검증 코드](prospective/shadow_protocol.py): 늦게 발견된 과거 글 금지, 권한·표본틀 미확인 자료 제외, 동일 원문 중복 방어, 동결 이전 미래 글·미래 가격 금지, 익명 작성자·본문 원문 공개 파일 보존 금지. 자동매매 코드 없음.
- 코드 회귀 테스트: **17개 전부 통과**. 이는 연구 인프라 검증이지 전략 성능이 아니다.

## 재현 방법

Python 3.11+ 및 `pandas`·`exchange_calendars` 필요 (tested Python 3.13).

```bash
python build_inputs.py
python historical/historical_replay.py
python -m unittest discover -s tests -v
```

실험은 완성된 가격 데이터만 세며 다음 거래일 **종가**를 가상 기준으로 삼는다. 실제 매수 가능 시가·호가를 사용한 백테스트와 혼동하지 말 것.

## 출처

- 2023 Feb: https://www.statmuse.com/money/ask/soxl-performance-february-2023
- 2024 weekly: https://www.statmuse.com/money/ask/soxl-price-2022-to-2024
- 2025 Apr weekly: https://www.financecharts.com/compare/SOXL%2CAVGO/summary/price
- 2025 Jun–Sep, 2026 Jul–Oct: https://chartexchange.com/symbol/nyse-soxl/historical/
- 게시물 원문은 `historical/expanded_historical_curated_claims.csv`의 개별 출처 링크로 접근. 텍스트 대량 저장 없음.
- SOXL 실제 기초지수는 NYSE Semiconductor Index: https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs
- 플랫폼 권한: https://stocktwits.com/about/legal/terms/ 와 https://redditinc.com/policies/data-api-terms

## 운영: 자동화와 제한

기존 SOXL 커뮤니티 시간별 점검과 주간 종합 보고를 유지/확장하고, 주기적 보고마다 누락 정보·충돌 정보·선행 검증 적격 표본 수·다음 거래일 결과를 구분한다. 검색엔진은 전체 글 모집단이 아니다. 법적 승인이 없는 자동 크롤링은 금지한다. 호스팅된 연속 수집 서버/API 접근권 부재로 본 도구는 **인증된 실시간 스트림이 아닌, 합법적 신규 관측이 들어올 때 오염 없이 보존·분석하는 검증 장부**다.

## 다음 성공 판정 게이트

1. 공식/허가된 2023~2026 전수 또는 무작위 추출 데이터(게시 시각·첫 관찰 시각·원 게시글/댓글 연결, 원문 저장권)와 ICESEMIT 일별 데이터 확보.
2. 2026-10-17 이후 충분한 관측과 가격이 실제로 도래한 다음, 모델 A(가격)·B(+뉴스)·C(+직접 심리)·D(+2차 심리)를 동일 미사용 세션에 평가.
3. 단지 같은 시점에 상관이 있거나 종가 기준 부호가 맞는 것으로는 검증 통과 불가. 수수료 차감 성과와 위험한 실패 사례를 요구.
4. 다른 결과가 나오면 부정 결과를 그대로 기록. **연구는 거래 권한을 주지 않음**.

## GitHub에서 바로 재실행 (2026-10-17 추가)

이 저장소 `main`에 검산에 필요한 **통합 CSV와 백테스트 엔진**을 연결했다. Python 환경에 `pandas` 및 `exchange-calendars`가 있을 때 아래 명령으로 68개 주장·35개 묶음 결과를 재생성한다. 가격 누락은 NULL로 보존하고 2022년 주장을 2023년 가격에 잘못 연결하는 버그를 수정했으며, 기존 2026 회귀 테스트 9개를 재통과했다.

```bash
python research/social-event-study/backtests/2026-10-17/backtest_retro.py \
  --prices research/social-event-study/backtests/2026-10-17/combined_verified_selected_daily_2023_2026.csv \
  --reddit research/social-event-study/2026-10-17/manual_samples_v0.csv \
  --claims research/social-event-study/backtests/2026-10-17/all_meta_claims_2022_2026.csv \
  --out local-social-study-output
```

- [merged historical source data](./all_meta_claims_2022_2026.csv)
- [combined partial official-market-day price data](./combined_verified_selected_daily_2023_2026.csv)
- [corrected, testable GitHub backtest script](./backtest_retro.py)
- [pre-registered prospective rules](./forward_preregistered_protocol.json)
- [first frozen prospective snapshot](./forward_first_snapshot.json)

주의: 'confirmed market-day price data'는 **공식 ICESEMIT 완전한 지수 파일을 확보했다는 의미가 아니라, 공개 가격 출처의 해당 SOXL 거래일 숫자를 검산하여 정리한 선별 부분자료**다. 표본 사후 선정/이용권 제약이 해소되었다는 의미도 아니다.
