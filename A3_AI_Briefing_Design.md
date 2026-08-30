# QuanTrade A3 AI Briefing 설계 문서 (2026-08-30)

> **코드 구현 없음 — 설계 문서만.** 코드 구현은 이 문서 PM 검토 후 별도 지시.
> **Step 1(입력)+Step 2(출력 스키마)가 확정되기 전엔 Step 3~4 착수 금지**
> (PM 지시 원문) — 이 문서는 Step 1+2만 담고, 완료 시 중간보고한다.
>
> 조사 근거: 이 세션에서 재확인한 기존 코드(`rule_trigger_report.py`/
> `market_indicators.py`/`news_event_cards.py`/`portfolio_report.py`/
> `post_trade_review.py`의 `audit()`, `analyze_lib.py`의 A2 Step 1~4 산출물),
> 실제 워크플로 cron 설정(`.github/workflows/*.yml`), 저장소 루트의 실제
> JSON 파일(`real_portfolio.json`/`portfolio_report.json`/
> `news_event_cards.json`). 판정성 서술 없이 사실과 설계안만 담는다.
>
> **접근 불가 자료**: PM 지시가 인용한 "v4.0 §6 AI 출력 4단계 경계"와
> "§7.1 금지어"/"§19.5 월 상한"은 이 저장소 밖의 로드맵 문서(CLAUDE.md가
> 명시한 대로 "별도 계획 문서")에 있다 — 이 세션은 그 문서에 접근하지
> 못한다. §6/§7.1은 PM 지시 원문에 정의가 그대로 포함돼 있어 그대로
> 따랐고, §7.1 금지어는 이 저장소에 실제로 존재하는
> `analyze_lib.FORBIDDEN_FIELDS_BASE`와 내용이 일치해 그것을 근거로 삼았다.
> **§19.5 월 상한(비용 한도) 숫자는 어디서도 찾지 못했다 — Step 3에서
> 실제로 필요해지므로, 그때 PM에게 값을 요청한다(임의로 가정하지 않음).**

---

## 0. 전제 — AI 출력 4단계 경계 (PM 지시 원문)

| 레벨 | 이름 | 정의 | 허용 여부 |
|---|---|---|---|
| L1 | Observation | 관찰된 사실 그대로 | 허용 |
| L2 | Interpretation | 관찰 연결·현재 상태 설명 | 허용 |
| L3 | Hypothesis | 가능한 설명, **단 과거/현재 설명일 때만**, "가설임을 명시" 필수 | 허용(조건부) |
| L4 | Recommendation | 처방("매수하라", "지금이 기회", 목표가 등) | **절대 금지** |

**"따라서 앞으로 이렇게 될 것"은 L3가 아니라 L4로 취급**(PM 지시 원문) —
시제가 경계선이다: 과거/현재에 대한 가설(예: "이 상승은 어제 발표 때문일
가능성이 있습니다")은 L3, 미래에 대한 가설(예: "앞으로 더 오를 가능성이
있습니다")은 문구가 같아도 L4로 취급한다. 이 시제 구분이 뒤에서(§2-4)
"순수 문자열 매칭 audit()의 한계"로 다시 나온다 — 같은 문자열("가능성이
있습니다")이 시제에 따라 L3와 L4를 오간다.

---

## Step 1. 입력 설계

### 1-1. 3개 입력 소스의 실제 신선도 (사실 확인)

PM이 지정한 3개 입력의 생성 워크플로를 실제로 확인했다(`.github/workflows/*.yml`):

| 입력 | 파일 | 워크플로 | 주기 | 확인한 사실 |
|---|---|---|---|---|
| change_events(A2 산출물) | `news_event_cards.json` | `news_event_cards.yml` | **1일 1회**(09:50 UTC) | `change_events[]`에 A2 Step 1~4가 만든 9필드 + `.priority.priority_score` |
| portfolio_report 규칙 위반 | `portfolio_report.json` | `portfolio_report.yml` | **주 1회**(일요일 23:10 UTC) | `rule_matches[]` — 지금 실제 파일은 빈 배열(위반 0건) |
| real_portfolio 요약 | `real_portfolio.json` | `sync_real.yml` | **1일 4회**(00:25/03:25/07:25/11:25 UTC) | `cash`/`positions[]`, 계좌번호 등 식별자 없음(기존 원칙 재확인) |

**핵심 사실 — portfolio_report.json은 최대 6일까지 묵을 수 있다.** AI
Briefing이 이걸 "오늘의 위반 상태"처럼 현재형으로 서술하면, 실제로는 최대
6일 전 스냅샷을 오늘 일로 말하는 셈이 된다. 이건 단순한 UX 디테일이 아니라
**L1(관찰된 사실 그대로) 위반의 소지**다 — "지금 SCHD 비중이 32%다"는
관측이 언제 것인지 안 밝히면 사실 서술이 아니게 된다. 그래서 입력 구조
설계(1-2)는 각 소스의 `generated_at`을 원자료 그대로 포함시키고, 프롬프트
설계(Step 4)는 이 시각을 반드시 언급하도록 강제해야 한다 — 이 요구사항은
지금 이 문서에 기록해두고 Step 4에서 실제로 반영한다.

**포함하지 않은 인접 입력**: `post_trade_review.py`(`post_trade_review_log.json`,
1일 1회 07:35 UTC)도 index.html에 `renderReviewCard`/`loadPostTradeReview`라는
미연결 훅이 이미 있고(A1에서 "A2에서 TODAY 카드를 실데이터로 바꿀 때 연결"로
표시해둔 자리) 내용상 AI Briefing과 인접하지만, **PM 지시가 3개 입력만
명시**했으므로 이번 설계에 넣지 않는다 — 범위를 임의로 넓히지 않는다.

### 1-2. 입력 JSON 구조 (제안)

```json
{
  "change_events": {
    "generated_at": "2026-08-30T09:50:00+00:00",
    "items": [
      {
        "symbol": "005930", "name": "삼성전자", "market_country": "KR",
        "event_type": "거래량_급증",
        "observed_value": 5000000, "baseline": 1000000, "change": 5.0,
        "timestamp": "2026-08-30T00:00:00+00:00"
      }
    ]
  },
  "portfolio_rules": {
    "generated_at": "2026-08-24T23:10:00+00:00",
    "stale_days": 6,
    "matches": [
      {"rule": "집중도", "symbol": "SCHD", "name": "SCHD ETF",
       "threshold": "단일 종목 비중 30% 이상", "observed": "32.10%",
       "fact": "SCHD ETF 비중이 총자산의 32.10%로 기준 30% 이상"}
    ]
  },
  "real_portfolio": {
    "synced_at": "2026-08-30T11:25:00+00:00",
    "cash_krw": 1040.70,
    "total_assets_krw": 5230000.0,
    "positions": [
      {"symbol": "SCHD", "name": "SCHD ETF", "weight_pct": 32.10, "return_pct": 4.2}
    ]
  }
}
```

`change_events.items`의 순서는 **A2 Step 3(Prioritization)이 이미 계산한
순서를 그대로 보존**한다 — AI가 다시 정렬하거나 우선순위를 재판단하지
않는다(이유는 1-3에서 상세). `portfolio_rules.stale_days`는
`(오늘 - portfolio_rules.generated_at)`을 시스템이 미리 계산해 넣는다 —
AI에게 날짜 뺄셈을 시키지 않고(실수 위험), "6일 지난 정보"라는 사실을
프롬프트가 놓치지 않게 강제로 넣는다.

### 1-3. 필드별 포함/제외 판단

**PM이 명시적으로 판단을 요청한 지점**: raw `priority_score`를 그대로
넘길지, "높음/보통" 같은 사전 계산된 상태값으로 바꿔 넘길지.

세 가지 안을 검토했다:

| 안 | 방식 | 문제 |
|---|---|---|
| A | `priority_score` 숫자를 그대로 넘기되, "이 숫자를 브리핑 텍스트에 직접 인용하지 마라"고 프롬프트로만 통제 | 프롬프트 지시에만 의존 — 모델이 "숫자가 크다=더 위험하다=더 강하게 얘기해야 한다"는 식으로 강도를 조절하다 L4로 미끄러질 여지가 남음 |
| B | "높음/보통/낮음" 3단계로 이산화해서 넘김 | **연속값을 라벨로 바꾸는 행위 자체가 v3.2가 이미 금지한 "국면/등급/신호등" 패턴과 구조적으로 동일**하다 — PM이 경고한 대로 필드 이름만 `grade`/`rating`을 피하면 `FORBIDDEN_FIELDS_BASE`(문자열 정확일치)는 통과하지만, "이산 등급을 만든다"는 개념 자체가 v3.2 정신 위반. 감사기는 필드 이름만 보고 개념을 못 봄(§2-3에서 같은 종류의 한계를 다시 다룸) |
| **C(제안)** | `priority_score`와 그 하위 인자(reliability/novelty/portfolio_relevance/magnitude)를 **아예 프롬프트에 넣지 않는다.** 대신 `change_events.items`의 배열 순서 자체가 "이미 시스템이 고른 상위 N건, 이 순서대로"라는 사실을 암묵적으로 전달 | 숫자를 안 주면 모델이 그 숫자를 근거로 강도를 조절할 재료 자체가 없다 — "얼마나 위험한지"를 AI가 판단할 필요 자체를 없앤다 |

**이 문서의 제안은 C다.** 근거: 이 저장소는 이미 "산술이 먼저 거르고
AI는 걸러진 것만 본다"는 패턴을 쓰고 있다(`entry_score`가 후보를 추리고
Claude는 추려진 후보만 받는 것과 같은 구조, `ask_claude_decision` 참고).
Prioritization(A2 Step 3)이 이미 "이 N건이 중요하다"는 판단을 산술로
끝냈으므로, AI Briefing에 그 산술 결과의 **숫자**까지 다시 넘길 필요가
없다 — 순서만 보존하면 충분하다. **PM 확인 필요**(부록 B) — A안이나
B안을 선호한다면 이 절을 다시 써야 한다.

**넘기는 필드 / 안 넘기는 필드 최종안**:

| 소스 | 넘김 | 안 넘김 | 이유 |
|---|---|---|---|
| change_events | `symbol`/`name`/`market_country`/`event_type`/`observed_value`/`baseline`/`change`/`timestamp` | `priority_score`/`priority.factors.*`/`reliability`/`related_assets`/`source` | 위 C안. `source`(예: `"news_event_cards.anomaly"`)는 내부 식별자라 사람이 읽는 브리핑과 무관 |
| portfolio_rules | `rule`/`symbol`/`name`/`threshold`/`observed`/`fact`(이미 portfolio_report.py 자체 audit() 통과분) | (전체 필드가 이미 소량) | `fact` 문장 자체가 이미 v3.2 규율을 통과한 사실 서술이라 재사용 |
| real_portfolio | `cash_krw`/`total_assets_krw`/`positions[].{symbol,name,weight_pct,return_pct}` | `avg_price`/`quantity`/`current_price`/`eval_amount`(원화 아닌 통화 단위) | 매입단가·수량까지 넘기면 "그래서 얼마에 사고팔라"는 판단 재료를 프롬프트가 스스로 만들어주는 셈 — 최소 노출 원칙. 계좌번호류는 애초에 `real_portfolio.json` 자체에 없음(기존 원칙 재확인, CLAUDE.md) |

---

## Step 2. 출력 스키마 설계

### 2-1. 필드 정의 (제안)

```json
{
  "generated_at": "2026-08-30T10:00:00+00:00",
  "schema": "ai_briefing_v1",
  "summary": "오늘 삼성전자에서 거래량 급증이 관측됐고, SCHD 비중은 집중도 기준을 넘은 상태가 이어지고 있습니다.",
  "key_changes": [
    {
      "symbol": "005930", "name": "삼성전자",
      "observation": "거래량이 20일 평균 대비 5.0배로 늘었습니다.",
      "context": "이 종목에서 이런 규모의 거래량 변화가 감지된 건 최근 7일 내 처음입니다."
    }
  ],
  "portfolio_notes": [
    {
      "symbol": "SCHD", "name": "SCHD ETF",
      "observation": "SCHD ETF 비중이 총자산의 32.10%로 기준(30%) 이상입니다.",
      "as_of_note": "이 규칙 판정은 6일 전(2026-08-24) 기준입니다."
    }
  ],
  "possible_explanations": [
    {
      "symbol": "005930",
      "hypothesis_text": "이 거래량 증가는 오늘 발표된 실적과 관련 있을 가능성이 있습니다(가설이며 확인되지 않았습니다).",
      "is_hypothesis": true
    }
  ],
  "confirm_items": [
    "SCHD ETF 비중이 집중도 기준을 초과한 상태가 이어지고 있습니다."
  ],
  "disclaimer": "이 브리핑은 관찰된 사실과 그 연결을 정리한 것이며, 매매 판단이나 추천을 포함하지 않습니다. 가능한 설명은 가설로만 표시되며 확인된 사실이 아닙니다."
}
```

**스키마에 없는 필드(v3.2 (b) 원칙 그대로, 설계 수준에서 배제)**:
`direction`/`confidence`/`action`/`recommendation`/`target_price`/
`target_weight_pct` — 애초에 필드를 만들지 않는다(A2 공통 스키마, 다른
5개 생성기와 같은 원칙).

### 2-2. L3(가설) 격리 — 구조와 문구 이중 강제

PM 지시: "가능한 설명, 단 과거/현재 설명일 때만, '가설임을 명시' 필수."
이걸 스키마 레벨에서 두 가지로 강제하는 안을 제안한다:

1. **위치 격리**: 가설은 오직 `possible_explanations[]`에만 나온다.
   `summary`/`key_changes`/`portfolio_notes`/`confirm_items`에는 가설성
   문구가 있으면 안 된다(이건 audit 대상, §2-3). 필드 위치 자체가 "이건
   L1/L2다, 이건 L3다"를 구분하는 1차 신호다.
2. **필드 강제**: `possible_explanations[]`의 각 항목은 `is_hypothesis: true`
   불리언 필드를 갖는다(스키마가 항상 참으로 고정 — 이 배열에 들어간
   모든 항목은 가설이라는 뜻). 그리고 **텍스트 자체에도** "(가설이며
   확인되지 않았습니다)" 같은 명시 문구가 들어가야 한다(PM 지시 "가설임을
   명시 필수"를 문자 그대로 - 필드 위치만으로는 부족하고 텍스트 자체에도
   있어야 한다는 뜻으로 읽었다). 렌더링 시(대시보드) `is_hypothesis`를
   보고 항상 "[가설]" 배지를 붙이는 이중 표시도 제안(A5 구현 시).

**시제 제약은 스키마가 강제할 수 없다** — "과거/현재 설명일 때만"이라는
조건은 문장의 시제 문제라, JSON 스키마(필드 존재/타입)로는 못 잡는다.
이건 프롬프트 레벨(Step 4)의 책임으로 넘긴다 — 이 사실을 부록 A에 남긴다.

### 2-3. audit() 재사용 판단

기존 5개 생성기의 `FORBIDDEN_FIELDS`/`FORBIDDEN_PHRASES` 확장을 비교했다:

| 파일 | FORBIDDEN_FIELDS 추가 | FORBIDDEN_PHRASES 추가 |
|---|---|---|
| `rule_trigger_report.py` | 없음(BASE 그대로) | `"매수"`, `"보입니다"` |
| `market_indicators.py` | `"국면"`,`"점수"`,`"순위"`,`"등급"`,`"신호등"` | `"상승장"`,`"하락장"`,`"국면 전환"`,`"국면 진입"`,`"진입 임박"`,`"매수"`,`"사도 됨"` |
| `news_event_cards.py` | `"호재"`,`"악재"`,`"판단"` | `"매수"`,`"보입니다"` |
| `portfolio_report.py` | BASE에서 `rank`/`ranking` 제외(파일 고유 사정) | `"정리하세요"` |
| `post_trade_review.py` | 없음(BASE 그대로) | 없음(BASE 그대로) |

**결론: `analyze_lib.audit_schema()`(A2 Step 3, 경로단위 allowlist)를
그대로는 재사용할 수 없다** — 코드를 다시 확인한 결과 `audit_schema()`는
`FORBIDDEN_FIELDS_BASE`/`FORBIDDEN_PHRASES_BASE`(모듈 전역 상수)만 검사하고,
기존 5개 파일처럼 "이 파일 고유의 확장 문구"를 추가로 넣는 파라미터가
없다. AI Briefing은 산문형 브리핑을 만드는 첫 생성기라 완곡한 권유형
표현(아래 §2-4)처럼 BASE에 없는 새 위반 패턴이 필요한 게 거의 확실하다.
두 가지 방향이 있다:

- **(a) 기존 5개처럼 이 파일 전용 `audit()`를 새로 만든다** — 일관성은
  있지만 "audit() 복붙을 더 늘리지 않는다"는 A2 Step 3의 취지와 어긋남.
- **(b, 제안) `audit_schema()`에 `extra_forbidden_phrases`(선택 인자)를
  추가해 호출자가 파일 고유 확장 문구를 넘길 수 있게 한다** — 함수
  시그니처를 조금 넓히는 작은 변경이고, 6번째 파일이 또 통짜 복붙
  `audit()`를 만드는 것보다 A2가 만든 공용 인프라를 실제로 공용으로
  쓰는 방향에 맞는다.

**PM 확인 필요**(부록 B) — (b)는 A2 Step 3에서 이미 구현된 함수의
시그니처를 넓히는 것이라, "이 설계 문서는 코드를 안 만든다"는 원칙과
어떻게 조율할지 PM 판단이 필요하다(이 문서는 방향만 제안하고, 실제
시그니처 변경은 A3 코드 구현 단계에서 하는 안을 제안).

### 2-4. 신규 위반 후보 문구 — "완곡한 권유형"

PM이 예시로 든 "그래서 ~하는 게 좋습니다" 계열을 실제로 점검했다.
기존 `FORBIDDEN_PHRASES_BASE`(`매수하세요`/`매도하세요`/`사세요`/`파세요`/
`추천`/`권장`/`권합니다`/`유망`/`저평가`/`고평가`/`목표가`/`목표주가`/
`상승 전망`/`하락 전망`/`전망됩니다`/`예상됩니다`/`기대됩니다`/`판단됩니다`/
`지금이 기회`/`그래서 사도`/`팔아야`/`1위`/`순위`)에 **없는** 완곡한
권유형 후보를 모았다:

- "~하는 게 좋습니다" / "~하는 것이 좋겠습니다" / "~하는 게 낫습니다"
- "고려해 보세요" / "고려하시는 것도" / "검토해 보시길" / "재검토가 필요"
- "~할 때입니다" / "적기" (`"지금이 기회"`는 BASE에 있지만 "적기"는 다른
  문자열이라 안 걸림)
- "대응이 필요합니다" / "조치가 필요합니다" / "주목할 필요가 있습니다"

**이 문서가 명확히 기록해야 할 한계**: 이 중 상당수는 **순수 문자열
매칭으로 완전히 못 잡는다.** PM이 든 예시가 정확히 이 문제를 보여준다 —
"~할 가능성이 높습니다"라는 구절은:
- "이 상승은 어제 발표 때문일 가능성이 높습니다" → **L3(허용)**, 과거 사실에
  대한 가설.
- "앞으로 더 오를 가능성이 높습니다" → **L4(금지)**, 미래에 대한 처방성
  전망.

둘 다 "가능성이 높습니다"라는 동일 문자열을 포함한다. 이 문구 자체를
`FORBIDDEN_PHRASES`에 넣으면 L3(허용돼야 하는 가설)까지 막혀버리고, 안
넣으면 L4가 새어나갈 수 있다. **결론: 문자열 매칭 audit()는 L3/L4 경계의
2차 방어선일 뿐이고, 1차 방어선은 항상 프롬프트(Step 4)다** — 이건 이미
`news_event_cards.py`가 쓰는 이중 방어 패턴(`strip_forbidden` + 프롬프트
자체의 "이런 표현 쓰지 마라" 지시)과 같은 원칙이며, AI Briefing에서는
시제 문제 때문에 그 한계가 더 뚜렷하게 드러난다는 사실을 기록해둔다.

### 2-5. 필드명 충돌 검사 (완료)

제안한 출력 필드(`summary`/`key_changes`/`observation`/`context`/
`portfolio_notes`/`as_of_note`/`possible_explanations`/`hypothesis_text`/
`is_hypothesis`/`confirm_items`/`disclaimer`/`generated_at`/`schema`)를
`FORBIDDEN_FIELDS_BASE`(`direction`/`confidence`/`action`/`recommendation`/
`signal`/`buy`/`sell`/`score`/`target_weight_pct`/`rating`/`rank`/`ranking`/
`phase`/`regime`/`grade`/`color`/`colour`)와 대조했다 — **충돌 없음**.

---

## 부록 A. Step 3~4에서 다룰 것 (이 문서가 확정 안 함)

1. 호출 시점 — `daily.yml`(11:00 UTC)/`news_event_cards.yml`(09:50 UTC)/
   `market_indicators.yml`(10:10 UTC) 중 어디에 얹을지, 아니면 별도
   워크플로로 뺄지. change_events가 news_event_cards.yml 산출물이라 그
   워크플로 끝단이 자연스러운 후보라는 점만 이 문서에서 관찰로 남긴다
   (결정은 Step 3).
2. `CLAUDE_API_KEY` 호출 비용 추정, §19.5 월 상한과의 대조 — **§19.5
   숫자를 이 세션이 갖고 있지 않다.** Step 3 착수 시 PM에게 요청 필요.
3. AI 호출 실패 시 change_events 원자료가 TODAY에 그대로 뜨는지 확인 —
   이미 사실이다: `index.html`의 `loadTodayEvents()`(2026-08-30 A2→A1
   연결)는 AI Briefing과 무관하게 독립적으로 `change_events`를 직접
   읽어 렌더링한다(현재 아키텍처에 AI Briefing이 껴 있지 않음). AI
   Briefing이 추가되어도 이 경로를 안 건드리면 "AI가 단일 장애점이 되지
   않는다"는 요구사항이 설계상 자동으로 충족된다 — Step 3에서 이 관찰을
   전제로 삼을 것을 제안.
4. L3의 "과거/현재 설명일 때만" 시제 제약을 프롬프트가 어떻게 강제할지
   구체 문구.
5. 시스템 프롬프트 초안, 좋은 예/나쁜 예.

## 부록 B. PM 확인 필요 목록

1. **§1-3**: `priority_score`를 프롬프트에 아예 안 넣는 C안을 이 문서가
   제안했다 — A안(숫자는 주되 인용 금지 지시)이나 B안(등급화)을 원하면
   재작성 필요.
2. **§2-3**: `audit_schema()`에 `extra_forbidden_phrases` 파라미터를
   추가하는 (b)안을 제안했다 — 기존 5개 파일처럼 새 `audit()`를 통짜로
   만드는 (a)안을 원하면 재작성 필요. (b)를 택해도 실제 시그니처 변경은
   코드 구현 단계(별도 지시) 몫이라는 점은 이 문서가 이미 전제했다.
3. **§2-2**: 가설 필드에 `is_hypothesis: true` 불리언 + 텍스트 내
   명시 문구를 이중으로 강제하는 안 — 텍스트 명시만으로 충분하다고
   보면 불리언 필드는 과설계일 수 있다.
