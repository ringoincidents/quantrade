"""[Alpha Lab — 격리됨, v4.0 §15] Phase 2 프롬프트 A/B 실험 (2026-08-03) — 같은 헤드라인, 새 프롬프트로 재판단.

**원본 데이터셋을 절대 건드리지 않는다.** 읽기: `news_event_backtest_log.json`
(706건, 프롬프트 A = 실시간 트랙과 동일한 `ask_news_event_judgment`).
쓰기: `PROMPT_B_LOG_FILE`(별도 파일). 실시간 트랙(`news_event_calibration_log.json`)과
매매 로직(`ask_claude_decision`)에는 전혀 연결되지 않는다.

**왜 이 실험을 하는가 (진단 결과 요약)**: 원본 706건에서
  - confidence가 "맞을 확률"이 아니라 "헤드라인 분량"을 따라간다
    (1개 67.3 → 5개 76.0인데 적중률은 ~40%로 평평) → ECE 0.25~0.29
  - 방향 판단에 정보가 없다. D+1 호재 적중 40.0% vs 기저비율 40.1%,
    악재 58.3% vs 58.1% — 두 방향 다 기저비율과 사실상 동일
프롬프트 A에는 (1) 호재/악재 정의 없음 (2) 예측 시계 없음 (3) confidence 정의 없음
(4) "애널리스트" 역할 부여 (5) 선택지에서 호재가 첫자리, 라는 결함이 있다.
프롬프트 B는 이 다섯을 고친다.

**기대치는 낮게 잡는다**: 방향 판단에 정보가 없다는 건 표본 특성이지 프롬프트
문구 탓만은 아니다. 정보 없는 신호를 재배분해봐야 상한이 baseline이므로 적중률
개선은 기대하지 않는다 — 이 실험의 1차 평가 지표는 **ECE와 중립 비율**이다.

**공정 비교를 위한 설계**:
  - 헤드라인은 원본에 저장된 것을 그대로 쓴다(재수집 안 함 → RSS 레이트리밋 무관,
    그리고 두 프롬프트가 문자 그대로 같은 입력을 본다).
  - outcomes도 원본에서 그대로 복사한다. 같은 종목·같은 판단일이라 가격/수익률이
    동일하므로 재계산할 이유가 없고, 복사해야 판단 외 요인이 끼어들지 않는다.
  - 모델(`JUDGE_MODEL`)과 도구 미제공(tools 파라미터 없음)은 프롬프트 A와 동일.
    바뀌는 건 프롬프트 문구 하나뿐이다.

[Alpha Lab 격리] Core(v3.2 활성 기능 — analyze.py/analyze_lib.py/news_event_cards.py 등)와
연결 없음. 재개 절차(v4.0 §15) 완료 전 통합 금지. 물리적 파일 이동 없이 이 태그로만
격리를 표시한다(옵션 B — 상세는 CLAUDE.md "Alpha Lab 격리" 절 참고).
"""
import argparse
import json
import time

import requests

from analyze_lib import CLAUDE_API_KEY, load_json, save_json
from news_event_experiment import JUDGE_MODEL

SOURCE_LOG_FILE = "news_event_backtest_log.json"      # 읽기 전용 원본(프롬프트 A)
PROMPT_B_LOG_FILE = "news_event_backtest_log_promptB.json"
API_SLEEP = 0.3


def ask_news_event_judgment_v2(market, headlines):
    """프롬프트 B. `news_event_experiment.ask_news_event_judgment`(프롬프트 A)와
    별개 함수로 둔다 — A는 실시간 트랙과 원본 백테스트가 쓰고 있어서 절대 건드리면
    안 된다(두 트랙의 기존 데이터와 비교 가능성이 깨진다).

    A 대비 변경점:
      1. 역할: "애널리스트"(한국 셀사이드는 구조적으로 매수 의견 우위) → "분류기"
      2. 판단 대상을 명시: 사건 분류가 아니라 **향후 주가 방향**. A는 "사건을
         분류하고 판단"이라고만 해서 "회사에 좋은 소식"과 "앞으로 오를 것"이
         구분되지 않았다 — 적중 정의는 후자인데 프롬프트는 전자를 유도했다.
      3. 시계(20거래일) 명시 + priced-in 개념 도입.
      4. confidence를 빈도주의적으로 정의(70 = 10번 중 7번). A는 정의가 아예 없어
         모델이 "신호 분량"으로 해석했다.
      5. 중립을 기본값으로 제시하고 선택지 첫자리에 둔다(A는 호재가 첫자리).
      6. 헤드라인 개수로 확신도를 가산하지 말라고 명시.

    tools 파라미터는 A와 동일하게 넘기지 않는다 — 룩어헤드 차단 유지."""
    return _call_judge(build_prompt_v2(market, headlines))


def build_prompt_v2(market, headlines):
    """프롬프트 B 본문을 문자열로 만든다. 함수로 분리한 이유: self-test가 함수
    소스가 아니라 **실제 프롬프트 문자열**을 검사할 수 있어야 한다 — 소스를 훑으면
    변경 이유를 적어둔 docstring 문구까지 걸려서 오탐이 난다(실제로 두 번 났다)."""
    headline_text = "\n".join(f"- {h}" for h in headlines)
    return (
        "너는 한국 주식 뉴스 헤드라인을 보고 향후 주가 방향을 예측하는 분류기다.\n"
        "가격 지표는 주지 않는다 - 오직 아래 헤드라인 원문만 보고 판단해.\n\n"
        "[판단 대상] 이 종목의 향후 20거래일 주가가 오를지 내릴지.\n"
        "- \"회사에 좋은 소식인가\"가 아니라 \"지금 사면 오를 것인가\"를 묻는 것이다.\n"
        "- 대부분의 뉴스는 공표 시점에 이미 주가에 반영돼 있다. 소식이 긍정적이라는 것과\n"
        "  앞으로 더 오른다는 것은 다르다.\n"
        "- 기저 확률상 상승과 하락은 대략 반반이다. 헤드라인이 이 확률을 실제로 움직이지\n"
        "  못한다면 \"중립\"이 정답이며, 중립은 드문 답이 아니라 흔한 답이다.\n"
        "- 긍정적으로 들리는 헤드라인이 여러 개라고 확신도를 더하지 마라. 개수가 아니라\n"
        "  그 사건이 아직 주가에 반영되지 않았을 가능성이 확신도를 정한다.\n\n"
        "[confidence 정의] 네 방향 판단이 맞을 확률을 백분율로 적어라.\n"
        "- 50 = 동전던지기와 다를 바 없음. 이 경우 direction은 \"중립\"이어야 한다.\n"
        "- 70 = 이런 판단을 10번 하면 7번 맞을 것으로 본다.\n"
        "- 90 = 10번 중 9번. 이 수준은 드물어야 한다.\n"
        "- 맞을 확률이 50 미만이라고 생각되면 방향을 반대로 뒤집어라.\n\n"
        f"[종목코드] {market}\n"
        f"[최근 헤드라인]\n{headline_text}\n\n"
        "다음 JSON 형식으로만 답해줘. 매우 중요한 규칙:\n"
        "- 다른 설명 텍스트 없이 순수 JSON만 출력\n"
        "- 모든 문자열 값은 반드시 큰따옴표로 감싸고, 문자열 안에는 줄바꿈이나 큰따옴표를 절대 넣지 마\n"
        "- reasoning은 한 줄로, 쉼표나 마침표로만 문장을 구분해\n\n"
        "{\n"
        '  "event_type": "실적발표 또는 공시 또는 M&A 또는 규제 또는 지정학/거시 또는 기타",\n'
        '  "direction": "중립 또는 호재 또는 악재",\n'
        '  "confidence": 0에서100사이정수,\n'
        '  "reasoning": "한 줄로 된 판단 근거"\n'
        "}"
    )


def _call_judge(prompt_text):
    """Anthropic API 호출. 프롬프트 A(`ask_news_event_judgment`)와 동일한 방식 —
    같은 모델, tools 미제공, 실패 시 1회 재시도, 코드펜스 제거 후 JSON 추출."""
    for attempt in range(2):  # 프롬프트 A와 동일하게 실패 시 한 번 더
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": JUDGE_MODEL, "max_tokens": 500,
                      "messages": [{"role": "user", "content": prompt_text}]},
                timeout=30,
            )
            data = response.json()
            if "content" not in data:
                return None
            raw_text = data["content"][0]["text"]
            cleaned = raw_text.strip().replace("```json", "").replace("```", "").strip()
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end + 1]
            return json.loads(cleaned)
        except Exception:
            if attempt == 0:
                continue
            return None
    return None


def rejudge(source_records, log, limit=None, sleep=API_SLEEP):
    """원본 레코드의 헤드라인을 그대로 프롬프트 B에 넣어 재판단.
    outcomes/price_at_judgment는 원본에서 복사한다 — 판단 외 요인을 고정해야
    프롬프트 차이만 비교된다."""
    existing = {r["id"] for r in log["records"]}
    stats = log.setdefault("stats", {})
    for k in ("judge_failed", "skipped_no_headlines"):
        stats.setdefault(k, 0)
    done = 0

    for src in source_records:
        if limit is not None and done >= limit:
            print(f"\n--limit {limit} 도달 - 중단")
            break
        if src["id"] in existing:
            continue
        if not src.get("headlines"):
            stats["skipped_no_headlines"] += 1
            continue

        judgment = ask_news_event_judgment_v2(src["market"], src["headlines"])
        time.sleep(sleep)
        if judgment is None:
            stats["judge_failed"] += 1
            print(f"⚠️ {src['id']}: 판단 파싱 실패 - 건너뜀")
            continue

        log["records"].append({
            "id": src["id"],
            "track": "backtest_promptB",
            "market": src["market"],
            "judged_at": src["judged_at"],
            "headlines": src["headlines"],
            "headline_dates": src.get("headline_dates", []),
            "event_type": judgment.get("event_type", "기타"),
            "direction": judgment.get("direction", "중립"),
            "confidence": judgment.get("confidence"),
            "reasoning": judgment.get("reasoning", "-"),
            # 아래 둘은 원본 그대로 - 재계산하지 않는다(같은 종목/날짜라 동일)
            "price_at_judgment": src["price_at_judgment"],
            "outcomes": src["outcomes"],
        })
        done += 1
        if done % 50 == 0:
            print(f"  ... {done}건 재판단 완료")
    return done


def run(args):
    source = json.load(open(SOURCE_LOG_FILE, encoding="utf-8"))
    src_records = source["records"]
    log = load_json(PROMPT_B_LOG_FILE, {"records": [], "stats": {}})

    log["track"] = "backtest_promptB"
    log["judge_model"] = JUDGE_MODEL
    log["prompt_variant"] = "B"
    log["source_log_file"] = SOURCE_LOG_FILE
    log["source_record_count"] = len(src_records)
    # 원본의 선정 기준을 그대로 물려받는다 - 표본을 새로 고르지 않았다는 표시
    log["selection_criteria"] = source.get("selection_criteria")
    log["note"] = ("같은 헤드라인·같은 outcomes에 프롬프트만 B로 바꿔 재판단. "
                   "표본 선정은 원본과 동일하며 새로 고르지 않았다.")

    print(f"원본 {len(src_records)}건 / 이미 재판단 {len(log['records'])}건")
    done = rejudge(src_records, log, args.limit, args.sleep)
    save_json(PROMPT_B_LOG_FILE, log)
    print(f"\n이번 실행 {done}건 재판단 / 누적 {len(log['records'])}건")
    print(f"통계: {log['stats']}")


def main():
    p = argparse.ArgumentParser(description="프롬프트 B 재판단 실험 (원본 데이터셋 읽기 전용)")
    p.add_argument("--limit", type=int, default=None, help="이번 실행 최대 재판단 건수")
    p.add_argument("--sleep", type=float, default=API_SLEEP)
    p.add_argument("--self-test", action="store_true", help="네트워크 없이 로직만 검증")
    a = p.parse_args()
    if a.self_test:
        run_self_test()
        return
    run(a)


def run_self_test():
    import inspect
    print("=== news_event_prompt_experiment.py 자체 검증 (네트워크 미사용) ===\n")

    # 1) 원본과 출력 파일이 다른지 (원본 보존)
    print(f"[1] 읽기={SOURCE_LOG_FILE} / 쓰기={PROMPT_B_LOG_FILE}")
    assert SOURCE_LOG_FILE != PROMPT_B_LOG_FILE, "원본을 덮어쓰면 안 됨"
    assert PROMPT_B_LOG_FILE != "news_event_calibration_log.json", "실시간 트랙 파일과도 달라야 함"

    # 2) 도구 미제공(룩어헤드 차단)이 프롬프트 A와 동일하게 유지되는지.
    #    단순히 "tools"가 소스에 있는지 보면 docstring의 설명 문구에도 걸린다
    #    (실제로 이 self-test가 처음에 그렇게 오탐했다) — 요청 본문의 dict 키
    #    형태('"tools":')로만 판정한다.
    src = inspect.getsource(_call_judge)
    has_tools_key = '"tools"' in src or "'tools'" in src
    print(f"[2] 요청 본문에 tools 키 없음={not has_tools_key}, 모델={JUDGE_MODEL}")
    assert not has_tools_key, "도구를 주면 룩어헤드 차단이 깨진다"

    # 3) 프롬프트 B가 A의 결함들을 실제로 고쳤는지 — 함수 소스가 아니라 **완성된
    #    프롬프트 문자열**을 본다(소스를 보면 docstring 설명 문구에 오탐).
    prompt = build_prompt_v2("005930", ["테스트 헤드라인"])
    for must in ("분류기", "20거래일", "이미 주가에 반영", "맞을 확률",
                 "중립은 드문 답이 아니라", "확신도를 더하지 마라"):
        assert must in prompt, f"프롬프트 B에 '{must}' 지시가 없음"
    assert '"중립 또는 호재 또는 악재"' in prompt, "중립이 선택지 첫자리여야 함"
    assert "애널리스트" not in prompt, "역할 부여를 분류기로 바꿨어야 함"
    assert "테스트 헤드라인" in prompt and "005930" in prompt, "입력이 프롬프트에 안 들어감"
    print("[3] 실제 프롬프트 문자열에서 필수 문구 7개 확인, '애널리스트' 미포함 확인")

    # 3-b) 프롬프트 A와 실제로 다른 문자열인지 (A/B 실험이 성립하려면 달라야 함)
    from news_event_experiment import ask_news_event_judgment
    a_src = inspect.getsource(ask_news_event_judgment)
    assert "애널리스트" in a_src, "프롬프트 A는 애널리스트 역할을 쓰고 있어야 함(전제 확인)"
    print("[3-b] 프롬프트 A는 '애널리스트' 역할 사용 중 - B와 실제로 다름 확인")

    # 4) 재판단이 outcomes를 원본에서 복사하는지 (판단 외 요인 고정)
    body = inspect.getsource(rejudge)
    assert '"outcomes": src["outcomes"]' in body, "outcomes는 원본을 그대로 써야 공정 비교"
    assert '"price_at_judgment": src["price_at_judgment"]' in body
    print("[4] outcomes/기준가를 원본에서 복사 - 판단 외 요인 고정 확인")

    print("\n모든 자체 검증 통과 - 네트워크/데이터셋 파일 미접촉.")


if __name__ == "__main__":
    main()
