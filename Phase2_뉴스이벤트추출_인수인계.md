# Phase 2: 뉴스 이벤트 추출 — 설계 메모 / 인수인계

2026-08-01 작성, 같은 날 구현 완료로 갱신. Phase 1 백테스트 §2.1 게이트 미통과 확정,
main merge 완료(`eafb570`) 이후 시작하는 별도 트랙.

**구현 상태(갱신)**: §5의 열린 질문 6개가 모두 결정되어 `news_event_experiment.py` +
`.github/workflows/news_event_experiment.yml`로 구현 완료. `analyze.py`/`ask_claude_decision`
연결 없음 — 분리 원칙 그대로 유지.

## 1. 현재 상태: get_news_headlines / _format_news

- 위치: `analyze_lib.py:391-446`
- 상태: Phase 1에서 "실험 단계 전용" 문구로 보존된 그대로, 변경 없음.
  `ask_claude_decision`/`analyze.py` 어디에도 호출부 없음 — `grep -rn "get_news_headlines\|_format_news"`로
  재확인, `analyze_lib.py`(정의부)와 `CLAUDE.md`(문서 언급) 2곳에만 존재.
- 라이브 뉴스 판단은 여전히 `get_news_sentiment`(감성 단어 카운트, `analyze_lib.py:372`)가 전담.
- **(구현 완료) 로케일 전환**: `get_news_headlines`의 Google News RSS 쿼리를
  `hl=en-US&gl=US&ceid=US:en` → `hl=ko&gl=KR&ceid=KR:ko`로 전환했다(analyze_lib.py).
  `get_news_sentiment`(라이브 경로)는 분리 원칙에 따라 그대로 두었다 — 로케일도 안 바꿈.
  query는 종목코드를 그대로 넘긴다(예: "005930") — 한국 금융 기사가 회사명 옆에 코드를
  병기하는 관례에 기대는 것이라 재현율에 한계가 있음(회사명 매핑은 다음 단계 개선 후보,
  Naver 실시간시세 API가 이름 필드를 주는지는 이 샌드박스에서 네트워크가 막혀 확인 못함 —
  analyze_lib.py의 get_news_headlines 함수 docstring에 그대로 기록해뒀다).

## 2. 이벤트 추출 설계안 (텍스트만)

### 2-1. 사건 유형 분류: 감성 점수 대신 유형 라벨

후보 유형: `실적발표` / `공시` / `M&A` / `규제` / `기타`(그 외 전부를 담는 캐치올, 분류 실패를
조용히 숨기지 않기 위해 명시적으로 남겨둠).

두 가지 분류 방식을 검토:

| | A) 키워드 규칙 | B) Claude 자체 분류 |
|---|---|---|
| 방식 | 정규식/키워드 매칭(예: "실적"/"매출"/"영업이익"→실적발표, "인수"/"합병"→M&A, "제재"/"과징금"/"금감원"→규제) | 헤드라인을 Claude에게 주고 판단(사건유형+투자판단+confidence)을 한 호출에서 같이 받음 |
| 비용 | 없음(추가 API 호출 없음) | 추가 API 호출 없음 — 어차피 판단 호출에 얹으면 됨(단, headline별이 아니라 market별 배치라면 종목당 1회) |
| 정확도 | 한국어 금융 용어 변주가 많아 브리틀함(예: "잠정실적", "컨센서스 하회" 같은 표현은 키워드 목록을 계속 늘려야 함) | 문맥 기반이라 변주에 강함, 다만 분류 근거를 같은 모델이 판단과 함께 내므로 순환 의존(같은 판단력을 같은 모델로 검증하는 셈) |
| 재현성 | 결정적(같은 입력 → 같은 출력) | 비결정적일 수 있음(temperature/모델 버전 변화) |

**(결정됨) B(Claude 자체 분류) 채택.** 근거: 이 프로젝트는 이미 매매 판단 자체를
Claude에게 맡기고 있어(`ask_claude_decision`), 별도 키워드 분류기를 추가로 유지보수하는 비용이
안 맞는다. 사람 스팟체크를 위해 `news_event_experiment.py`가 판단 로그마다 원본 헤드라인
원문(`headlines` 필드, 리스트 그대로)을 함께 저장한다 — 나중에 event_type/direction 분류가
말이 되는지 사람이 직접 원문을 보고 확인할 수 있게.

### 2-2. 헤드라인 원문을 프롬프트에 전달하는 방식 (구현됨)

Phase 1에서 되돌린 시도(같은 날 `get_news_sentiment`를 `get_news_headlines`로 실제 교체)의
프롬프트 아이디어 자체는 폐기하지 않았다 — **`news_event_experiment.py`의
`ask_news_event_judgment(market, headlines)`** 라는 별개 함수/별개 프롬프트로 구현,
`ask_claude_decision`(analyze_lib.py, 라이브 경로)과는 물리적으로 다른 파일에 둬서 절대
안 섞이게 했다. 실제 프롬프트 스키마:

```
{
  "event_type": "실적발표 또는 공시 또는 M&A 또는 규제 또는 기타",
  "direction": "호재 또는 악재 또는 중립",
  "confidence": 0에서100사이정수,
  "reasoning": "한 줄로 된 판단 근거"
}
```

가격 지표(RSI/이동평균 등)는 이 실험 프롬프트에 넣지 않는다 — Phase 1에서 되돌린 지시문의
취지("가격 지표가 아니라 뉴스 사건이 근거") 그대로, 이 실험은 "뉴스 단독으로 얼마나 예측력이
있는가"를 순수하게 보려는 것. 가격 지표와 결합했을 때 성능이 어떻게 바뀌는지는 이 실험이
어느 정도 성숙한 뒤의 다음 질문으로 남겨둔다.

### 2-3. Confidence 캘리브레이션 기록 방식 (구현됨)

핵심 문제: backtest.py도 이미 겪은 것과 같은 제약 — **과거 시점의 AI 판단은 재현할 수 없다**
(비용·비결정성). 그래서 이 실험은 backtest처럼 과거를 되돌려 계산하지 않고, **지금부터
전향적으로(prospectively) 판단을 기록하고, 시간이 지난 뒤 실제 결과와 짝짓는 방식**으로
구현했다 — `news_event_experiment.py`가 매일 실행될 때마다 두 단계를 순서대로 한다.

실제 구현한 스키마(`news_event_calibration_log.json`, D+1/D+5/D+20 세 시점 고정 — 결정사항
3):
```json
{
  "id": "005930_2026-08-01",
  "market": "005930", "judged_at": "2026-08-01",
  "headlines": ["...", "..."],
  "event_type": "실적발표", "direction": "호재", "confidence": 72,
  "reasoning": "...",
  "price_at_judgment": 71200,
  "outcomes": {
    "d1": {"date": null, "price": null, "return_pct": null},
    "d5": {"date": null, "price": null, "return_pct": null},
    "d20": {"date": null, "price": null, "return_pct": null}
  }
}
```

1. **판단 (judge_new_events)**: 오늘 아직 판단 안 한 종목 중 관련 헤드라인이 있는 것만 새
   레코드로 append. `outcomes`의 세 시점은 전부 `null`로 시작.
2. **결과 채우기 (fill_outcomes)**: 매 실행마다 모든 기존 레코드를 훑어서, `judged_at`으로부터
   경과일이 1/5/20일 이상인데 아직 해당 시점이 `null`인 것만 오늘 가격으로 채운다(이미 채워진
   시점은 건드리지 않음 — 오프라인 테스트로 멱등성 확인). "정확히 D+N일째"가 아니라 "D+N일
   이상 경과 후 첫 실행 시점"의 가격이라는 근사(하루 단위 그리드) — 매일 도는 스케줄이라
   오차는 최대 하루.

캘리브레이션 지표는 표본이 쌓인 뒤(§결정사항 5, 30건 알림 시점부터 검토 가능):
- confidence 구간별(예: 0-40/41-60/61-80/81-100) 실제 방향 적중률 — 이상적으로는 confidence
  구간이 높을수록 적중률도 높아야 함(과신/과소신 여부 판단)
- event_type별 평균 적중률/평균 수익률 — 어떤 사건 유형이 실제로 예측력이 있는지
- window(d1/d5/d20)별로 따로 봐야 함 — 단기(d1) 반응과 중장기(d20) 반응이 다를 수 있음

캘리브레이션 지표 (충분한 표본이 쌓인 뒤):
- confidence 구간별(예: 0-40/41-60/61-80/81-100) 실제 방향 적중률 — 이상적으로는 confidence
  구간이 높을수록 적중률도 높아야 함(과신/과소신 여부 판단)
- event_type별 평균 적중률/평균 수익률 — 어떤 사건 유형이 실제로 예측력이 있는지

## 3. 실행 범위 — 분리 유지 (구현됨)

- 별도 실험 스크립트 `news_event_experiment.py`로만 실행. `analyze.py`/`ask_claude_decision`
  변경 없음, 이번 트랙 전체에서 마찬가지 — grep으로 재확인 가능.
- 로그 파일도 별도 저장 `news_event_calibration_log.json` — 기존 5개 상태 파일
  (`portfolio.json`/`trade_history.json`/`pending_actions.json`/`last_report.json`/
  `telegram_offset.json`)과 분리해서 `daily.yml`/`poll.yml`의 커밋 레이스에 안 걸린다.
- 전용 워크플로 `.github/workflows/news_event_experiment.yml` (`cron: '30 9 * * *'`,
  `daily.yml`의 11:00 UTC보다 앞서 매일 1회) — `news_event_calibration_log.json`만 커밋.
- 유니버스는 KRX 중심 유지(Phase 1에서 이미 정리된 원칙), `backtest.py`의
  `KRX_MARKET_CAP_TOP`를 그대로 import해서 재사용 — "[Phase 2 승인 유니버스]" 리스트가
  두 군데(백테스트/이 실험)에서 갈라지지 않게.
- 안전장치(`HARD_STOP_LOSS`, `needs_approval()`의 승인 기준, `AUTO_TIER_WEIGHT`/
  `POSITION_WEIGHT_HARD_CAP`) — 이 실험은 매매를 전혀 실행하지 않으므로 애초에 안전장치 경로를
  타지 않음. 약화 대상 자체가 아님.
- 거래비용/슬리피지: 이 실험은 매매를 실행하지 않으니 직접 해당 없음. 다만 캘리브레이션이
  끝나고 실제 신호로 승격하는 단계가 오면(별도 논의) 그때는 `TRADING_COSTS`를 반드시 반영해야
  함 — "뉴스 반응만으로 수익률이 나오는 것 같아도 비용 반영하면 사라질 수 있다"는 점을 다음
  단계로 넘길 때 잊지 않도록 여기 남겨둠.

## 4. 구현 여부

**구현 완료 (2026-08-01, 같은 날 후속 지시로 진행).** 실험 스크립트 + 자동 스케줄까지
이번 세션에서 구현. `analyze.py`/`ask_claude_decision` 연결은 여전히 안 함 — 분리 원칙 유지.

## 5. 방향성 판단 지점 — 전부 결정됨

1. **뉴스 소스 언어 → 결정**: `get_news_headlines`를 `hl=ko&gl=KR&ceid=KR:ko`로 전환.
   `get_news_sentiment`(라이브)는 분리 원칙에 따라 그대로 둠.
2. **분류 방식 → 결정**: B(Claude 자체 분류) 채택 + 원본 헤드라인 원문을 판단 로그에 함께
   저장해서 사람이 나중에 스팟체크 가능하게 함.
3. **Confidence 스케일 → 결정**: 0-100 연속값 그대로 채택.
4. **결과 판정 시점(outcome window) → 결정**: 전략유형별/사건유형별로 나누지 않고 D+1/D+5/D+20
   세 고정 시점을 모든 레코드에 동일하게 적용 — 나중에 window별로 따로 비교 가능.
5. **실행 주기 → 결정**: GitHub Actions 매일 1회 자동 스케줄(`cron: '30 9 * * *'`,
   `news_event_experiment.yml`).
6. **표본 30건 도달 알림 → 결정**: 텔레그램으로 1회만 알림(`maybe_notify_sample_size`,
   로그에 `notified_30` 플래그로 중복 방지). 중간 점검 시점 신호일 뿐, 자동 판정/게이트에는
   미반영 — 명시적으로 확인.

**표본 확보 기간은 여전히 추정 불가** — 실측 데이터가 쌓여야 알 수 있음. 워크플로가 매일
자동으로 돌기 시작하므로, 이후 세션에서 `news_event_calibration_log.json`의 레코드 수를
확인하는 것으로 진행 상황을 알 수 있다.
