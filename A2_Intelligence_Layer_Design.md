# QuanTrade A2 Intelligence Layer 설계 문서 (2026-08-29, 최종본)

> **최종본** — 1차 초안 확정(4건) + 2차 확정(부록 B 잔여 5건) 반영 완료.
> **코드 구현 없음 — 설계 문서만.** 코드 구현은 이 문서 PM 검토 후 별도 지시.
> **Step 1(공통 스키마)이 확정되기 전엔 Step 2~4 구현 착수 금지**라는 전제
> 그대로, 이 문서도 Step 1을 가장 상세히 다루고 Step 2~4는 Step 1이 확정됐다는
> 가정 위에서 설계했다 — Step 1이 PM 검토에서 바뀌면 Step 2~4도 다시 봐야 한다.
>
> 조사 근거: A0 Gap Analysis(`A1_Dashboard_Wireframe_Step1-2.md` §2-2/§2-3)와
> 이 세션에서 재확인한 5개 생성기(`market_indicators.py`/`news_event_cards.py`/
> `post_trade_review.py`/`portfolio_report.py`/`rule_trigger_report.py`)의
> 현재 소스. 판정성 서술 없이 사실과 설계안만 담는다 — "이렇게 하면 될 것
> 같다"는 제안이지 "이게 맞다"는 확정이 아니다.

## 개정 이력

**2026-08-29 2차 확정 반영(부록 B "여전히 열려 있는 항목" 5건 처리)**: PM이
아래 5건을 확정 지시, 이 버전(최종본)에 반영했다.

1. 변동성 급증 계산식을 `market_indicators.py`의 백분위 방식으로 통일 —
   `news_event_cards.py`의 `VOLATILITY_MULTIPLE` 배율 방식은 대체(§2-3).
2. 기존 `signal`/`rank`/`ranking` 파일단위 audit 예외는 소급 전환하지
   않음(현 상태 유지) — `audit_schema()`는 신규 코드부터 적용, "신규 예외는
   파일단위 제외가 아닌 경로단위 allowlist 사용"을 원칙으로 확정(§3-3).
3. 관심종목 고정값(§4-2의 `0.3`)은 이번 확정에서 값 자체를 정하지 않고
   명명된 상수로 분리 — 주석 "watchlist 데이터 축적 후 조정 대상"만
   부여(§4-2).
4. Novelty "최근 N일" 값을 `news_event_cards.json` 실제 이력(158건, 29개
   커밋)의 재등장 간격 분포를 근거로 결정 — N=7일 제안(§3-1a, 신규 절).
5. 환율 급변/뉴스 빈도 급증은 A2 범위에서 제외 — v4.0 로드맵 Phase B(B2/B4)
   항목으로 이관, 공통 스키마에 `event_type` 자리만 예약하고 계산식 설계는
   보류(§1-1, §2-3).

**2026-08-29 PM 확정 반영(1차 초안 → 2차 개정)**: PM이 아래 4건을 확정 지시,
그 버전에 반영했다.

1. Prioritization 공식을 4인자(Reliability × Novelty × Portfolio Relevance ×
   Magnitude)로 확정 — Importance 인자·event_type 고정가중치표 폐기(§3).
2. `audit_schema()` 경로 단위 allowlist 설계안 승인 — 변경 없이 그대로 유지(§3-3).
3. Portfolio Relevance는 "재가중" 해석으로 확정, `watchlist.json`이 비어
   유니버스가 보유 5종목뿐이라는 제약 명시(§4).
4. Step 1 스키마 통일에 `rule_trigger_report.py` 정규화 포함 — 스키마 버전
   `v1`→통일, 타임스탬프 KST naive→ISO 8601 UTC(§1-3/§1-4).

---

## Step 1. 공통 스키마 확정

### 1-1. 필드별 타입·허용값·필수여부

| 필드 | 타입 | 필수 | 허용값/형식 | 비고 |
|---|---|---|---|---|
| `timestamp` | string | **필수** | ISO 8601, UTC, 오프셋 포함(`2026-08-29T07:13:48+00:00`) | §1-4에서 상세 |
| `asset` | object | **필수** | `{symbol, name, market_country, currency}` | KRX는 `symbol` 6자리 숫자 문자열, 해외는 티커 문자열(기존 관례 그대로) |
| `source` | string | **필수** | `"<모듈>.<방법>"` 형태(예: `"news_event_cards.anomaly"`, `"news_event_cards.ai_summary"`, `"market_indicators.state_board"`) | 모듈 단위가 아니라 방법 단위까지 구분 — Step 3의 Reliability 산정에 필요(§3-1) |
| `event_type` | string | **필수** | 아래 §2-3 표의 고정 enum 중 하나 | 새 값 추가는 여기 한 곳에서만(각 생성기가 제멋대로 만들지 않음). `환율_급변`/`뉴스빈도_급증`은 enum에 자리만 예약 — 계산식 설계는 Phase B 대기(§2-3, PM 확정) |
| `observed_value` | number \| null | 조건부 필수 | Change Detection 계열 이벤트는 필수, 순수 뉴스 사건(수치 없음)은 `null` | 단위는 `event_type`별로 고정(§2-3) |
| `baseline` | number \| null | 조건부 필수 | `observed_value`와 동일 조건 | |
| `change` | number \| null | 조건부 필수 | `observed_value`/`baseline` 배율 또는 %p 차이 — 계산 결과를 그대로 저장(소비 측에서 재계산 안 해도 되게) | |
| `reliability` | number | **필수** | 0.0~1.0 | "이 관측이 사실이라고 얼마나 확신하는가"이지 "이 사건이 좋은/나쁜 소식일 확률"이 아님(§3-3에서 금지 입력과의 경계 명시) |
| `related_assets` | array | **필수(빈 배열 허용)** | `[{symbol, name, relation}]` — `relation`은 `"correlation_pair"`/`"portfolio_holding"`/`"watchlist"` 등 고정 enum | Step 4(Portfolio Relevance)가 채우는 필드(§4) |

**"asset"을 object로, "related_assets"를 배열로 분리한 이유**: 상관관계 이벤트(예: "포트폴리오 상관관계 변화")처럼 종목 쌍이 필요한 이벤트가 있어 주종목(`asset`)과 부수종목(`related_assets`)을 구조적으로 나눴다. 뉴스/이상행동처럼 종목이 하나뿐인 이벤트는 `related_assets: []`.

**타입에 없는 것 — 의도적으로 뺀 필드**: `severity`/`impact`/`sentiment` 같은 필드는 이 스키마에 없다. v4.0 §5의 9개 필드셋에 없고, 있으면 Step 3의 "금지 입력"과 충돌할 여지가 커서 넣지 않았다.

### 1-2. 5개 생성기 출력 → 공통 스키마 매핑표

| 생성기 | 현재 출력 단위 | `timestamp` | `asset` | `source` | `event_type` | `observed_value`/`baseline`/`change` | `reliability` | `related_assets` |
|---|---|---|---|---|---|---|---|---|
| `news_event_cards.py`(뉴스) | `cards[]`(`market`/`name`/`event_type`/`summary`/`headlines`) | 없음(카드별) → 최상위 `generated_at`만 | `market`+`name`에서 매핑 가능 | 신규(현재 없음) → `"news_event_cards.ai_summary"` | 있음(실적발표/공시/M&A/규제/지정학거시/기타) → 거의 그대로 재사용 가능 | 없음(뉴스는 수치 없음) → `null` | 없음(신규 부여 필요, §3-1) | 없음(신규) |
| `news_event_cards.py`(이상행동) | `cards[]`(`event_type:"이상행동"`, `summary`가 완성 문장) | 없음 → 최상위만 | `market`+`name` | 신규 → `"news_event_cards.anomaly"` | **단일값 "이상행동"** → 3종으로 분해 필요(§2-1) | **`summary` 문자열 안에 섞여 있음** → 분리 필요(§2-1) | 신규(산술이므로 1.0 고정 제안) | 없음(신규) |
| `market_indicators.py`(state_board) | `rows[]`(`symbol`/`name`/`volatility_20d_pct`/`volatility_percentile`/`adx_14`/`data_status`) | 없음 → 최상위만 | `symbol`+`name` | 신규 → `"market_indicators.state_board"` | 없음(이벤트가 아니라 스냅샷) → Change Detection으로 승격 시 부여(§2-2) | `volatility_20d_pct`가 observed에 해당, `baseline`은 과거분포(현재는 백분위만 저장, 원 baseline 값 저장 안 함) | 없음(신규, 산술이므로 1.0) | `correlation`에 종목 쌍 있음(현재 요약 통계뿐, 개별 쌍 목록 아님) |
| `portfolio_report.py`(rule_matches) | `rule_matches[]`(`rule`/`symbol`/`name`/`threshold`/`observed`/`fact`) | 없음 → 최상위만 | `symbol`+`name` | 신규 → `"portfolio_report.rule_matches"` | 규칙명이 사실상 event_type 역할(예: "집중도리밸런싱") → enum 정리 필요 | `observed`/`threshold`가 각각 observed_value/baseline에 대응(형식 통일 필요 — 현재 문자열) | 없음(신규, 산술이므로 1.0) | 없음(신규) |
| `post_trade_review.py` | 종합 리포트 1건(`exposure_change`/`allocation_gap`/`correlation_blind_spots`/`behavior_patterns`/`recent_news_links`) | `generated_at`(리포트 단위) | 없음(포트폴리오 전체 단위, 종목 단위 아님) | 신규 → `"post_trade_review.<섹션명>"` | 섹션별로 나눠야 함(현재 5섹션이 한 리포트에 뭉쳐 있음) | 섹션마다 다름(예: `correlation_blind_spots`는 이미 상관계수 값 보유) | 없음(신규) | `correlation_blind_spots`가 이미 종목 쌍 형태 |
| `rule_trigger_report.py` | 리포트 1건(`trigger`/`company`/`chart`/`market`) | **정규화 대상**(§1-3) — 현재 `"%Y-%m-%d %H:%M"` 오프셋 없는 KST naive 문자열 → 나머지 4개와 같은 ISO 8601 UTC로 통일 | `symbol`+`name` | 신규 → `"rule_trigger_report.<섹션명>"` | `trigger.rule`이 event_type 역할 | `trigger` 섹션에 수치 있음 | 없음(신규) | 없음(신규) |

**요약**: `event_type`은 이미 4/5 생성기가 어떤 형태로든 갖고 있어(뉴스 event_type, 규칙명, trigger.rule) enum 통합이 상대적으로 쉽다. `source`/`reliability`/`related_assets`는 **5개 생성기 전부 신규 추가**가 필요하다. `timestamp`는 항목별로는 전무하다(§1-4).

### 1-3. 기존 `schema` 문자열과의 관계

현재 5개 파일의 `schema` 값은 `post_trade_review_v3.2`/`portfolio_report_v3.2`/`market_indicators_v3.2`/`explanation_only_v3.2`/`rule_trigger_report_v1`로 **버전 번호부터 통일돼 있지 않다**(4개는 `v3.2`, `rule_trigger_report.py`만 `v1` — 이번 조사에서 확인). 이 필드는 "이 파일이 어떤 생성기가 만들었나"라는 **파일 단위 정체성**이고, 공통 스키마의 9개 필드는 **이벤트 단위 정체성**이라 서로 다른 층이다. 제안:

- 각 생성기 JSON의 최상위 `schema` 필드는 그대로 둔다(무엇이 이 파일을 만들었는지는 여전히 필요한 정보).
- 공통 스키마를 따르는 이벤트 배열(예: `change_events`)이 생기면, 그 배열 자체에 `schema_version: "intelligence_layer_v4.0"` 같은 별도 태그를 붙여 "이 배열 안의 각 객체는 공통 스키마를 따른다"는 걸 명시한다 — 파일 스키마와 이벤트 스키마를 같은 필드에 욱여넣지 않는다.

**`rule_trigger_report.py` 정규화 (PM 확정, §개정 이력 4)**: 이 파일만 `schema: "rule_trigger_report_v1"`로 다른 4개(`_v3.2`)와 버전이 다르고, `generated_at`도 `datetime.now(KST).strftime("%Y-%m-%d %H:%M")`(오프셋 없는 naive 문자열)이라 다른 4개(`datetime.now(timezone.utc).isoformat()`)와 형식이 다르다는 사실을 이번 세션에서 재확인했다(§1-2 표). 정규화안:

- `"schema": "rule_trigger_report_v1"` → `"rule_trigger_report_v3.2"`로 변경 — 나머지 4개와 동일한 버전 표기 체계로 통일.
- `generated_at`을 `datetime.now(KST).strftime(...)` → `datetime.now(timezone.utc).isoformat()`로 변경 — 다른 4개 생성기와 동일한 ISO 8601 UTC로 통일. KST 표시가 필요하면(사람이 읽는 화면 쪽) 저장 시점이 아니라 표시 시점에 변환하는 게 이미 이 저장소의 관례다(`index.html`의 `fmtBasis()`가 UTC를 받아 브라우저 로컬로 변환하는 방식 그대로).
- **하위 호환 확인(사실)**: `autoexec.py`를 grep한 결과 `rule_trigger_report.py`의 `generated_at`을 파싱(`strptime` 등)하는 코드가 없다 — 이 리포트는 텔레그램 `/autoexec_report <id>` 조회용으로만 쓰이고 시각 문자열을 재파싱하는 소비처가 없다. `index.html`의 `fmtBasis()`도 naive KST 문자열과 ISO 문자열을 이미 둘 다 처리하도록 만들어져 있어(오프셋 없는 `"YYYY-MM-DD HH:MM"` 패턴을 감지해 UTC로 파싱하는 분기가 이미 있음), 이 필드를 직접 fetch해 표시하는 화면이 생기더라도 형식 변경 자체가 기존 코드를 깨뜨리지 않는다. 다만 현재 `index.html`은 `rule_trigger_report.py`의 출력을 직접 fetch하지 않는다(텔레그램 전용 경로) — 이 사실은 참고용이며 정규화의 필요조건은 아니다.

### 1-4. 항목별 timestamp 부재 문제 — 해결안

현재 5개 생성기 전부 **최상위 `generated_at` 하나만** 있고 카드/행 단위 시각이 없다. 같은 파일 안에서도 항목마다 실제 관측 시점이 다를 수 있는 경우(예: 뉴스 카드는 헤드라인 발행 시각이 제각각)에도 지금은 구분이 안 된다.

**제안**: 공통 스키마의 `timestamp`는 **이벤트(관측) 시각**이고, 각 생성기 파일의 최상위 `generated_at`은 **그대로 둔 채 의미를 좁힌다** — "이 파일을 실행한 시각"으로. 즉 이번 설계는 최상위 필드를 없애는 게 아니라 그 아래에 항목별 `timestamp`를 추가하는 것이다:

```
{
  "generated_at": "...",          // 기존 그대로 — 파일 생성 시각
  "schema": "market_indicators_v3.2",   // 기존 그대로 — 파일 정체성
  "change_events": [
    {
      "timestamp": "...",         // 신규 — 이 이벤트의 관측 시각
      "asset": {...},
      ...
    }
  ]
}
```

값을 못 구하는 경우(예: 뉴스 헤드라인에 발행 시각이 없는 경우)는 `generated_at`으로 대체하되, 대체했다는 사실 자체를 `timestamp_is_fallback: true` 같은 플래그로 남기는 안도 검토할 것 — 이 문서에서 확정하지 않고 후보로만 남긴다(A5급 세부사항).

---

## Step 2. Change Detection 통합 설계

### 2-1. `detect_anomalies()` 구조화 승격안

현재(`news_event_cards.py`):
```python
facts.append(f"거래량 20일 평균 대비 {vol_mult:.1f}배")
```
`facts`는 완성된 한국어 문장 리스트다. 승격안:

```python
change_events.append({
    "event_type": "거래량_급증",
    "observed_value": today_vol,
    "baseline": avg_vol,
    "change": round(vol_mult, 2),          # observed/baseline 배율
    "unit": "KRW" 또는 "shares",            # 거래대금/거래량 중 실제 쓰는 단위
    "fact_text": f"거래량 20일 평균 대비 {vol_mult:.1f}배",   # 기존 문장은 표시용으로 보존
})
```

**핵심은 "문장 생성을 없애는 게 아니라 문장 뒤에 숫자를 남긴다"는 것** — `fact_text`는 대시보드가 지금처럼 그대로 표시하는 데 계속 쓰고, `observed_value`/`baseline`/`change`는 Step 3(Prioritization)·Step 4(Portfolio Relevance)가 계산에 쓴다. 기존 self-test(문자열 안에 판단 문구 없는지 확인하는 8개 케이스, `news_event_cards.py` 참고)는 `fact_text`에 대해 그대로 재사용 가능 — 구조가 바뀌어도 문장 자체의 문구 규율은 안 바뀐다.

### 2-2. `market_indicators.py` 상태판 → 같은 change-event 객체로

`state_board`는 원래 "지금 값 / 과거 분포 위치"를 스냅샷으로 보여주는 화면이지 이벤트 로그가 아니다(현재 `note`에도 "판정 아님"이라고 명시돼 있음). Change Detection으로 승격하려면 **스냅샷과 이벤트를 같은 파일 안에 공존**시켜야 한다 — 스냅샷을 이벤트로 바꾸는 게 아니라, 스냅샷에서 "임계값을 넘었다"는 사실만 뽑아 별도 이벤트로 추가 생성하는 방식을 제안:

```python
if volatility_percentile >= 90:   # 임계값, 사전 등록 필요(v4.0 §5)
    change_events.append({
        "event_type": "변동성_급증",
        "observed_value": volatility_20d_pct,
        "baseline": None,   # 백분위 자체가 이미 baseline 대비 위치라 baseline 값 자체는 없음 — 스키마상 null 허용(§1-1)
        "change": volatility_percentile,   # 배율이 아니라 백분위를 change로 재사용
        ...
    })
```

`state_board`(스냅샷 화면용)는 지금 그대로 유지 — MARKET 화면(index.html)이 이미 이걸 쓰고 있어 깨면 안 됨. `change_events`는 이 스냅샷 계산 도중 옆에서 같이 만들어지는 **부산물**로 설계한다(계산은 한 번만, 출력은 두 갈래).

### 2-3. 탐지 대상별 소스·계산 (v4.0 §5 6종)

| 탐지 대상 | 현재 상태 | `event_type` 값(제안) | 계산 소스 |
|---|---|---|---|
| 거래량 급증 | 있음(`news_event_cards.detect_anomalies`, `VOLUME_SPIKE_MULTIPLE=2.0`) | `거래량_급증` | 캔들 데이터(거래량) |
| 변동성 급증 | **통일 확정(PM, 2026-08-29)** — `market_indicators.py`의 백분위 방식을 표준으로 채택. `news_event_cards.py`의 `VOLATILITY_MULTIPLE=2.0`(당일 등락폭 배율 방식)은 **대체됨** | `변동성_급증` | `market_indicators.py`의 `volatility_percentile`(§2-2 승격안 그대로) — `news_event_cards.py` 쪽 계산식은 더 이상 표준이 아니므로 신규 코드에서 참조하지 않음 |
| 가격 갭 | 있음(`news_event_cards.detect_anomalies`, `PRICE_GAP_PCT=3.0`) | `가격_갭` | 캔들 데이터(시가/전일종가) |
| 환율 급변 | **A2 범위 제외(PM, 2026-08-29) — Phase B(B2) 대기.** 코드 어디에도 환율 변화를 이벤트로 잡는 로직 없다는 사실은 그대로. 공통 스키마 `event_type` enum에 `환율_급변` 자리만 예약하고, 계산식·데이터 축적 방식 설계는 이 문서에서 다루지 않는다 | `환율_급변`(예약만) | 미설계(Phase B) |
| 뉴스 빈도 급증 | **A2 범위 제외(PM, 2026-08-29) — Phase B(B4) 대기.** `get_news_headlines()`가 "평소보다 많다"는 비교를 하지 않는다는 사실은 그대로. 공통 스키마 `event_type` enum에 `뉴스빈도_급증` 자리만 예약하고, 계산식·데이터 축적 방식 설계는 이 문서에서 다루지 않는다 | `뉴스빈도_급증`(예약만) | 미설계(Phase B) |
| 포트폴리오 상관관계 변화 | **부분 있음** — `market_indicators.py`가 보유종목 간 평균 상관계수를 "현재 값"으로 계산(`compute_correlation_summary`)하나, 과거 대비 "변화"를 이벤트로 만들지 않음(시계열 저장 없음) | `상관관계_변화` | 기존 계산 로직 재사용 가능, 과거 값과 비교하려면 상관계수 자체를 시계열로 저장하는 부분만 신규 |

**사실 요약(2차 개정)**: A2 범위는 4종(거래량 급증/변동성 급증/가격 갭/상관관계 변화)으로 좁혀졌다 — 완전히 존재 2종(거래량 급증/가격 갭), 계산식 통일 확정 1종(변동성 급증), 부분 존재 1종(상관관계 변화 — 시계열 없음). 환율 급변/뉴스 빈도 급증 2종은 Phase B로 이관 — event_type enum 자리만 예약, 계산식·축적 방식은 이 문서의 설계 대상이 아니다.

---

## Step 3. Event Prioritization 설계 (가장 위험한 단계)

### 3-1. 공식과 인자별 허용 입력 매핑

**공식 확정(PM, 2026-08-29): `Reliability × Novelty × Portfolio Relevance × Magnitude`** — Importance 인자를 제거한 4인자 공식이다. 1차 초안의 5인자 공식(Importance 포함)과 그에 딸린 `event_type` 고정가중치표 제안은 **폐기**했다.

**폐기 사유(PM 지시 원문 그대로 기록)**: "event_type별 중요도 사전 부여는 관측 사실이 아닌 사전 신념이며, 근거를 추적하면 '예상 주가 영향도'(§5.1 금지 입력)로 귀결됨." 1차 초안은 §3-2에서 이 위험을 "가중치 정의 문구를 조심하면 피할 수 있다"는 완화책으로 다뤘으나, PM은 완화가 아니라 **인자 자체를 없애는** 결정을 내렸다 — 사건이 일어나기 전에 "이 사건 유형은 중요하다"고 사전 등록하는 행위 자체가, 아무리 문구를 "알림 우선순위"로 순화해도 결국 "이 유형의 사건이 (다른 유형보다) 주가에 더 큰 영향을 준다"는 사전 신념에서 나온 숫자라는 점은 못 피한다는 판단으로 이해했다.

| 인자 | 허용 입력(지시 원문) | 계산 제안 | 데이터 소스 |
|---|---|---|---|
| Reliability(출처 신뢰도) | 출처 신뢰도 | §1-1의 `reliability` 필드 그대로(소스별 사전 등록 고정값 — 산술 기반은 1.0, AI 기반은 사전 등록값) | `source` 필드 기준 조회 |
| Novelty(신규성) | 신규성 | 같은 종목·같은 event_type이 최근 N일 내 이미 발생했는지(있으면 감쇠, 없으면 1.0) — 통계적/시간적 정의, "이 정보가 시장에 새로운가"를 예측하지 않음. N=7 제안(조사 근거는 §3-1a) | 과거 이벤트 로그(신규 축적 필요) |
| Portfolio Relevance(보유비중·관련도) | 보유 비중·관련도 | Step 4가 채우는 `relevance_value` 그대로 | Step 4 출력 |
| Magnitude(변화 크기) | 평균 대비 배율 | `change` 필드 값 그대로(또는 `abs(change - 1.0)` 등 정규화) | Step 1/2에서 이미 계산된 `change` |

4개 인자 모두 지시 원문의 "허용 입력" 목록과 1:1로 대응한다 — Importance 제거로 "허용 입력 목록에 없는 인자"라는 불일치 자체가 사라졌다(1차 초안의 §3-1 미확정 항목 해소).

### 3-1a. Novelty "최근 N일" 조사 및 제안값(PM 지시, 2026-08-29)

**방법**: `news_event_cards.json`은 매일 덮어쓰기(append-only 아님)라 히스토리가 남지 않는다. 이 파일을 건드린 전체 git 커밋(`git log --all -- news_event_cards.json`, 29건, 2026-08-04~2026-08-28)마다 `git show <sha>:news_event_cards.json`로 그 시점 스냅샷을 복원해 카드를 전부 추출했다 — **158건**, 파싱 오류 0건, **고유 (market, event_type) 조합 29개**.

**전처리(중복 제거)**: 2026-08-28 하루에 Anthropic API 키 재발급 검증(CLAUDE.md 보안 절 참고, workflow_dispatch 런 #26/#28)으로 같은 날 카드가 여러 번 재생성된 커밋 군집이 있다 — 이건 "사건이 여러 번 재등장"이 아니라 같은 날 반복 실행의 산물이므로, `(market, event_type, 달력일)` 단위로 먼저 중복 제거했다. 결과: **144개 (조합, 날짜) 쌍**, 이 중 **재등장(2회 이상 등장) 조합은 21개**, 1회만 등장한 조합은 8개(간격 계산 불가, 표본에서 제외).

**간격(gap) 분포 — 재등장 21개 조합, 총 115개 gap 샘플(일 단위)**:

| gap(일) | 빈도 | 비율 |
|---|---|---|
| 1 | 107 | 93.0% |
| 2 | 3 | 2.6% |
| 3 | 1 | 0.9% |
| 4 | 1 | 0.9% |
| 7 | 1 | 0.9% |
| 9 | 1 | 0.9% |
| 10 | 1 | 0.9% |

min=1, median=1, mean=1.27, max=10.

**해석**: 재등장의 93%가 "바로 다음 날"이다. 재등장 조합 21개 중 다수(예: `SCHD`/`기타`, `004000`/`실적발표`)는 거의 매일 연속으로 카드가 나온다 — 이는 "새 사건이 자주 일어난다"기보다, **보유 5종목이라는 좁은 유니버스(§4-2, `watchlist.json` 빈 상태) 안에서 같은 종목·같은 event_type이 매일 재생성**되는 패턴에 가깝다(예: 롯데정밀화학의 "실적발표"가 18일 연속 등장 — 실제로 새 실적발표가 18번 있었다기보다 같은 사건에 대한 설명 카드가 매일 다시 만들어진 것으로 읽힌다). gap이 2일 이상으로 벌어지는 경우는 8건(7%)뿐이고, 그중에서도 7/9/10일처럼 뚜렷하게 벌어지는 경우는 3건뿐이다.

**제안 N=7**: Novelty를 `min(1, 마지막 등장 이후 경과일 / N)`처럼 정의한다면(§3-1 "있으면 감쇠, 없으면 1.0"), N을 분포의 지배적 패턴(gap=1, 93%)에 맞춰 작게 잡으면 "매일 재등장하는 사건"도 감쇠가 약해 Novelty가 별로 안 낮아진다. N=7(달력 주 단위)로 두면 gap=1일 때 Novelty≈0.14로 강하게 감쇠되어(어제도 있었던 사건은 "새롭지 않다"는 §3-1의 의도와 일치), 분포 꼬리의 자연스러운 경계(7/9/10일 — 8건 중 3건이 7일 이상)에서 Novelty가 1.0에 가까워진다. **이 값은 PM 지시대로 조사 분포를 근거로 이 문서가 제안하는 것이지, 확정으로 기록하지 않는다** — A5(구현) 단계에서 실제 감쇠 함수 형태(선형/계단식 등)를 정할 때 같이 재검토할 것.

**한계(표본 caveat)**:
- 관측 기간이 25일(2026-08-04~08-28)뿐이라 7일보다 긴 재등장 주기는 이 표본에 거의 안 잡힌다 — N=7 제안은 "관측된 최댓값(10일)보다 짧게, 지배적 패턴(1일)보다 길게"라는 상대적 근거이지, 장기 재등장 패턴까지 반영한 값은 아니다.
- 현재 "이상행동" event_type은 단일 버킷이다(위 표에서 `TE`/`이상행동`, `NMR`/`이상행동`, `196170`/`이상행동`이 이 버킷). 그런데 §2-1 설계는 이걸 거래량_급증/변동성_급증/가격_갭 3종으로 분해하는 걸 전제로 한다 — **분해 후에는 이 히스토리의 "이상행동" 재등장 패턴이 3종으로 쪼개져 각각의 표본 수가 더 작아지고, 위 분포가 그대로 적용되지 않는다.** 분해 이후 실제 재등장 주기는 A5에서 새로 쌓이는 데이터로 재검증이 필요하다.
- 재등장 조합 21개 중 절반 가까이가 유니버스가 좁아(보유 5종목) 생기는 "거의 매일 반복" 패턴이라, `watchlist.json`이 채워져 유니버스가 넓어지면 분포 자체가 달라질 수 있다.

### 3-2. 금지 입력이 섞이지 않는지 인자별 점검

| 인자 | 금지 입력과 헷갈릴 수 있는 지점 | 경계 설정 |
|---|---|---|
| Reliability | "이 뉴스가 좋은 소식일 확률"(금지: 상승/하락 확률)과 혼동 가능 | Reliability는 **"이 관측이 실제로 일어났다는 사실 자체에 대한 확신"**만 의미. 뉴스의 경우 "헤드라인이 실제로 이 종목에 관한 것인가/AI 요약이 원문을 왜곡하지 않았는가"의 신뢰도이지, "이 소식이 좋은지 나쁜지"가 아니다. |
| Novelty | "시장이 아직 반영 안 한 정보인가"(예상 주가 영향도의 다른 표현) 로 흐를 위험 | Novelty는 **"이 종목에 같은 event_type 이벤트가 최근 N일 내 몇 번 있었나"**라는 카운트 기반 통계로만 정의. "아직 안 알려진 정보"인지 여부는 판단하지 않는다. |
| Portfolio Relevance | 없음(§4에서 별도로 산술만 다룸) | |
| Magnitude | 없음(이미 §1/§2에서 산술로 확정) | |

Importance 항목은 인자 자체가 폐기되어 이 표에서도 제거했다(§3-1). 이 표는 "지금 이렇게 정의하면 안전하다"는 제안이지, 실제 계산식의 최종 문구는 A5(구현) 단계에서 다시 audit() 대상으로 검증해야 한다.

### 3-3. audit() 충돌과 필드 경로 단위 allowlist 설계 — PM 승인, 변경 없음

**PM이 이 설계안을 그대로 승인(2026-08-29)** — 아래 내용은 1차 초안에서 바뀐 것이 없다. Prioritization 공식이 5인자에서 4인자로 바뀌었어도(§3-1) 출력 필드 이름(`priority_score`)과 그 필드가 audit()과 충돌하는 지점은 동일하므로 이 설계는 그대로 유효하다.

**충돌 확인**: `FORBIDDEN_FIELDS_BASE`(`analyze_lib.py`)에 이미 `score`/`rank`/`ranking`/`rating`/`grade`가 있다(이번 세션에서 재확인, §1-1 인용). Prioritization 결과값의 가장 자연스러운 필드명은 `priority_score`인데, 현재 `audit()`는 **키 이름을 정확히 일치시켜서만** 검사한다(`k.lower() in FORBIDDEN_FIELDS` — 부분일치 아님, `priority_score`는 `score`와 정확히 같지 않아 지금 로직으로는 사실 안 걸린다). 그런데도 이 문서가 "금지어 삭제 금지 + allowlist" 방식을 설계하는 이유:

1. 지시 원문이 이 방식을 명시했고,
2. 현재 정확일치 로직에 의존해서 "우연히 안 걸린다"는 사실에 기대는 건 **다른 모듈이 나중에 필드를 `score`로 그대로 쓰면 걸린다**는 위험을 남긴다 — allowlist는 "우연히 피함"이 아니라 "이 정확한 위치는 검토 후 허용됨"을 코드에 남기는 장치다.

**설계**(analyze_lib.py에 신설 제안, 각 생성기가 개별 `audit()` 6벌을 유지하는 대신 여기로 합류):

```python
def normalize_path(path):
    """배열 인덱스를 지워 경로 패턴으로 만든다.
    'report.change_events[3].priority.priority_score'
    -> 'report.change_events[].priority.priority_score'"""
    return re.sub(r"\[\d+\]", "[]", path)

def audit_schema(obj, path="report", allowed_paths=frozenset()):
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            field_path = f"{path}.{k}"
            if k.lower() in FORBIDDEN_FIELDS_BASE and normalize_path(field_path) not in allowed_paths:
                bad.append(f"{field_path} (금지 필드)")
            bad += audit_schema(v, field_path, allowed_paths)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += audit_schema(v, f"{path}[{i}]", allowed_paths)
    elif isinstance(obj, str):
        for ph in FORBIDDEN_PHRASES_BASE:
            if ph in obj:
                bad.append(f"{path}: 금지 문구 '{ph}'")
    return bad
```

각 생성기는(예: Prioritization을 넣는 모듈) 자기 파일에서:
```python
ALLOWED_FIELD_PATHS = frozenset({
    "report.change_events[].priority.priority_score",
})
violations = audit_schema(report, allowed_paths=ALLOWED_FIELD_PATHS)
```

**이 방식이 기존 방식과 다른 점(사실 기록)**: 기존에 있던 파일 단위 예외(`indicator_significance_test.py`의 `signal` 제외, `portfolio_report.py`의 `rank`/`ranking` 제외 — 둘 다 이번 세션 이전 A0 조사에서 확인된 것)는 **그 파일이 감사하는 모든 객체에서 해당 단어를 통째로 면제**한다. 새 방식은 **정확히 등록된 경로 하나만** 면제하고, 같은 파일 안에서 다른 위치에 우연히 `score`가 다시 나타나면 여전히 걸린다 — 더 좁은 범위의 예외다.

**소급 전환 여부 확정(PM, 2026-08-29): 소급 전환 없음, 현 상태 유지.** 기존 두 파일단위 예외(`signal`/`rank`/`ranking`)는 그대로 둔다 — `audit_schema()`(경로 단위 allowlist)는 **신규로 작성되는 코드부터만** 적용하고, 기존 6개 파일의 `audit()`를 이 방식으로 바꾸는 작업은 하지 않는다. 이번 확정으로 남기는 원칙은 다음 한 문장뿐이다:

> **신규 예외는 파일단위 제외가 아닌 경로단위 allowlist 사용.**

즉 앞으로 새 필드가 금지어와 충돌하면(예: Prioritization의 `priority_score`) 그 필드가 속한 파일 전체에서 단어를 면제하는 방식이 아니라, 위 `audit_schema()`의 `allowed_paths`에 정확한 경로 하나만 등록하는 방식을 쓴다. 기존 두 예외를 이 원칙에 맞게 다시 쓸지는 이 문서의 범위 밖이며, 필요해지면 별도 지시로 처리한다.

**공용화 관련 사실**: 지금 `audit()`는 6개 파일에 복붙돼 있다(A0 조사에서 확인). 위 `audit_schema()`를 `analyze_lib.py`에 새로 만드는 안은 그 중복을 늘리지 않는 방향이지만, **기존 6개 파일의 `audit()`를 이걸로 교체하는 건 이 설계의 범위가 아니다** — 새로 스키마를 따르는 코드(Change Detection/Prioritization)만 이 함수를 쓰고, 기존 파일들은 각자 개편 시점에 옮겨가면 된다.

---

## Step 4. Portfolio Relevance 설계

### 4-1. 현재 부분 구현 재확인

- `post_trade_review.py`의 "최근 뉴스 연결"(§5) — 뉴스 카드를 보유 포지션에 연결. 이벤트 전체가 아니라 이미 만들어진 카드를 사후에 연결하는 방식.
- `market_indicators.py`의 `compute_correlation_summary` — 보유종목 간(관심종목 제외) 평균 상관계수 하나만 계산, 이벤트 단위 관련도가 아님.
- 둘 다 **"이미 만들어진 산출물을 나중에 포트폴리오와 이어붙이는" 사후 연결**이지, "Change Detection 출력 전체를 관련도로 필터링/재가중"하는 **독립 단계**가 아니다 — 지시 원문의 "현재 없음" 판단과 일치.

### 4-2. 정식 스테이지 설계

```python
# watchlist 데이터 축적 후 조정 대상 — 현재는 watchlist.json이 비어 있어
# 이 값이 실제로 쓰이는 사례가 없다(§4-2 하단 제약 사항 참고). 값 자체는
# 이번 확정에서 정하지 않고, 상수로만 분리해 A5 재검토 지점을 명시한다.
WATCHLIST_RELEVANCE_WEIGHT = 0.3

def compute_portfolio_relevance(change_event, real_portfolio, watchlist):
    symbol = change_event["asset"]["symbol"]
    held = next((p for p in real_portfolio.get("positions", []) if p["symbol"] == symbol), None)
    is_watched = symbol in watchlist.get("symbols", [])
    weight_pct = None
    if held:
        total = real_portfolio.get("cash", 0) + sum(
            p.get("eval_amount_krw", 0) for p in real_portfolio.get("positions", []))
        weight_pct = round(held.get("eval_amount_krw", 0) / total * 100, 2) if total > 0 else None
    return {
        "is_held": held is not None,
        "weight_pct": weight_pct,           # 보유 비중(%) — 미보유면 null
        "is_watched": is_watched,
        "relevance_value": (weight_pct or 0) / 100 if held else (WATCHLIST_RELEVANCE_WEIGHT if is_watched else 0.0),
    }
```

`relevance_value`(0.0~1.0)가 Step 3 공식의 Portfolio Relevance 인자로 그대로 들어간다. 보유 비중이 높을수록 값이 크고, 관심종목만이면 `WATCHLIST_RELEVANCE_WEIGHT`(명명된 상수로 분리 확정, PM 2026-08-29 — 값 자체 0.3은 미확정, "watchlist 데이터 축적 후 조정 대상"), 둘 다 아니면 0.

**"재가중" 해석으로 확정(PM, 2026-08-29).** 지시 원문의 "Change Detection 전체 출력을 보유·관심종목 관련도로 필터링/재가중"에서, `news_event_cards.py`/`market_indicators.py`의 `build_universe()`가 **이미 보유+관심종목으로만 스캔 대상을 좁혀놓은 상태**라(A0 조사에서 확인 — 시장 전체가 아니라 애초에 이 유니버스만 조회함) Change Detection 출력 자체가 이미 이 범위 밖의 이벤트를 만들지 않는다는 사실은 1차 초안 그대로다. PM이 이를 "필터링"이 아니라 **"재가중"**으로 확정 — Portfolio Relevance 단계는 이미 좁은 집합 안에서 보유 vs 관심종목의 비중 차이를 값으로 매기는 역할이지, 집합에서 이벤트를 들어내는 역할이 아니다.

**제약 사항(PM 지시로 명시): `watchlist.json`이 비어 있어 유니버스가 보유 5종목뿐이다.** A0 조사에서 확인한 대로 `watchlist.json`의 `symbols`는 현재 `[]`이고 `target_prices.json`의 `targets`도 `{}`다 — `build_universe()`가 만드는 실제 대상은 `real_portfolio.json`의 보유종목 5개(004000/NCPL/SCHD/TE 등, 인프라 조사 시점 기준)뿐이다. 이게 Portfolio Relevance 설계에 미치는 영향:

- `is_watched`(§4-2)는 현재 **항상 `False`**를 반환한다 — 코드는 맞게 동작해도 이 조건이 실질적으로 한 번도 참이 되지 않는다.
- 관심종목 전용 고정값(`WATCHLIST_RELEVANCE_WEIGHT`, 예시 `0.3`)이 실제로 쓰이는 사례가 지금은 하나도 없다 — 이 값이 적절한지 검증할 데이터가 없다는 뜻이라, A5에서 관심종목 사례가 생기기 전까지는 이 숫자를 튜닝할 근거 자체가 없다. 상수로 분리한 것(2026-08-29 확정)은 이 사실을 코드에 남기는 조치이지, 값 자체를 검증했다는 뜻은 아니다.
- 보유 5종목 간에는 relevance 값의 **분산이 거의 없다**(전부 `is_held=True`, `weight_pct`만 서로 다름) — Portfolio Relevance가 Step 3 공식에서 실제로 사건 우선순위를 갈라놓는 정도는 `watchlist.json`이 채워지기 전까지 제한적이다(보유 비중 차이만으로 갈릴 뿐, 보유 vs 관심의 큰 격차는 아직 관측되지 않음).
- 이 제약은 코드 설계를 바꾸지 않는다 — `watchlist.json`을 사람이 채우면 별도 코드 변경 없이 그 즉시 반영된다(§4-2 함수는 이미 두 파일을 다 읽음). 다만 A5 구현 직후 실제로 검증 가능한 것은 "보유 종목 간 비중 재가중"뿐이고 "보유 vs 관심 재가중"은 데이터가 채워질 때까지 미검증 상태로 남는다는 사실을 기록해 둔다.

### 4-3. Step 3와의 연결

`related_assets`(§1-1)와 Portfolio Relevance의 관계: 상관관계 이벤트처럼 종목이 여러 개 얽힌 경우, `asset`(주종목)의 relevance뿐 아니라 `related_assets` 각각의 relevance도 계산해야 하는지는 이 문서가 확정하지 않는다 — 최초 구현은 `asset` 기준 단일 relevance로 시작하고, 필요해지면 확장하는 안을 제안한다(과설계 방지, "필요한 만큼만" 원칙).

---

## 부록 A. 구현 순서 의존관계 (참고용, 이 문서가 확정하는 건 아님)

```
Step 1 (공통 스키마 확정, PM 승인)
  └─▶ Step 2 (Change Detection 구조화)
        ├─▶ Step 3 (Prioritization) — Step 2의 change/reliability 값 필요
        └─▶ Step 4 (Portfolio Relevance) — Step 2의 asset 필드 필요
              └─▶ Step 3이 Step 4의 relevance_value를 소비 (Step 3 ⟷ Step 4 상호 의존)
```
Step 3과 Step 4는 서로의 출력을 필요로 하므로(Step 3 공식이 Step 4 값을 인자로 쓰지만, Step 4 자체는 Step 3 없이도 독립 계산 가능) **구현 순서는 Step 4 → Step 3** 쪽이 자연스럽다(지시 원문의 Step 번호는 문서 서술 순서이지 구현 순서로 못박은 게 아니라고 이해했다 — 다르면 정정 필요).

## 부록 B. PM 확인 목록

**2026-08-29 2차 확정으로 해소/이관된 항목**:
- ~~Novelty의 "최근 N일" N값~~ → 실제 이력(158건) 분포 조사 후 N=7 제안(§3-1a). **"제안"이지 계산식(감쇠 함수 형태)까지 확정된 건 아님 — A5에서 함수 형태와 함께 재검토.**
- ~~변동성 급증의 두 계산식 중 어느 쪽을 표준으로 할지~~ → `market_indicators.py`의 백분위 방식으로 통일 확정, `news_event_cards.py` 쪽은 대체됨(§2-3).
- ~~기존 `signal`/`rank` 파일단위 audit 예외를 새 path 단위 allowlist로 소급 전환할지~~ → 소급 전환 없음, 현 상태 유지로 확정. 원칙 문서화: "신규 예외는 파일단위 제외가 아닌 경로단위 allowlist 사용"(§3-3).
- ~~Portfolio Relevance의 관심종목 고정값~~ → 값 자체는 미확정이나 명명된 상수(`WATCHLIST_RELEVANCE_WEIGHT`)로 분리 완료, "watchlist 데이터 축적 후 조정 대상" 주석 부여(§4-2). **값 검증은 여전히 미해결** — `watchlist.json`이 비어 있어 A5 진입 시점에도 이 숫자를 튜닝할 근거가 없다는 사실 자체는 변하지 않음.
- ~~환율 급변/뉴스 빈도 급증의 데이터 축적 방식~~ → A2 범위에서 제외, v4.0 로드맵 Phase B(B2/B4)로 이관. 공통 스키마 `event_type` enum에 자리만 예약, 계산식·축적 방식 설계는 Phase B 착수 시로 미룸(§1-1, §2-3). **"해소"가 아니라 "이 문서의 범위 밖으로 명시적으로 이동"임에 유의.**

**2026-08-29 1차 확정으로 해소된 항목(1차 초안 기준, 기록용으로 남김)**:
- ~~Importance 인자의 정확한 계산식~~ → 인자 자체 폐기로 해소(§3-1, §개정 이력 1).
- ~~`rule_trigger_report_v1`이 다른 4개와 달리 `v3.2`가 아닌 이유/정정 필요 여부~~ → 정규화안 확정으로 해소(§1-3, §개정 이력 4).
- ~~Step 4 "필터링"의 실제 의미 정정~~ → "재가중" 해석으로 확정(§4-2, §개정 이력 3).

**남은 항목 — 이 문서 범위를 벗어나 A5(구현) 또는 Phase B로 넘어가는 것들**:

1. Novelty 감쇠 함수의 정확한 형태(선형/계단식 등) — N=7은 제안됐으나 함수 형태는 A5 결정 사항(§3-1a).
2. "이상행동" event_type이 3종(거래량_급증/변동성_급증/가격_갭)으로 분해된 뒤의 재등장 주기 재검증 — 현재 N=7 근거 데이터는 분해 이전(단일 버킷) 히스토리 기준(§3-1a 한계).
3. Portfolio Relevance 관심종목 가중치(`WATCHLIST_RELEVANCE_WEIGHT`)의 실제 값 검증 — `watchlist.json`이 채워지기 전까지 불가능(§4-2).
4. 환율 급변/뉴스 빈도 급증의 계산식·데이터 축적 설계 — Phase B 착수 시 별도 문서 필요(§2-3).
