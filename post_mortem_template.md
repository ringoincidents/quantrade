# QuanTrade 게이트 미통과 Post-Mortem 템플릿

> **사용 시점**: 2026년 10월 방향성 세션에서 §2.1 게이트(Phase 1 백테스트) 및/또는 Phase 2
> 캘리브레이션 판정이 나온 뒤, 미통과 시 이 템플릿을 채워서 원인분석을 진행한다. 통과 시에도
> §1(지표 비교표)만 채워서 기록을 남기는 걸 권장 — "그냥 운이 좋았다"와 "실제로 개선됐다"를
> 나중에 구분하려면 통과 시점 데이터도 필요하다.
>
> **작성 원칙**: 이 문서는 냉정하고 정량적인 분석용이다. 결론을 먼저 정해두고 숫자를 끼워맞추지
> 않는다(`backtest.py`의 `SUCCESS_CRITERIA` 자체가 "결과가 나온 뒤 기준을 짜맞추는 것을 막기
> 위해 미리 박아둔" 원칙 — 이 문서도 같은 정신으로 쓴다). 모든 결론에는 반드시 해당 항목의
> 실측 수치를 근거로 인용한다.

- **작성일**: ____
- **작성자/세션**: ____
- **대상 게이트**: [ ] Phase 1 §2.1 백테스트 게이트  [ ] Phase 2 캘리브레이션(고확신군 승률 비교)  [ ] 둘 다
- **참조 리포트 파일**: `backtest_report.json` (generated_at: ____) / `news_event_calibration_log.json` (레코드 수: ____) / `news_event_calibration_analysis.py` 실행 결과

---

## 1. 게이트 지표별 Target vs. Actual

Phase 1(`backtest_report.json`의 `gate`/`overall`)과 Phase 2(`news_event_calibration_analysis.py`
출력)의 지표를 한 표에 모은다. Target 열은 `backtest.py`의 `SUCCESS_CRITERIA`와
`news_event_calibration_analysis.py`의 상수(`HIGH_CONFIDENCE_THRESHOLD`,
`SIGNIFICANCE_ALPHA` 등)에서 그대로 가져온다 — 이 문서를 쓰면서 새로 기준을 만들지 않는다.

| 지표 | 출처 | Target | Actual (훈련) | Actual (검증) | Pass/Fail |
|---|---|---|---|---|---|
| 거래 건수 | `overall.train/validation.trade_count` | ≥30건 각각 | | | |
| 검증구간 샤프 유사 지표 | `overall.validation.sharpe_like` | ≥1.0 | — | | |
| 훈련/검증 방향 일치 | `gate.criteria` | 같은 부호 | | | |
| 승률 | `overall.*.win_rate_pct` | (참고용, 고정 기준 없음) | | | — |
| Buy&Hold 대비 | `strategy_vs_buy_hold` | "전략 우위" | | | |
| MDD | `overall.*.mdd_pct` | ≤-20% (참고용, 판정 제외) | | | 판정 제외 |
| ECE (Expected Calibration Error) | `news_event_calibration_analysis.py` → `ece_mce.ece` | <0.10 권장(표준 관행, 프로젝트 고정값 아님 — 첫 판정 시 근거와 함께 확정) | window별: d1= / d5= / d20= | | |
| MCE (Maximum Calibration Error) | 〃 → `ece_mce.mce` | (참고용) | window별: d1= / d5= / d20= | | — |
| 고확신군 vs 저확신군 승률 | 〃 → `high_confidence`/`low_confidence` | 고확신 > 저확신 | window별로 기입 | | |
| 유의성 검정 (Fisher's exact) | 〃 → `significance.p_value` | p < 0.05 | window별로 기입 | | |

> **주의**: ECE Target `<0.10`은 이 템플릿 작성 시점의 잠정값이며 프로젝트가 공식 채택한
> 고정 기준이 아니다(`SUCCESS_CRITERIA`의 `min_trades`/`sharpe_meaningful`처럼 사전에
> 못박힌 값이 아님). 첫 판정 세션에서 실제 채택 여부와 근거를 논의하고, 이후엔 다른
> 지표들과 동일하게 사후 변경 금지 원칙을 적용한다.

**종합 판정**: [ ] 게이트 통과  [ ] 게이트 미통과 (미통과 시 아래 §2로)

---

## 2. 실패 원인 4대 분해 축

각 축을 **독립적으로** 점검한다 — 하나의 원인으로 성급하게 결론짓지 않는다(여러 축이 동시에
해당될 수 있다).

### 2-1. 과적합 (Overfitting) 여부 검증

- [ ] 훈련구간 성과가 검증구간보다 뚜렷이 좋은가? (`overall.train` vs `overall.validation`
      비교 — sharpe_like/avg_return_pct 격차 정량 기입: ____)
- [ ] `gate.criteria`의 "훈련/검증 같은 방향(과최적화 징후 없음)" 항목 결과: [ ] 통과 [ ] 실패
- [ ] 파라미터 튜닝 이력 확인: 이 신호(`MA_SHORT`/`MA_LONG`/`ADX_TREND_THRESHOLD`/
      `RSI_ENTRY_OVERBOUGHT` 등)가 검증 결과를 보고 사후에 조정된 적이 있는가? (있다면 그
      자체가 과적합 위험 신호 — `--max-hold-multiplier`/`--rsi-exit`의 "1회 한정 실험" 원칙이
      지켜졌는지 함께 확인)
- **결론**: ____

### 2-2. 시장 국면 변화 (Regime Change) 영향 분석

- [ ] `by_regime_strategy`/`by_regime_buy_hold`(상승장/하락장/횡보장)를 비교해 특정 국면에서만
      성과가 나쁜지 확인 — 국면별 표 기입:

| 국면 | 전략 거래수 | 전략 평균수익 | B&H 거래수 | B&H 평균수익 |
|---|---|---|---|---|
| 상승장 | | | | |
| 하락장 | | | | |
| 횡보장 | | | | |

- [ ] 훈련구간과 검증구간의 국면 분포가 크게 다른가? (예: 훈련은 상승장 위주, 검증은 횡보장
      위주였다면 "전략이 나빠진 게 아니라 국면이 바뀐 것"일 수 있음 — 단, 이건 변명이 아니라
      "이 전략이 국면에 취약하다"는 것 자체가 실패 원인일 수 있다는 점도 같이 평가)
- **결론**: ____

### 2-3. 데이터 노이즈 / 알고리즘 오작동 여부

- [ ] 백테스트/실험 실행 로그(`daily.yml`/`backtest.yml`/`news_event_experiment.yml` GitHub
      Actions 로그)에 조용히 삼켜진 에러가 있었는가? (예: 이전에 발견된 `get_krx_candles` 날짜
      포맷 버그, `get_us_closes`의 Yahoo/stooq 폴백 실패 이력처럼 신호 자체가 아니라 데이터
      파이프라인 결함으로 결과가 왜곡됐을 가능성)
- [ ] `calc_adx()`의 근사치(Wilder 재귀평활 생략, 단순평균 버전)나 매도 규칙 근사(실제 AI
      판단이 아니라 하드손절/RSI과열/타임스탑 규칙 기반)가 결과에 유의미한 영향을 줬을
      가능성이 있는가?
- [ ] Phase 2 쪽: `get_news_headlines`의 재현율 한계(회사명 매핑 없이 종목코드만으로 검색)가
      표본을 편향시켰을 가능성이 있는가?
- **결론**: ____

### 2-4. Risk Engine 제어 실패 여부

- [ ] `AUTO_TIER_WEIGHT`(10%)/`POSITION_WEIGHT_HARD_CAP`(20%) 상한이 시뮬레이션에서 실제로
      지켜졌는가 — `portfolio.json`/`pending_actions.json` 이력에서 상한 초과 시도나 clamp
      경고 로그(`⚠️ ... 하드 상한을 초과해...`)가 있었는지 확인
- [ ] `MIN_CASH_RESERVE_RATIO`(0.3)가 실제로 지켜졌는가 — 리스크자산 노출이 70%를 넘은
      시점이 있었는지
- [ ] MDD 계산(날짜축 포트폴리오 시뮬레이션, `compute_portfolio_mdd()`)이 가정한 것과 실제
      동시보유 패턴이 크게 다른가? (예: 실제로는 설계보다 훨씬 많은 종목이 겹쳐 있었다면
      MDD_CAVEAT가 경고하는 근사 오차가 실제로 문제가 됐을 가능성)
- **결론**: ____

---

## 3. 종합 결론에 따른 Action Item 트리

아래 중 해당하는 가지 하나 이상을 선택하고, 선택 근거를 §2의 결론과 연결해서 기술한다.
**이 결정은 방향성 세션(claude.ai)에서만 확정한다** — Code 세션이 이 트리를 보고 자체
판단으로 실행하지 않는다.

```
게이트 미통과
├── §2-1(과적합) 또는 §2-3(데이터/알고리즘 결함)이 주원인
│   └── → 파라미터 재설정 제한 규정 적용
│       - 동일 신호(MA/ADX/RSI 기반)의 파라미터 재조정은 "1회 한정 실험" 원칙
│         (Experiment B 선례)을 벗어나지 않는 범위에서만
│       - 재조정 후에도 미통과면 이 신호 계열 자체를 폐기 검토(아래 가지로)
│       - 데이터/알고리즘 결함이 발견됐다면 그 버그부터 수정하고 전체 재실행 —
│         버그가 있는 상태로 나온 이전 결과는 무효로 표기
│
├── §2-2(국면 변화)가 주원인이고, 전략이 특정 국면에서만 유효했던 것으로 확인됨
│   └── → 국면 필터 추가를 "새 실험"으로 별도 설계(파라미터 재조정이 아니라 새 가설이므로
│       1회 한정 원칙 밖) 후 재검증, 또는 아래 "전략 폐기" 가지와 함께 검토
│
├── §2-4(Risk Engine 제어 실패)가 발견됨
│   └── → 이건 원인 분석과 별개로 즉시 조치 대상: Risk Engine 코드 버그 수정을
│       최우선으로 처리(다음 방향성 세션을 기다리지 않고 가능) — 단, 실계좌 관련
│       파일이면 여전히 방향성 세션 승인 필요(CLAUDE.md 세션 시작 체크리스트)
│
├── 가격 신호(MA/ADX/RSI) 계열 전체가 이 유니버스에서 근본적으로 우위가 없다고 판단됨
│   └── → 전략 폐기: entry_score/scan_crypto/scan_stocks에 반영하지 않고 백테스트
│       기록으로만 남긴다. 라이브 스캔 로직은 변경하지 않음(원래도 반영 안 돼 있었음)
│
└── Phase 2(뉴스 이벤트) 캘리브레이션이 유의미한 신호를 보임(고확신군 승률 유의미하게 높고,
    ECE 낮음)
    └── → Phase 2 전환 검토: get_news_headlines를 ask_claude_decision에 연결하는 걸
        다음 방향성 세션의 정식 안건으로 상정. **이 문서 하나로 연결을 승인하지 않는다**
        — 별도 세션에서 명시적으로 논의/승인 후 진행(PR#4 재발 방지 원칙, CLAUDE.md)
```

**최종 결정**: ____
**결정 근거 (§1/§2 인용)**: ____
**다음 조치 담당/시점**: ____
