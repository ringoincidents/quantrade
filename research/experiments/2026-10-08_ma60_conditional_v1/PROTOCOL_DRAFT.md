# MA60 조건부 연구 — 후속 프로토콜 초안
2026-10-08 / #122 / 상태: DESIGN_DRAFT_NOT_PREREGISTERED / NOT_EXECUTED
Phase 1 통과 후 데이터 manifest·달력·비용·검정력을 검토하여 최종 사전 등록한다. 아래 값은 결과를 본 후 바꿀 수 있는 탐색 공간이 아니라 최종 등록의 제안이다. 지금 백테스트 구현/검증 완료를 의미하지 않는다.

## Experiment A
완료 봉 t의 close, abs(close/SMA60-1)<=0.002 최초 진입을 근접 이벤트로 정의 제안. 30분 cooldown을 공통 적용. SMA60 기울기는 SMA60(t)/SMA60(t-5)-1; 상승>0.0005, 하락<-0.0005, 나머지 평탄. Wilder RSI14(초기 14개 변동 평균, 양쪽 0이면 50), BB20 ±2 population std, 폭=(upper-lower)/SMA20, 폭 percentile은 t-120~t-1만 기준, volume_ratio=V(t)/mean(V(t-20:t-1)). 분모 0/결측은 미평가한다. 전일·이전 세션 이어붙이기 없이 워밍업을 확보한 동일 세션만 사용한다.

비교 6개: 근접만 / 근접+상승 기울기 / 근접+RSI<50 / 근접+volume_ratio>=2 / 사전 복합(근접 또는 하향교차 + RSI<50 + volume_ratio>=2 + 직전 봉 BB폭 percentile<=0.2) / 무조건 대조군. 하향교차=직전 close>=직전 SMA60, 현재 close<현재 SMA60; 복합군의 cross 포함 범위를 최종 등록 시 명시적으로 고정한다.

소수 주검정 제안은 H1 근접 대 대조 15분 signed return, H3 RSI 조건 대 근접 15분 signed return, H4 복합 대 근접/교차 기반군 15분 signed return의 세 가지, 양측 Holm family-wise alpha=.05. H1 미래 변동성 등 다른 outcome·5/30분은 보조 기술통계 또는 별도 사전 family 정의 후 보정하며 주검정 성공으로 대체하지 않는다. 기본군을 비교군과 일치시키고 불균형을 보고한다. 방향 우위를 주장하려면 OOS 효과 부호와 신뢰구간·경제성까지 확인한다. 필터 비발생군을 추가하여 subset/base 중복 영향을 드러낸다.

H2 5개 상태(상승선 위에서 접근/상승선 하향이탈/하락선 아래에서 접근/하락선 상향돌파/평탄 반복교차), H3 RSI slope·30/70·divergence, H4 다른 거래량/폭/직전 수익, H5 레짐·세션 비교는 탐색 보조 가설로 제한한다. 반복교차는 과거 20봉의 교차 수>=3 제안이며 미래 회복 여부로 과거 신호를 분류하지 않는다. 레짐의 최종 수식과 유니버스는 등록 전 고정해야 하며 현재 초안에서 미확정이다.

## 대조군·시간·라벨
동일 종목·시장·세션·장 시작 후 30분 시간 bucket으로 비이벤트 대조를 선택한다. 결과 값을 사용하지 않는 고정 hash/seed 규칙, 동일 워밍업·결측·거래가능 조건 적용. 무조건 기준군과 MA60 대신 임의 시간 이벤트 음성 대조도 함께 보고한다. 미래를 보고 유사한 종목/사건만 선택하지 않는다.

예측 라벨은 close(t) 이후 정확한 5/15/30분 가격변화와 MFE/MAE, log-return 실현 변동성 및 과거 동길이 대비 변화. clock 분 단위와 봉수 차이를 검사하고 누락/세션 종료를 넘어선 라벨은 제외한다. 상승·하락·0 확률과 표본 수를 모두 표시. 실행 성과는 신호 봉 마감 및 처리 지연 뒤 다음 봉 이후 실행 가능 시점부터 별도 계산한다. 다음 시가 체결은 낙관적 proxy로 표시하며 호가/지연이 없으면 실행성 입증 불가.

공통 달력으로 개발/검증/독립검증 60/20/20 분할 제안, 최대 30분 label horizon와 실행 지연을 purge/embargo, 날짜별 walk-forward 보조. 탐색은 개발 partition만 사용. 검증/독립검증은 사전 규칙 lock 후 단 한 번 평가하고 결과를 보고 수정한 버전은 새 실험 ID와 미래 데이터가 필요하다. 시장 공통 충격과 겹친 label에 대응해 전체 종목을 함께 묶은 거래일 block bootstrap(고정 seed, 10000회)으로 효과 CI와 다중검정 p를 계산하는 설계. 비중첩 이벤트 민감도·보류 종목 평가도 수행. 단순 봉별 iid t-test 금지.

최소 표본 제안은 각 비교군 100 비중첩 이벤트, 30개 독립 날짜 cluster. 부족 시 INCONCLUSIVE_SAMPLE_SIZE 및 inferential 수치 null; 최소 수만 넘었다고 검정력이 보장되지 않는다. 효과·분산별 power 검토로 최종 요구량을 등록 전 고정한다.

## 비용 및 경제성
수수료·거래세·실측 bid/ask spread·슬리피지·지연·미체결/부분체결·다음 실행 봉 거래량 대비 주문량을 명시한다. 가정과 실측을 분리하고 세율은 상품/날짜별 확인한다. OHLCV만으로 체결/호가를 복원하지 않는다. 비용 정보가 없으면 net performance=null/UNVERIFIED_EXECUTION. 하락 예측은 방향 연구이며 공매도 수익이 아니다. Long-only 실행 규칙·단일 포지션/중복 신호 처리·주문 참여율과 비용 sensitivity를 데이터 lock 이전 등록한 뒤 별도 평가한다. 현재 실행 규칙은 미확정이며 경제성 결과 없음.

## Experiment B와 독립 검증
개발 데이터에서 해석 가능한 제한 조건부 표부터 시작한다. 탐색 후보 최대 20개, 후보/threshold/검색횟수/탈락 모두 기록; 모델 복잡도를 늘리기 전에 단순 기준과 비교. 같은 데이터에서 발견·최종검증 금지. 패턴마다 조건·시장·발생수·효과·최악 손실·실패 상태·기존 중복·독립 검증 날짜/manifest를 기록하고 상태는 CANDIDATE. Phase 5의 미사용 데이터 평가를 통과해도 실거래 자동 승격 없음.

## 구현 시 필수 검증 목록 (현재 미작성·미실행)
SMA/RSI 정답 fixture, 미래 suffix 변경 시 과거 신호 불변, incomplete 봉 거부, 동일 입력/seed 재현, UTC/KST/New York DST 및 휴장/조기폐장·세션 분리, 결측/중복/충돌, 음수·NaN·비정상 OHLCV/정상 급등 구분, 비용·세금·미체결, 표본 부족, purge 경계 및 label session 경계, 합성 random walk의 반복 false-positive와 injected effect 검증. FeatureProvider metadata/non-authority를 유지하며 Core/runtime 변경 없이 별도 연구 adapter를 구현한다.
