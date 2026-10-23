# 기존 연구 감사 — MA60 Conditional Behavior v1.0
날짜: 2026-10-08 / 참조: [#122](https://github.com/ringoincidents/quantrade/issues/122)
상태: AUDIT_COMPLETE / NON_CANONICAL / RESEARCH_ONLY
감사 기준 커밋: f9050575be6ce4e1e5ecf3ea58bf394462cf21be. GitHub 연결로 읽기 검토했으며 로컬 checkout이나 코드 실행은 하지 않았다.

## 범위와 권한
Canonical Vision §2.4/2.10/3.2/3.6에 따른 시장 상태 연구의 확장이다. 수익전략 채택, Core 통합, 위험 제한 변경 및 주문 권한은 없다. Alpha Lab의 격리 태그와 기존 실패 기록을 유지한다. 새로운 문서만 추가한다. 독립 Runtime 부서 Agent를 실행하지 않았다. 아래 역할 검토는 단일 세션의 검토 항목이다.

## 코드 근거
| 감사 항목 | 확인 사실과 한계 |
|---|---|
| 시간·출처 | [load_candles](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/backtest.py#L130)가 Upbit/Yahoo 또는 Stooq/Naver를 재사용. [Upbit](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/analyze_lib.py#L649)는 days, [Yahoo](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/analyze_lib.py#L776)는 interval=1d, [KRX](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/analyze_lib.py#L851)는 timeframe=day. 기본 주식 1500봉, crypto 5000봉 요청은 실제 확보량과 다르며 상장 기간·조회 실패에 의존한다. 분봉/거래소/세션/호가 자료가 아니다. |
| 신호별 평가 | [raw_forward_return](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/indicator_significance_test.py#L332)는 종가부터 5봉 뒤 종가까지. [run_instrument_signals](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/indicator_significance_test.py#L369)에서 신호일 direction*raw-cost와 비신호일 raw-cost의 평균 차이를 종목당 하나로 집계한다. 기준군에는 같은 방향 변환이 없다. 하락 예측의 추가 정보와 실행 가능한 수익을 동일시할 수 없다. 시간대·변동성 매칭도 없다. |
| 개별·복합 | [compute_signals](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/indicator_significance_test.py#L185)에는 거래량+가격, BB터치+폭수축, RSI다이버전스, MA5/20/60 배열 등 이미 복합 후보가 있다. [simulate](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/backtest.py#L152)는 MA20/60 골든크로스+ADX 및 RSI/BB 필터다. 단독 지표만 검증했다는 해석은 부정확하다. MA60 근접과 기울기별 1분봉 조건의 증분 비교는 없다. |
| 분리·누수 | [significance 분리](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/indicator_significance_test.py#L380)와 [backtest 분리](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/backtest.py#L383)는 종목별 인덱스 70/30. 공통 달력 분할·종목 holdout·walk-forward는 없다. 라벨 종료시점으로 purge하지 않아 훈련 마지막 5봉의 미래 수익률 및 경계 넘는 훈련 진입 거래가 검증 가격을 사용 가능. backtest는 종가로 지표를 확정한 동일 종가에 비용을 더해 진입한다. 다음 봉 주문 모델이 아니다. |
| 통계·탐색 | [one_sample_p_value](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/indicator_significance_test.py#L343)는 종목별 차이의 양측 z근사(최소 10종목); 문서/JSON의 Welch 설명과 실제 구현이 다르다. [evaluate](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/indicator_significance_test.py#L428)는 7개 Bonferroni, 훈련 통과 후보만 검증 및 부호 일치. 종목별 집계는 겹친 5일 라벨의 봉별 독립 가정을 완화하지만 종목 간 시장 공통 충격은 남는다. 신뢰구간·효과의 불확실성·탐색 이력 전체 보정·날짜 cluster 추론은 없다. |
| 비용·실행 | [TRADING_COSTS](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/analyze_lib.py#L30)는 편도 crypto 수수료 0.05%/슬리피지 0.1%, KRX 0.015%/0.1% 및 매도세 0.18%, 미국 0.25%/0.1%. crypto 수수료는 코드에서 실측으로 표기하나 이번 감사에서 독립 확인하지 않았다. 나머지 슬리피지/해외 수수료는 가정. 현재 세율·상품·브로커 적합성은 미검증. 호가스프레드·부분체결·미체결·주문 참여율·공매도 가능성 없다. significance는 양쪽 같은 비용 차감으로 차이에서 비용이 상쇄된다. |
| 거래 성과 | [compute_metrics](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/backtest.py#L319)는 거래 승률·평균 및 비연율화 mean/std의 sharpe_like. [MDD](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/backtest.py#L274)는 거래 최종 수익을 날짜별 균등복리 근사하며 실제 경로·가용자본 제약을 복원하지 않는다. [buy&hold 비교](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/backtest.py#L464)는 보유기간이 다른 거래 평균 비교. [국면별](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/backtest.py#L475)은 훈련+검증 합산이라 독립 OOS 국면 검증이 아니다. |

## 실패 결과 보존 및 수치 불일치
- 현재 [indicator_significance_report.json](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/indicator_significance_report.json)은 2026-08-09, 실제 110종목, N=5, 후보 7개 모두 훈련 보정 p>=0.05. MA배열 p=0.08984, RSI다이버전스 p=0.05511. 검증 필드는 null이며 검증 성공/실패율을 만들어서는 안 된다.
- 관찰/코드의 118티커는 유니버스 설명이며 실제 110종목과 구별한다. 현재 backtest 상수는 KRX 38개를 포함하므로 역사적 설명과 현재 목록도 일치하지 않는다. 조회 실패/당시 목록·원천 snapshot 없이 차이 원인을 단정하지 않는다.
- 현재 [backtest_report.json](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/backtest_report.json)은 MA/ADX 재설계 결과: 검증 180거래, 평균 -0.59%, sharpe_like -0.055, gate_passed=false, train/validation 모두 buy&hold 우위.
- 관찰이 참조한 [과거 RSI/BB 결과](https://github.com/ringoincidents/quantrade/blob/b52f6a01c31c31e4f2cc23dfd2247581148ca28b/backtest_report.json)는 검증 46거래, 평균 -1.48%, sharpe_like -0.133. 현재 파일과 다른 실험이다. 어느 결과도 삭제·교체하지 않는다.
- 통계 우위 미확인은 모든 미래 조건부 관계의 부재를 증명하지 않는다. 그러나 새로운 가설의 입증 책임을 낮추지도 않는다.

## 새로 배운 차이와 중복
기존 국면 태그는 60일 수익률 ±10%이며 일봉 시점의 상태다. 장 시작 경과시간, 정규/시간외, MA60 접근 방향·기울기, 5/15/30분 MFE/MAE·미래 변동성, 조건별 증분 정보 및 현실적인 다음 봉 Long-only 실행을 학습하지 못했다. 이번 연구는 SIMILAR_VARIANT + 새로운 시간척도/세션 질문이며 NEW_VALIDATED_ALPHA가 아니다.

[FeatureProvider](https://github.com/ringoincidents/quantrade/blob/f9050575be6ce4e1e5ecf3ea58bf394462cf21be/quantrade/capabilities/features.py)는 closes만 받아 SMA5/20·수익률·전체 입력 변동성을 반환한다. OHLCV/시간/as-of/세션 계약은 없으며 호출자가 미래 closes를 전달하면 스스로 차단하지 못한다. 확장 시 이 경계를 재사용하고 시간·세션 검증 wrapper와 연구용 provider를 별도로 두는 것이 적절하다. 단순 평균 RSI인 analyze_lib.calc_rsi와 Wilder 평활 rolling_rsi도 다르므로 앱 표시와 계산법 일치를 가정할 수 없다.

## precedents/ 검토
6개 문서를 모두 읽었다: FEATURE_PROVIDER_PRECEDENT, CONDITIONAL_REVIEW_GATE_DECISION, REVIEW_GATE_SHADOW_MISSION, REVIEW_GATE_LIVE_BINDING_DECISION, REVIEW_GATE_EVALUATION_MISSION, REASON_TRANSLATION_OBSERVABILITY_DECISION (모두 2026-10-04).
FeatureProvider의 출처·비권한 경계를 재사용한다. ReviewGate는 조직 검토 routing이며 시장 알파 검증이 아니다. Shadow routing intent를 실제 AI 호출/절감으로 오인하지 않는 원칙은 연구 계획을 실제 실험으로 오인하지 않는 원칙과 같다. 알 수 없는 상태·데이터 공백을 명시하고 승격을 차단한다.

## 단일 세션 역할 검토
- Research: H1~H5를 가설로 유지하고 일봉 실패와 분봉 질문을 구분.
- Data / Engineering: 원천 없음, 세션/평활/보존 계약 미확인; Phase 1 통과 불가.
- Quant Validation: 동일 종가 진입, split 경계 라벨 중첩, 추론 문서 불일치 기록.
- Counter-Research: 사후 선택된 급등 종목·하락 사례, 동봉 거래량 동시성, 가격 파생 feature 중복, 종목 간 상관 및 생존 편향 검토.
- Risk & Compliance: 정적 비용 재사용 금지, KORU/통화 분리, 하락 정합수익을 공매도 수익으로 취급 금지.
- Performance & Learning: 모든 기존 실패 유지; 새 결과는 BLOCKED_DATA로 별도 누적.
