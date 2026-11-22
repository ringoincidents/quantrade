# 1분봉 데이터 확보 가능성 — Phase 1
날짜: 2026-10-08 / #122 / 상태: BLOCKED_DATA / 문서상 경로 확인, 실제 확보·품질 검증 미통과

## 확인 범위
기준 커밋 f9050575be6ce4e1e5ecf3ea58bf394462cf21be의 전체 Git tree(truncated=false)를 조사했다. CSV/Parquet/분봉 원천 파일은 확인되지 않았고 관찰 문서도 원본 OHLCV가 없다고 명시한다. 이 세션에서 사용 가능한 도구는 GitHub와 웹 문서 조회이며 인증된 시세 데이터 조회 도구·제공된 자격증명·로컬 shell은 없다. 숨겨진 credential을 검색하거나 계좌 조회를 하지 않았다. 실제 데이터 API 요청·다운로드·품질 검사는 실행하지 않았다. 접근 401/403을 실제 관측했다고 주장하지 않는다.

## 공식 출처 후보
| 후보 | 공식 문서에서 확인 | 미확인 / 다음 확보 요건 |
|---|---|---|
| 한국투자증권 KRX/NXT | [주식일별분봉조회](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_time_dailychartprice/inquire_time_dailychartprice.py): FHKST03010230, 날짜·시간 지정, 호출당 최대 120건, 보관 최대 1년, J/NX/UN 구분, 과거/허봉 옵션. 읽은 파일 blob SHA aafa68e6f9cb8b06453f98ad63f954b096e3d7bb. | 계정 신청 및 Appkey/secret을 private runner에 제공, 시세 endpoint만 허용. 알루코 NX 대상 여부·실제 earliest date·세션 OHLCV·허봉 의미·수정 방식·반복 조회 안정성 검증 필요. 요금/현재 rate limit/연구용 보관·재배포 권리는 미확인이며 공급자 확인 필요. UN 혼합으로 NXT 단독 결과를 만들지 않는다. |
| 키움 KRX/NXT | [공식 ka10080 sample](https://github.com/Kiwoom-Securities/Kiwoom-REST-API/blob/main/examples/국내주식/차트/get_domestic_stock_minute_chart.py): tic_scope=1, KRX bare/NXT _NX/SOR _AL, 수정주가 옵션·기준일·연속 조회. 읽은 blob SHA e7cbf89464138162330e5e770991d5e4680fb122. [공식 이용 안내](https://openapi2.kiwoom.com/intro?dummyVal=0): 계좌/HTS ID와 API 등록 필요, 국내 조회 초당 5회. | 보관 기간·페이지 상한·과거 NXT 및 애프터마켓 실제 범위·수정주가 산식·데이터 비용/저장 권리 미검증. sample의 MAX_PAGES=10과 0.2초 delay는 예제 설정이지 서버 보장 아님. |
| Alpaca 미국 정규/프리마켓 | [계획·인증](https://docs.alpaca.markets/us/docs/about-market-data-api): 과거 2016년부터, Basic 무료 200회/분 및 최신 15분 제한; Plus 월 $99, 10000회/분. 주식 데이터 인증 필요. [bars](https://docs.alpaca.markets/us/reference/stockbarsingle-1): 1Min, SIP/IEX 구분, raw/split/dividend 등, USD 기본, 페이지 token. | private API key/secret과 계정의 historical SIP entitlement 확인. 상품별 earliest date와 분봉 실제 완전성은 미검증. IEX 거래량을 전체 시장 거래량으로 사용 금지. UTC→America/New_York 및 DST/휴장/조기폐장 달력으로 세션 분리; 프리마켓 품질은 별도 검증. 영구 내부 보관·공개 재배포는 약관 확인 필요. |

한국투자 포털은 [2026-09-09 KRX 애프터마켓/NXT 제도 변경 공지](https://apiportal.koreainvestment.com/intro)를 표시한다. 그러므로 화면의 “애프터마켓”을 NXT로 단정하거나 예전 고정 시각을 적용하지 않는다. 해당 공지의 세부 거래시간과 실제 날짜별 거래소 캘린더를 확보해야 한다.

문서 조회 시점의 가격/호출 제한이며 계약 견적이나 실제 endpoint 성공 증거가 아니다. 데이터 저장·연구 이용 권한이 확인된 공급자 계약을 통과 전제로 한다. 기존 Yahoo/Naver 일봉 endpoint를 임의 분봉 스크래핑으로 확장하지 않는다. KORU는 레버리지 ETF 독립 cohort, 가격·비용 USD; 원화 앱 표시값과 혼합하지 않는다.

## MVP 확보 순서와 승인 사항
우선 KRX 정규장 또는 미국 SIP 정규장 하나를 선택한다. NXT 및 미국 프리마켓은 후속 cohort다. 구매/새 계정 개설/유료 구독은 실행하지 않았다. 필요한 것은 (1) 공급자·연구 이용/저장 조건 확인, (2) 필요한 경우 비용 승인, (3) 비공개 시세용 secret 설정과 연구 runner 네트워크 허용, (4) 반환 데이터 품질 증거다. 키를 공개 repo/PR/채팅에 기록하지 않는다. 계좌/잔고/주문 endpoint는 수집 범위에 없다. 대안은 같은 출처·라이선스·세션 metadata가 있는 적법한 OHLCV export다.

## Phase 1 통과에 필요한 증거
1. 요청/원응답을 허용된 private 원천 저장소에 append-only 저장: 공급자, endpoint, query(인증 제외), feed, adjustment, symbol/as-of, currency, 취득시각, 반환범위, revision, SHA256. 공개 저장소에는 metadata/집계 품질 보고서만 저장.
2. 서로 다른 거래일·종목·월에 걸친 pilot 수집. 이어 여러 종목 최소 120거래일을 목표로 고정 유니버스 수집; 이 수는 검정력 보장이 아니므로 효과 크기별 power 검토와 충분한 독립 날짜 cluster가 필요. 알루코 단일일은 통계 표본이 아님.
3. tz-aware bar start/end, 거래소, 날짜별 session ID, 완료 여부, 1분 간격 명세. timestamp 시작/종료 의미 및 공급자 지연 확인. 세션 간 label/feature 연결 금지; 워밍업 정책 명시.
4. 유일 key(symbol, venue, session, bar_start) 검사. 동일 중복은 provenance와 함께 dedup; 충돌 중복은 격리. 빠진 분을 무체결/정지/장외/공급자 누락으로 구분하고 OHLC forward-fill로 거래 봉을 만들지 않음.
5. 유한 양수 OHLC, low<=open/close<=high, 음수/비정상 volume, 틱단위, split·정지·가격제한 점검. 급등을 단순 outlier로 삭제하지 말고 corporate action·타 출처 확인 후 격리/결정 로그. raw 및 조정본 구분, volume 단위 확인.
6. 재조회 checksum/revision 차이와 표본 cross-source 대조. 2026-10-08 알루코 표시값은 미완료 봉/실시간 quote/주석을 구분해서 대조하며 캔들 종가와 일치를 강요하지 않음.
7. 결측·이상·탈락 종목/일·세션 수와 이유, 실제 earliest/latest, completeness, 호출 429/retry/pagination 검증, 저장 권리 기록. 검증 결과 확인 전에 manifest/분할/규칙 lock.

현재 1~7의 실제 데이터 증거는 모두 미확보. Phase 2~5 중단은 이번 임무의 “신뢰할 수 있는 데이터를 확보하지 못한다면 … 해당 단계에서 중단” 조건에 따른다. 코드/테스트/실험 결과를 가상으로 채우지 않는다.
