"""[v4.0 Phase A3] AI Briefing — change_events를 사람이 읽는 브리핑으로 합성
(A3_AI_Briefing_Design.md Step 1~4 최종본, 2026-08-30 PM 지시로 코드 구현).

**예측이 아니다 — v3.2 (b) 원칙의 A3 버전.** news_event_cards.json의
change_events(A2 산출물, 상위 우선순위 N건) + portfolio_report.json의
규칙 위반 상태 + real_portfolio.json 요약을 Claude에게 보내 사람이 읽을
자연어 브리핑을 만든다. 출력 스키마에 direction/confidence/action/
target_weight_pct 같은 필드가 아예 없다 — 다른 5개 생성기와 같은 설계.

**두 겹 방어, 순서가 다르다(PM 지시 "순서 명확히"):**

  **1차 방어선(사전) — SYSTEM_PROMPT.** L1(관찰)~L4(처방) 4단계 경계와
  "L4를 판별하는 기준은 문구가 아니라 시제다"를 모델에게 직접 지시한다
  (설계 문서 4-2). 이게 실질적인 방어의 대부분을 맡는다.

  **2차 방어선(사후) — audit_schema().** 모델 응답을 받은 뒤
  `analyze_lib.audit_schema()`로 FORBIDDEN_PHRASES_BASE +
  EXTRA_FORBIDDEN_PHRASES(이 파일 고유)를 재귀 검사한다. **이 2차
  방어선은 순수 문자열 매칭이라 태생적 한계가 있다** — 설계 문서
  §2-4가 이미 기록한 대로 "~가능성이 높습니다" 같은 시제 의존적 위반은
  같은 문자열이 L3(허용)와 L4(금지)를 오가서 문자열만으로는 구분이 안
  된다. 이 파일의 self-test가 이 한계를 실제로 재현한다 — 설계 문서의
  나쁜 예 3건 중 "시제"만으로 위반인 문장은 EXTRA_FORBIDDEN_PHRASES에
  "앞으로"/"게 좋겠습니다" 같은 **구체적인 문구**가 실제로 들어 있어야만
  걸린다(run_self_test 참고). 2차 방어선이 걸리면 status="audit_failed"로
  표시하고 briefing 내용은 전부 비운다 — 파일 저장 자체를 막지는 않는다
  (market_indicators.py의 "위반 시 전체 반려"와 다른 선택: 이 파일은 매일
  커밋되는 대상이라 "오늘은 감사에 걸려 브리핑이 비어 있다"는 사실 자체가
  대시보드에 남아야 한다는 판단 — 자세한 이유는 generate_briefing() 참고).

**호출 조건 — "change_events 있을 때만"(PM 지시).** change_events가
비어 있으면 Claude API를 아예 호출하지 않는다(비용 낭비 방지 — "오늘
특이사항 없음"은 규칙 기반 산술로 충분하다는 판단, A3 설계 §3-2/§3-3).
이 판단은 워크플로 레벨(news_event_cards.yml의 조건부 스텝)과 이 파일
내부(generate_briefing()) 양쪽에 있다 — 워크플로 가드는 CI에서 스크립트를
아예 안 돌리는 효율 목적, 이 파일 내부 체크는 workflow_dispatch로 수동
실행되거나 로컬에서 직접 돌아도 안전하게 동작하기 위한 방어적 목적이다.

**AI가 단일 장애점이 아니다.** `index.html`의 `loadTodayEvents()`(TODAY
"오늘의 사건" 카드)는 이 파일과 완전히 독립적으로 news_event_cards.json의
change_events를 직접 읽는다 — 이 파일이 실패하거나 아예 실행 안 돼도
`loadTodayEvents()`는 영향을 받지 않는다(A3 설계 §3-5에서 이미 코드로
확인한 사실, 이 파일 신설 이후에도 그 사실은 그대로다 — 이 파일은
loadTodayEvents()가 읽는 어떤 파일/필드도 건드리지 않는다)."""
import argparse
import json
from datetime import datetime, timezone

import requests

from analyze_lib import CLAUDE_API_KEY, audit_schema, load_json, save_json

CARDS_FILE = "news_event_cards.json"
PORTFOLIO_REPORT_FILE = "portfolio_report.json"
REAL_PORTFOLIO_FILE = "real_portfolio.json"
BRIEFING_FILE = "ai_briefing.json"

# TODAY 카드(index.html)와 동일한 상위 N건 — A3 설계 §1-1 "change_events(상위
# N건)"의 N을 TODAY_EVENTS_LIMIT(index.html)과 맞춘다. 두 곳이 다른 숫자를
# 쓰면 "브리핑이 언급한 사건"과 "TODAY가 보여주는 사건"이 어긋난다.
CHANGE_EVENTS_LIMIT = 3

# 이 파일이 실제로 쓰는 모델 문자열. news_event_experiment.JUDGE_MODEL을
# import하지 않는다 — news_event_cards.py가 이미 그 역방향 의존(Core가
# Alpha Lab을 import)을 갖고 있고(CLAUDE.md에 기록된 사실), 세 번째 파일이
# 같은 패턴을 반복하면 나중에 Alpha Lab을 옮기거나 지울 때 발이 더 묶인다.
# analyze_lib.ask_claude_decision()도 같은 이유로 모델 문자열을 자체
# 상수/리터럴로 갖고 있다 — 그 선례를 따른다. 값 자체는 JUDGE_MODEL과
# 우연히 같다(claude-api 스킬로 확인한 현재 실제 모델 - A3 설계 §3-1).
BRIEFING_MODEL = "claude-sonnet-4-6"

# A3 설계 §2-4가 모은 후보를 구현 단계에서 최종 선택한 것(부록 A item 1
# "최종 선택은 구현 단계 몫"). 원안보다 짧은 조각으로 다듬었다 — 한국어는
# 활용형이 다양해서("검토하시는 게 좋겠습니다" vs "검토해 보세요") 긴
# 문구를 그대로 넣으면 조사/어미가 조금만 달라져도 못 잡는다. "앞으로"는
# 원안에 없었지만 SYSTEM_PROMPT의 "미래 시제 자체를 경계하라" 지시가
# 이 단어를 직접 지목하므로, 프롬프트가 이미 금지한 단어를 2차 방어선도
# 그대로 잡게 하는 게 자연스러운 확장이다(설계를 벗어난 임의 추가가
# 아니라 프롬프트 원문에서 직접 도출).
EXTRA_FORBIDDEN_PHRASES = (
    "앞으로",
    "게 좋습니다", "게 좋겠습니다", "게 낫습니다",
    "고려해", "검토해 보",
    "할 때입니다", "적기",
    "대응이 필요", "조치가 필요", "재검토가 필요", "주목할 필요",
)

# 스키마 필드 화이트리스트 — 모델 응답에서 이 필드 밖의 키는 clean_response()가
# 버린다(news_event_cards.py의 strip_forbidden/CARD_FIELDS와 같은 패턴).
KEY_CHANGE_FIELDS = ("symbol", "name", "observation", "context")
PORTFOLIO_NOTE_FIELDS = ("symbol", "name", "observation", "as_of_note")
EXPLANATION_FIELDS = ("symbol", "hypothesis_text", "is_hypothesis")

# 코드가 고정 — 모델에게 이 문구를 그대로 출력하라고 프롬프트에 이미
# 지시했지만(4-2), 실제로 쓰는 값은 모델 출력을 신뢰하지 않고 여기서
# 덮어쓴다(rule_trigger_report.py의 disclaimer가 애초에 모델에게 묻지
# 않는 Python 리터럴인 것과 같은 이유 — 고정 문구는 모델이 만들 필요가
# 없다. 이건 설계 문서 4-2의 프롬프트 문구를 안 바꾸는 선에서의 구현
# 단계 보강이다).
#
# self-test로 실제 발견한 버그(2026-08-30): 설계 문서 4-2가 예시로 든
# 원문("...추천을 포함하지 않습니다")은 "추천을 포함하지 않는다"고
# 말하려다가 "추천"이라는 금지 문구 자체를 문장에 남겨서, 이 disclaimer가
# 매번 자기 자신의 audit_schema() 검사에 걸리는 자기지시적 함정이었다
# (news_event_cards.py 등이 이미 겪은 것과 같은 종류). 뜻은 그대로 두고
# 금지어를 피해 다시 썼다 — SYSTEM_PROMPT의 예시 문구도 이 값과 맞춰
# 같이 고쳤다(모델이 뭘 반환하든 이 값으로 덮어쓰므로 기능상 프롬프트
# 예시와 실제 값이 달라도 동작엔 문제없지만, 둘을 다르게 두면 나중에
# 읽는 사람이 헷갈린다).
DISCLAIMER_TEXT = (
    "이 브리핑은 관찰된 사실과 그 연결을 정리한 것이며, 매매 판단이나 "
    "매수·매도 조언을 담지 않습니다. 가능한 설명은 가설로만 표시되며 "
    "확인된 사실이 아닙니다."
)

# A3 설계 문서 §4-2 그대로. 입력 데이터(JSON)는 이 문자열 뒤에 이어 붙인다.
SYSTEM_PROMPT = """너는 개인 투자자를 위한 포트폴리오 브리핑 작성자다. 아래 데이터를 보고
오늘 무슨 일이 있었는지 정리한다.

[네 출력은 4단계로 나뉜다]
- L1(관찰): 데이터에 있는 사실을 그대로 서술 — 허용
- L2(연결): 여러 관찰을 연결하거나 지금 상태를 설명 — 허용
- L3(가설): 과거/현재에 일어난 일에 대한 "가능한 설명" — 조건부 허용(아래)
- L4(처방): 무엇을 사거나 팔라는 조언, 목표가, "지금이 적기" 같은 행동
  촉구, 그리고 앞으로 무슨 일이 일어날지에 대한 어떤 서술도 — 절대 금지

[L4를 판별하는 기준은 문구가 아니라 시제다]
"가능성이 높습니다"라는 같은 문구도:
  - "이 상승은 어제 실적 발표 때문일 가능성이 높습니다" → 과거 사실에
    대한 설명 → L3(허용)
  - "앞으로 더 오를 가능성이 높습니다" → 아직 일어나지 않은 일 → L4(금지)
문장을 쓰기 전에 스스로에게 물어라: "이 문장이 아직 일어나지 않은 일을
말하고 있는가?" 그렇다면, 문구가 아무리 조심스러워도 쓰지 마라.

[금지 문구 — 예시일 뿐, 이 목록에 없어도 같은 성격이면 금지]
매수하세요, 매도하세요, 사세요, 파세요, 추천, 권장, 고려해 보세요,
검토해 보세요, ~하는 게 좋습니다, ~할 때입니다, 목표가, 목표주가, 유망,
저평가, 고평가, 지금이 기회, 앞으로 ~것이다, ~할 전망입니다,
~것으로 예상됩니다, ~것으로 기대됩니다.

[미래 시제 자체를 경계하라]
"-것이다", "-할 전망", "-할 것으로 보입니다", "앞으로" 같은 표현이
문장에 있다면 사실 서술이 아니라 예측일 가능성이 높다 — 과거/현재형으로
고쳐 쓰거나 아예 빼라.

[L3(possible_explanations)에 대한 별도 규칙]
- 오직 possible_explanations 필드에만 넣는다. summary/key_changes/
  portfolio_notes/confirm_items에는 가설을 절대 넣지 마라 — 그 필드들은
  L1/L2 전용이다.
- 반드시 과거형 또는 현재형 문장으로만 써라. "~했을 가능성이
  있습니다"(과거)나 "~인 상태로 보입니다"(현재)는 되지만, "~할
  것입니다"/"~할 가능성이 있습니다"(미래) 형태는 절대 안 된다.
- 문장 끝에 반드시 "(가설이며 확인되지 않았습니다)"를 붙여라.
- is_hypothesis는 항상 true로 채운다.
- 근거가 데이터에 없으면 이 필드 자체를 비워둬라 — 억지로 채우지 마라.

[stale_days 처리]
portfolio_rules.stale_days가 0보다 크면, 그 규칙 위반을 "지금"이나
"현재"처럼 서술하지 말고 그 판정이 며칠 전 것인지
portfolio_notes[].as_of_note에 반드시 명시하라(예: "이 규칙 판정은
6일 전 기준입니다"). stale_days가 0에 가까우면 이 언급은 생략해도 된다.

[출력 형식]
다른 설명 텍스트 없이 순수 JSON만 출력한다. 아래 스키마의 필드만 쓰고
새 필드를 만들지 마라. 모든 문자열 값은 큰따옴표로 감싸고, 문자열 안에
줄바꿈이나 큰따옴표를 넣지 마라.

{
  "summary": "전체 요약 한두 문장",
  "key_changes": [{"symbol": "...", "name": "...", "observation": "...", "context": "..."}],
  "portfolio_notes": [{"symbol": "...", "name": "...", "observation": "...", "as_of_note": "..." 또는 null}],
  "possible_explanations": [{"symbol": "...", "hypothesis_text": "...", "is_hypothesis": true}],
  "confirm_items": ["..."],
  "disclaimer": "이 브리핑은 관찰된 사실과 그 연결을 정리한 것이며, 매매 판단이나 매수·매도 조언을 담지 않습니다. 가능한 설명은 가설로만 표시되며 확인된 사실이 아닙니다."
}

이제 아래 데이터를 보고 브리핑을 작성하라."""


# ── 입력 조립 (A3 설계 §1-2/§1-3) ───────────────────────────────────────────

def select_top_change_events(cards_data, limit=CHANGE_EVENTS_LIMIT):
    """news_event_cards.json의 change_events를 priority_score 내림차순으로
    정렬해 상위 limit건만, §1-3에서 확정한 필드만 남겨 반환한다.
    **priority_score 자체는 넣지 않는다**(§1-3 C안 — Step 4에서 PM의
    "착수 승인"을 이 해석 유지로 받아들여 그대로 구현) — 배열 순서 자체가
    이미 우선순위를 반영하므로 숫자를 프롬프트에 노출하지 않는다."""
    events = cards_data.get("change_events") or []
    ordered = sorted(
        events,
        key=lambda e: (e.get("priority") or {}).get("priority_score", float("-inf")),
        reverse=True,
    )
    items = []
    for e in ordered[:limit]:
        asset = e.get("asset") or {}
        items.append({
            "symbol": asset.get("symbol"),
            "name": asset.get("name"),
            "market_country": asset.get("market_country"),
            "event_type": e.get("event_type"),
            "observed_value": e.get("observed_value"),
            "baseline": e.get("baseline"),
            "change": e.get("change"),
            "timestamp": e.get("timestamp"),
        })
    return items


def compute_stale_days(generated_at, now):
    """§1-1 "portfolio_report.json은 최대 6일까지 묵을 수 있다"를 프롬프트
    입력에 강제로 실어 보내기 위한 계산. 달력 날짜 차이로 계산한다(예:
    8/24 23:10 생성분을 8/30 00:00에 보면 실제 경과시간은 144시간 미만이라
    timedelta.days는 5가 나오지만, 설계 문서 예시("6일 전")가 말하는 건
    달력상 며칠 전인가이다 — .date() 차이를 쓴다). 파싱 실패 시 None —
    호출자가 "모름"으로 취급하게 한다(0으로 잘못 단정하지 않음)."""
    if not generated_at:
        return None
    try:
        gen = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, (now.date() - gen.date()).days)


def build_portfolio_rules_input(portfolio_report_data, now):
    generated_at = portfolio_report_data.get("generated_at")
    matches = portfolio_report_data.get("rule_matches") or []
    return {
        "generated_at": generated_at,
        "stale_days": compute_stale_days(generated_at, now),
        "matches": [
            {k: m.get(k) for k in ("rule", "symbol", "name", "threshold", "observed", "fact")}
            for m in matches
        ],
    }


def build_real_portfolio_input(real_portfolio_data):
    """§1-3 최소 노출 원칙 — avg_price/quantity/current_price/eval_amount는
    빼고 비중(weight_pct)·수익률만 넘긴다. weight_pct는
    analyze_lib.compute_portfolio_relevance()와 같은 방식으로 계산한다
    (cash + 전 종목 eval_amount_krw 합을 분모로)."""
    cash = real_portfolio_data.get("cash") or 0
    positions = real_portfolio_data.get("positions") or []
    total = cash + sum(p.get("eval_amount_krw") or 0 for p in positions)
    pos_out = []
    for p in positions:
        eval_krw = p.get("eval_amount_krw") or 0
        weight_pct = round(eval_krw / total * 100, 2) if total > 0 else None
        pos_out.append({
            "symbol": p.get("symbol"), "name": p.get("name"),
            "weight_pct": weight_pct, "return_pct": p.get("return_pct"),
        })
    return {
        "synced_at": real_portfolio_data.get("synced_at"),
        "cash_krw": cash,
        "total_assets_krw": round(total, 2) if total else total,
        "positions": pos_out,
    }


def build_input_data(cards_data, portfolio_report_data, real_portfolio_data, now):
    """반환: (프롬프트에 넣을 입력 dict, 상위 change_events 리스트) —
    후자를 별도로 돌려주는 이유는 호출자가 "change_events가 비었는지"를
    다시 계산하지 않고 그대로 재사용하게 하기 위해서다."""
    change_events = select_top_change_events(cards_data)
    return {
        "change_events": {
            "generated_at": cards_data.get("generated_at"),
            "items": change_events,
        },
        "portfolio_rules": build_portfolio_rules_input(portfolio_report_data, now),
        "real_portfolio": build_real_portfolio_input(real_portfolio_data),
    }, change_events


# ── Claude 호출 (1차 방어선 = SYSTEM_PROMPT) ────────────────────────────────

def ask_briefing(input_data):
    """news_event_cards.ask_explanation()과 같은 방어 패턴(코드펜스 제거,
    {}추출, 1회 재시도, content 없으면 상태코드/본문 일부만 로깅 — 키 원문은
    절대 남기지 않음, 2026-08-28 보안 사고 대응 관례 그대로).

    이 저장소는 requests로 API를 직접 호출하는 관례를 이미 갖고 있고
    (CLAUDE.md: "유일한 서드파티 의존은 requests"), 이 파일도 그 관례를
    따른다 — 새 SDK 의존을 들이지 않는다."""
    prompt = SYSTEM_PROMPT + "\n\n[입력 데이터]\n" + json.dumps(input_data, ensure_ascii=False, indent=2)
    for attempt in range(2):
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": BRIEFING_MODEL, "max_tokens": 1600,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            data = resp.json()
            if "content" not in data:
                print(f"⚠️ AI Briefing: Claude API 응답에 content 없음 "
                      f"(status={resp.status_code}, body={json.dumps(data)[:300]})")
                if attempt == 0:
                    continue
                return None
            text = data["content"][0]["text"].strip()
            text = text.replace("```json", "").replace("```", "").strip()
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1:
                text = text[s:e + 1]
            return json.loads(text)
        except Exception as e:
            print(f"⚠️ AI Briefing: Claude API 호출 예외 ({type(e).__name__}: {e})")
            if attempt == 0:
                continue
            return None
    return None


# ── 응답 정제 + 2차 방어선 ──────────────────────────────────────────────────

def _pick(d, keys):
    if not isinstance(d, dict):
        return {}
    return {k: d.get(k) for k in keys if k in d}


def clean_response(raw):
    """모델 응답에서 허용 필드만 남긴다(news_event_cards.strip_forbidden과
    같은 역할) — 이것도 방어선이지만 audit_schema()보다 앞선, 별개의
    "필드 화이트리스트" 단계다(문구 검사가 아니라 구조 검사)."""
    if not isinstance(raw, dict):
        raw = {}
    cleaned = {
        "summary": raw.get("summary") if isinstance(raw.get("summary"), str) else None,
        "key_changes": [_pick(x, KEY_CHANGE_FIELDS) for x in (raw.get("key_changes") or []) if isinstance(x, dict)],
        "portfolio_notes": [_pick(x, PORTFOLIO_NOTE_FIELDS) for x in (raw.get("portfolio_notes") or []) if isinstance(x, dict)],
        "confirm_items": [c for c in (raw.get("confirm_items") or []) if isinstance(c, str)],
    }
    explanations = []
    for x in (raw.get("possible_explanations") or []):
        if not isinstance(x, dict):
            continue
        picked = _pick(x, EXPLANATION_FIELDS)
        picked["is_hypothesis"] = True  # 항상 강제 — 모델이 뭘 보내든 신뢰 안 함(§2-2)
        explanations.append(picked)
    cleaned["possible_explanations"] = explanations
    return cleaned


def empty_briefing_fields():
    return {"summary": None, "key_changes": [], "portfolio_notes": [],
            "possible_explanations": [], "confirm_items": [], "disclaimer": None}


def build_report(raw, generated_at, status):
    cleaned = clean_response(raw) if status == "ok" else empty_briefing_fields()
    if status == "ok":
        cleaned["disclaimer"] = DISCLAIMER_TEXT  # 코드가 고정, 모델 출력 무시
    cleaned["generated_at"] = generated_at
    cleaned["schema"] = "ai_briefing_v1"
    cleaned["status"] = status
    return cleaned


def generate_briefing(cards_data, portfolio_report_data, real_portfolio_data, now=None):
    """전체 파이프라인. 반환: (report, violations) — violations는
    status=="audit_failed"일 때만 비지 않는다(참고용, report 자체에는
    이미 반영 안 됨 — report의 briefing 필드는 항상 비어 있음)."""
    now = now or datetime.now(timezone.utc)
    generated_at = now.isoformat()
    input_data, change_events = build_input_data(cards_data, portfolio_report_data, real_portfolio_data, now)

    if not change_events:
        # PM 지시: "change_events 있을 때만 호출" — API를 아예 안 부른다.
        return build_report(None, generated_at, "no_events"), []

    raw = ask_briefing(input_data)
    if raw is None:
        return build_report(None, generated_at, "api_failed"), []

    candidate = build_report(raw, generated_at, "ok")
    violations = audit_schema(candidate, extra_forbidden_phrases=EXTRA_FORBIDDEN_PHRASES)
    if violations:
        return build_report(None, generated_at, "audit_failed"), violations

    return candidate, []


# ── 실행 ─────────────────────────────────────────────────────────────────

def run(args):
    cards_data = load_json(CARDS_FILE, {"change_events": []})
    portfolio_report_data = load_json(PORTFOLIO_REPORT_FILE, {"rule_matches": []})
    real_portfolio_data = load_json(REAL_PORTFOLIO_FILE, {"cash": 0, "positions": []})

    report, violations = generate_briefing(cards_data, portfolio_report_data, real_portfolio_data)
    if violations:
        report["_audit_violations"] = violations

    save_json(BRIEFING_FILE, report)
    msg = f"AI Briefing 상태: {report['status']}"
    if violations:
        msg += f" (감사 위반: {violations})"
    print(msg)


def main():
    p = argparse.ArgumentParser(description="AI Briefing - change_events를 사람이 읽는 브리핑으로 합성")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        run_self_test()
        return
    run(a)


def run_self_test():
    print("=== ai_briefing.py 자체 검증 (네트워크 미사용) ===\n")

    import sys
    import unittest.mock as mock
    mod = sys.modules[__name__]

    # 1) select_top_change_events - priority_score 내림차순 + 상위 N건 슬라이싱
    fake_events = [
        {"asset": {"symbol": "A", "name": "가", "market_country": "KR"}, "event_type": "거래량_급증",
         "observed_value": 1, "baseline": 1, "change": 1, "timestamp": "t1", "priority": {"priority_score": 0.5}},
        {"asset": {"symbol": "B", "name": "나", "market_country": "KR"}, "event_type": "가격_갭",
         "observed_value": 2, "baseline": 2, "change": 2, "timestamp": "t2", "priority": {"priority_score": 1.5}},
        {"asset": {"symbol": "C", "name": "다", "market_country": "US"}, "event_type": "변동성_급증",
         "observed_value": 3, "baseline": 3, "change": 3, "timestamp": "t3", "priority": {"priority_score": 0.9}},
        {"asset": {"symbol": "D", "name": "라", "market_country": "US"}, "event_type": "거래량_급증",
         "observed_value": 4, "baseline": 4, "change": 4, "timestamp": "t4"},  # priority 없음 - 방어적 케이스
    ]
    top = select_top_change_events({"change_events": fake_events}, limit=3)
    order = [x["symbol"] for x in top]
    print(f"[1] 정렬+상위3건: {order}")
    assert order == ["B", "C", "A"], f"priority_score 내림차순+상위3건이 아님: {order}"
    assert "priority_score" not in json.dumps(top), "priority_score가 프롬프트 입력에 새어나가면 안 됨(§1-3)"
    assert set(top[0]) == {"symbol", "name", "market_country", "event_type",
                            "observed_value", "baseline", "change", "timestamp"}

    # 2) compute_stale_days
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)
    sd = compute_stale_days("2026-08-24T23:10:00+00:00", now)
    print(f"[2] stale_days(2026-08-24 -> 2026-08-30) = {sd}")
    assert sd == 6
    assert compute_stale_days(None, now) is None
    assert compute_stale_days("garbage", now) is None

    # 3) build_real_portfolio_input - 최소 노출(avg_price/quantity/current_price 없음), weight_pct 계산
    fake_real = {"cash": 1_000_000.0, "synced_at": "2026-08-30T00:00:00+00:00",
                 "positions": [{"symbol": "005930", "name": "삼성전자", "quantity": "10",
                                 "avg_price": "70000", "current_price": "75000",
                                 "eval_amount_krw": 750000.0, "return_pct": 7.1}]}
    rp = build_real_portfolio_input(fake_real)
    print(f"[3] real_portfolio 입력: {rp}")
    assert rp["positions"][0]["weight_pct"] == round(750000.0 / 1750000.0 * 100, 2)
    for leaked in ("avg_price", "quantity", "current_price", "eval_amount_krw", "eval_amount"):
        assert leaked not in rp["positions"][0], f"최소노출 원칙 위반 - {leaked}가 새어나감(§1-3)"

    # 4) build_portfolio_rules_input - stale_days 포함, fact 텍스트 그대로 전달
    fake_pr = {"generated_at": "2026-08-24T23:10:00+00:00",
               "rule_matches": [{"rule": "집중도", "symbol": "SCHD", "name": "SCHD ETF",
                                  "threshold": "단일 종목 비중 30% 이상", "observed": "32.10%",
                                  "fact": "SCHD ETF 비중이 총자산의 32.10%로 기준 30% 이상",
                                  "extra_junk": "제거되어야 함"}]}
    pri = build_portfolio_rules_input(fake_pr, now)
    print(f"[4] portfolio_rules 입력: stale_days={pri['stale_days']}, matches={pri['matches']}")
    assert pri["stale_days"] == 6
    assert "extra_junk" not in pri["matches"][0]

    # 5) clean_response - 화이트리스트 밖 필드 제거, is_hypothesis 강제
    dirty_raw = {
        "summary": "요약", "extra_field": "버려져야함",
        "key_changes": [{"symbol": "A", "name": "가", "observation": "관찰",
                          "context": "맥락", "confidence": 99}],
        "portfolio_notes": [{"symbol": "B", "observation": "관찰2", "score": 1}],
        "possible_explanations": [{"symbol": "A", "hypothesis_text": "가설", "is_hypothesis": False}],
        "confirm_items": ["확인1", 123],  # 문자열 아닌 항목은 버려짐
    }
    cleaned = clean_response(dirty_raw)
    print(f"[5] 정제 결과: {cleaned}")
    assert "extra_field" not in cleaned
    assert "confidence" not in cleaned["key_changes"][0]
    assert "score" not in cleaned["portfolio_notes"][0]
    assert cleaned["possible_explanations"][0]["is_hypothesis"] is True, \
        "모델이 False를 보내도 is_hypothesis는 항상 True로 강제해야 함(§2-2)"
    assert cleaned["confirm_items"] == ["확인1"]

    # 6) build_report - disclaimer는 모델 출력과 무관하게 고정값
    raw_with_bad_disclaimer = {"summary": "s", "disclaimer": "모델이 지어낸 다른 문구"}
    report_ok = build_report(raw_with_bad_disclaimer, "2026-08-30T00:00:00+00:00", "ok")
    print(f"[6] disclaimer 강제: {report_ok['disclaimer'] == DISCLAIMER_TEXT}")
    assert report_ok["disclaimer"] == DISCLAIMER_TEXT, "disclaimer는 모델 출력이 아니라 코드 고정값이어야 함"

    # 7) [설계 문서 §4-3] 나쁜 예 3건이 2차 방어선(audit_schema)에 실제로 걸리는지,
    #    좋은 예는 안 걸리는지 - 이 파일 자체의 EXTRA_FORBIDDEN_PHRASES로 검증.
    #    (§2-4에서 이미 기록한 한계: 시제만으로 다른 두 문장이 "가능성이
    #    높습니다"라는 동일 문자열을 공유하면 문자열 매칭만으론 못 가른다 -
    #    아래는 그 한계를 인정한 채로, 실제 EXTRA 목록에 있는 구체적
    #    단어("앞으로"/"게 좋겠습니다")가 우연히도 세 나쁜 예 전부에 들어있어
    #    걸린다는 걸 보여준다. 시제 자체를 감지하는 게 아니다.)
    bad_examples = {
        "예시1(거래량_급증 미래시제)":
            "삼성전자 거래량이 급증했습니다. 이는 주가가 앞으로 더 오를 가능성이 "
            "높다는 신호일 수 있습니다.",
        "예시2(가설 미래시제, PM 지목 케이스)":
            "이 거래량 증가는 앞으로 시장에서 계속 주목받을 가능성이 높습니다"
            "(가설이며 확인되지 않았습니다).",
        "예시3(stale_days 무시+L4 처방)":
            "SCHD ETF 비중이 지금 32.10%로 기준을 넘어서 있어 정리하는 걸 "
            "검토하시는 게 좋겠습니다.",
    }
    good_examples = {
        "예시1 좋은예(observation)": "삼성전자 거래량이 20일 평균 대비 5.0배로 늘었습니다.",
        "예시1 좋은예(context)": "이런 규모의 거래량 증가가 감지된 건 최근 7일 내 이 종목에서 처음입니다.",
        "예시2 좋은예": "이 거래량 증가는 오늘 발표된 실적과 관련 있을 가능성이 있습니다(가설이며 확인되지 않았습니다).",
        "예시3 좋은예(observation)": "SCHD ETF 비중이 총자산의 32.10%로 기준(30%) 이상입니다.",
        "예시3 좋은예(as_of_note)": "이 규칙 판정은 6일 전(2026-08-24) 기준입니다.",
    }
    print("[7] 설계 문서 나쁜 예 3건 - audit_schema()로 실제 검증:")
    for label, text in bad_examples.items():
        v = audit_schema({"t": text}, extra_forbidden_phrases=EXTRA_FORBIDDEN_PHRASES)
        print(f"    {label}: {'CAUGHT' if v else 'MISSED'} -> {v}")
        assert v, f"나쁜 예가 2차 방어선에 안 걸림: {label} — {text!r}"
    print("[7] 설계 문서 좋은 예 - false positive 없는지:")
    for label, text in good_examples.items():
        v = audit_schema({"t": text}, extra_forbidden_phrases=EXTRA_FORBIDDEN_PHRASES)
        print(f"    {label}: {'clean' if not v else 'FALSE POSITIVE'} -> {v}")
        assert not v, f"좋은 예가 잘못 걸림(false positive): {label} — {text!r}"

    # 8) generate_briefing - change_events 없으면 API를 아예 호출하지 않는지
    with mock.patch.object(mod, "ask_briefing") as mock_ask:
        report, violations = generate_briefing({"change_events": []}, {"rule_matches": []},
                                                 {"cash": 0, "positions": []}, now=now)
        print(f"[8] change_events 없음 -> status={report['status']}, ask_briefing 호출됨={mock_ask.called}")
        assert report["status"] == "no_events"
        assert not mock_ask.called, "change_events가 없는데 API를 호출하면 안 됨(PM 지시)"
        assert report["summary"] is None and report["key_changes"] == []

    # 9) generate_briefing - API 실패(None 반환) -> status=api_failed, TODAY 원자료엔 영향 없음(별도 파일)
    with mock.patch.object(mod, "ask_briefing", return_value=None) as mock_ask:
        report, violations = generate_briefing({"change_events": fake_events}, {"rule_matches": []},
                                                 {"cash": 0, "positions": []}, now=now)
        print(f"[9] API 실패 -> status={report['status']}, ask_briefing 호출됨={mock_ask.called}")
        assert mock_ask.called, "change_events가 있으면 API를 호출해야 함"
        assert report["status"] == "api_failed"
        assert report["summary"] is None

    # 10) generate_briefing - 모델이 나쁜 예 문구를 실제로 반환 -> audit_failed, 내용 전부 비움
    dirty_model_response = {
        "summary": "이 거래량 증가는 앞으로 시장에서 계속 주목받을 가능성이 높습니다.",
        "key_changes": [], "portfolio_notes": [], "possible_explanations": [], "confirm_items": [],
    }
    with mock.patch.object(mod, "ask_briefing", return_value=dirty_model_response):
        report, violations = generate_briefing({"change_events": fake_events}, {"rule_matches": []},
                                                 {"cash": 0, "positions": []}, now=now)
        print(f"[10] 모델이 나쁜 예 반환 -> status={report['status']}, 위반={violations}")
        assert report["status"] == "audit_failed"
        assert violations, "감사 위반이 감지됐어야 함"
        assert report["summary"] is None and report["disclaimer"] is None, \
            "감사 실패 시 briefing 내용이 전부 비어 있어야 함"

    # 11) generate_briefing - 정상 응답 -> status=ok, disclaimer 강제, 필드 채워짐
    clean_model_response = {
        "summary": "삼성전자에서 거래량 급증이 관측됐습니다.",
        "key_changes": [{"symbol": "B", "name": "나", "observation": "관찰 문장입니다.", "context": "맥락 문장입니다."}],
        "portfolio_notes": [], "possible_explanations": [], "confirm_items": ["확인 항목입니다."],
        "disclaimer": "모델이 지어낸 문구(무시돼야 함)",
    }
    with mock.patch.object(mod, "ask_briefing", return_value=clean_model_response):
        report, violations = generate_briefing({"change_events": fake_events}, {"rule_matches": []},
                                                 {"cash": 0, "positions": []}, now=now)
        print(f"[11] 정상 응답 -> status={report['status']}, disclaimer 강제={report['disclaimer'] == DISCLAIMER_TEXT}")
        assert report["status"] == "ok"
        assert violations == []
        assert report["disclaimer"] == DISCLAIMER_TEXT
        assert report["summary"] == clean_model_response["summary"]

    # 12) run() 종단 - load_json/save_json/ask_briefing 전부 모킹, 실제 파일 안 건드림
    captured = {}
    with mock.patch.object(mod, "load_json", side_effect=lambda path, default:
                            {"change_events": fake_events, "generated_at": "g"} if path == CARDS_FILE
                            else {"rule_matches": [], "generated_at": None} if path == PORTFOLIO_REPORT_FILE
                            else {"cash": 0, "positions": []}), \
         mock.patch.object(mod, "ask_briefing", return_value=clean_model_response), \
         mock.patch.object(mod, "save_json", side_effect=lambda path, data: captured.update({"path": path, "data": data})):
        run(argparse.Namespace())
    print(f"[12] run() 저장 경로={captured['path']}, status={captured['data']['status']}")
    assert captured["path"] == BRIEFING_FILE
    assert captured["data"]["status"] == "ok"

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    main()
