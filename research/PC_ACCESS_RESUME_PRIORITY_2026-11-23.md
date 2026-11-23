# QuanTrade 재개 최우선 확인 사항 — PC 접근 시 Market Data Vault부터

기록일: 2026-11-23 KST
분류: Founder 지정 재개 우선순위 · 기술 작업 보류 기록
상태: PC 전용 저장공간 구축 DEFERRED / NOT STARTED
규칙: 운영/매매 권한 없음. QUANTRADE_CANONICAL_VISION.md와 CLAUDE.md가 항상 우선한다.

## 지금 중단한 이유와 재개 트리거

사용자는 반복되는 과거 시세·경제지표 API 확보 문제를 해결하기 위해 시장 데이터 저장소와 재사용 지표 라이브러리를 먼저 만들기로 했다. 그러나 실제 PC에 접근할 때까지 저장소의 위치, 용량, 백업, 전원, 사용권한, 운영비를 결정하기 어렵다. **지금은 그 부분을 보류하고 미래 QuanTrade 재개 시 최상단에서 다시 알려달라**고 명시했다.

트리거: QuanTrade를 다시 열 때, PC 사용이 가능해질 때, 시장데이터/API 확보 문제로 연구가 정체될 때, 복합지수·시황 모델 개발을 다시 시작할 때.

### 미래 AI가 먼저 전할 메시지

> 잠깐! QuanTrade 연구마다 API·과거 차트 수집에서 막혀서 공용 Market Data Vault를 먼저 만들기로 했어. 2026-11-23에 데이터 저장·지표 계산 코드, 미국 재무부 3개 연도의 공식 원천 데이터 수집 및 임시 복원 시험이 성공했지만 **영구 비공개 저장공간 확보는 PC 접근 시까지 보류 중**이야. 중복 개발하지 말고 Issue #137·Draft PR #138부터 확인해서 실제 저장 위치·백업을 먼저 결정하자. 그런 뒤 QQQ/SPY·VIX·KRX 데이터를 확보하고 Issue #135 시장 복합지수 연구를 재개하자.

## 읽는 순서 (반드시 먼저)

1. [Canonical Vision](../QUANTRADE_CANONICAL_VISION.md) — 연구/포트폴리오/위험관리/실행 권한 분리.
2. [Data Vault Issue #137](https://github.com/ringoincidents/quantrade/issues/137) — 기반시설과 현재의 보류 상황.
3. [Data Vault Draft PR #138](https://github.com/ringoincidents/quantrade/pull/138) — 브랜치 research/market-data-vault-p0-20261123. **아직 main 병합 안 됨**.
4. [Data Vault README](https://github.com/ringoincidents/quantrade/blob/research/market-data-vault-p0-20261123/research/market_data_vault/README.md), [실제 국채금리 수집·복원 보고서](https://github.com/ringoincidents/quantrade/blob/research/market-data-vault-p0-20261123/research/market_data_vault/P1_TREASURY_PILOT_RESULT_2026-11-23.md), [시장 데이터 공급원 비교](https://github.com/ringoincidents/quantrade/blob/research/market-data-vault-p0-20261123/research/market_data_vault/P1_SOURCE_PROVIDER_MATRIX_2026-11-23.md).
5. [복합 시장지수 연구 Issue #135](https://github.com/ringoincidents/quantrade/issues/135), [Draft PR #136](https://github.com/ringoincidents/quantrade/pull/136)와 [원본 연구 문서](2026-11-22_MARKET_REGIME_COMPOSITE_SCENARIO_RESEARCH_V0.md).

## 실제로 완료된 작업

| 항목 | 실증 완료 범위 |
| --- | --- |
| 연구 기획 | 공통 Data Vault + 지표 계산 엔진의 설계, 보존 정책, 소스/이용권 후보, Issue #137/PR #138 |
| 저장 프로토타입 | 오프라인 SQLite에 OHLCV CSV 등록, 출처·SHA256·버전·중복·잘못된 값 검증, 관측일과 이용가능시각 분리, as-of 조회 |
| 계산 가능한 지표 | SMA / EMA / Wilder RSI / Wilder ATR 4개; 기존 QuanTrade 계산식과 차이 문서화 |
| 공식 데이터 연동 | 미국 재무부 2년물·10년물 공식 XML: 2008년 각 251일, 2020년 각 251일, 2025년 각 249일. **각 만기 751개 관측값, 두 만기 합계 1,502개** |
| 복구 시험 | CI 임시 비공개 경로에서 원본 XML 3개를 해시·메타데이터와 보존, SQLite 지우고 원본만으로 3개 배치 복원 성공 |
| 자동 테스트 | 2026-11-23 GitHub Actions에서 합성 테스트 29/29 성공 |
| 공급원 조사 | Treasury, FRED/ALFRED, Cboe, KRX OPEN API, Tiingo, 기타 미국 ETF 공급원 분석. 승인된 유료 구독/키 없음 |
| 복합지수 기초 연구 | VIX·신용스프레드·금리·달러 등 후보 33개 등록 및 G0/G1 첫 연구 스펙. 실측 예측력 검증은 여전히 미완료 |

## PC 접근 이후 할 일 (우선순위가 높은 순서)

### A. PC 접근 즉시: 현재 보류 중인 첫 기술 과제
- [ ] PC 운영체제, 여유 디스크, 켜져 있는 시간, 네트워크·원격 운영 가능성, 보유 저장장치 파악.
- [ ] 기존 로컬 QuanTrade/개인 데이터 백업을 먼저 확인. 기존 데이터 삭제·덮어쓰기 금지.
- [ ] 비공개·권한 통제되는 영구 원천 데이터 저장 장소 결정. 라이선스가 허용하는 데이터만 보관; 공개 GitHub에 원본을 올리지 않음.
- [ ] 장기 보관 비용, 백업 복사본, 정기 해시 검증, 다른 기기에서 복원 시험 결정.
- [ ] PR #138 기존 코드/테스트 재확인 및 PC에서 실행. 배포나 장기 수집은 백업 정책 승인 후만.
- [ ] **현재 시점에서 영구 스토리지/클라우드 유료 계정·자동 수집은 만들지 말 것.** 나중에 접근 가능할 때 판단.

### B. 영구 저장장소 확보 후
- [ ] 승인된 미국 QQQ·SPY 장기 일봉 공급원과 배당·분할 조정 이력 확보, 별도 원본/조정 기준 저장.
- [ ] 미국 재무부 2008/2020/2025 실데이터 재수집: 기존 원본은 임시 GitHub Actions 러너 종료와 함께 사라졌으며 지금 영구 저장소에 없음.
- [ ] Cboe VIX·FRED 시계열은 각 이용약관, 릴리스 시간, vintage를 검증한 뒤 수집.
- [ ] KRX OPEN API 인증/승인/데이터 이용 범위 확인; 키를 공개 저장소에 절대 넣지 않음.
- [ ] 누락일·시장 달력·중복·수정·해시·데이터 출처·원본 보관/복원 품질 시험 완료.
- [ ] 최소한 한 ETF+한 금리 시계열의 동일 입력/계산 버전으로 재현 가능한 연구용 스냅샷 확보.

### B-2. 2000~2025년 지표 데이터 G0 완성 기준 (Issue #135 직접 연결)
- [ ] **2000~2025년 목표 범위**의 QQQ·SPY 일별 가격(배당·분할 보정), VIX 등 변동성, 미국 2년/10년물 금리를 각 이용권·수집 가능 기간 범위에서 확보한다. 없는 연도를 채워 넣거나 원천 기간을 과장하지 말 것.
- [ ] 신용지표는 **장기 Moody's Baa–미국 10년물 스프레드(BAA10Y)**와 **ICE BofA 하이일드 OAS(BAMLH0A0HYM2)**를 서로 다른 시계열로 보관하고, 서로 대체하거나 무단 연결하지 말 것. 장기 하이일드 OAS는 라이선스/공개 이력 제약이 해결되기 전까지 BLOCKED.
- [ ] 관측일, 공식 발표 시각, 실제 최초 이용 가능 시각, 수정 이력(vintage)을 구분해 PIT(as-of) 적합 여부를 검증한다. 공개 시각이 입증되지 않은 자료는 'PIT 검증 완료'로 표시하지 말 것.
- [ ] 2000~2025년 전체를 확보하지 못해도 **범위와 누락, 사용할 수 있는 부분 표본, 독립 위기 사례 수**를 명시한 G0 결과표를 작성한다. 무리한 전체 구간 조합보다 정직한 범위 표시 우선.

### C. 데이터 검증 성공 후 연구 재개
- [ ] DuckDB/Parquet의 채택은 실제 데이터 크기와 분석 속도 비교 후 결정.
- [ ] 기존 quantrade/capabilities/features.py와 지표 계산식 정합성 및 구버전 모델 결과 유지 확인.
- [ ] Issue #135에서 VIX+신용스프레드의 실제 미래 수익률 선행성을 먼저 검증, Baa 대체지표와 하이일드 OAS 구별.
- [ ] **첫 실측 결과표(G1)**: VIX/신용스프레드 단독 및 결합 신호의 선행·지연 상관, 신호 건수(독립 에피소드 기준), 향후 5/20/60거래일 수익률, 최대 추가하락폭, 단순 기준모델 대비 개선 여부와 불확실성을 계산한다. **결과가 없거나 실패해도 기록**하고, 실제 표본 외(OOS) 검증을 명시한다.
- [ ] 근거가 생기면 복합지수 -> 10,000회 조건부 경로 시뮬레이션 -> 한 화면 그래프 순으로 진행. 효과가 없으면 예측 모델 승격 보류.

## 재개 시 반드시 지켜야 할 한계

- 공식 실데이터를 다운로드하고 **임시 보관·복원에 성공한 것**과 **영구 데이터 자산을 구축한 것**은 다르다.
- 연구 PR #136·#138은 main 미병합 Draft. 데이터 보존 구조와 코드의 성공 여부를 합쳐서 운영 완료라고 말하지 말 것.
- 과거 국채금리 관측일은 원래 최초 공개시각과 다르다. 공개시간이 확인되지 않으면 point-in-time 백테스트에 사용하지 말 것.
- VIX·하이일드 신용스프레드의 실제 데이터는 단순 주식 일봉에서 복원할 수 없다.
- 기존 운영 market_indicators.py의 종합점수 제한·이전 알파 실패·자동 주문 금지 유지.
- 자동 알림을 생성한 것이 아니라 **GitHub 저장소를 다시 읽을 때 발견할 수 있는 재개 메모**다.

*2026-11-23 사용자 요청: PC 접근 전까지 영구 저장공간 구축 과제 보류, QuanTrade 재개 시 우선 보고 목록에 재등장. 이 파일을 변경할 때 상태/근거를 덮어쓰지 말고 날짜를 붙여 갱신할 것.*
