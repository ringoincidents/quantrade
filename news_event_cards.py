"""[v3.2 활성 기능] 뉴스 사건 설명 카드 생성 (2026-08-03).

**예측이 아니다.** "오늘 이 종목에 이런 뉴스가 있었다"는 사실 설명만 만든다.
출력 스키마에 `direction`/`confidence`/`action` 같은 필드가 **아예 없다** —
누락이 아니라 설계다. 방향 판단은 §2.1 게이트 미통과로 중단됐다(CLAUDE.md v3.2).

**기존 파이프라인 재사용**: 헤드라인 수집(`get_news_headlines`)과 사건유형 분류
(실적발표/공시/M&A/규제/지정학/거시/기타)는 Phase 2에서 만든 것을 그대로 쓴다.
바뀐 건 그 다음이다 — 예전엔 사건유형에 방향/확신도를 붙여 매매 판단으로 넘겼고,
지금은 사건유형 + 사실 요약만 남긴다.

**실시간 캘리브레이션 트랙과는 별개다.** `news_event_experiment.py`(→
`news_event_calibration_log.json`, 76건, 최초 코호트 D+20 = 2026-08-21)는
방향 판단의 캘리브레이션을 계속 검증하기 위해 **그대로 돈다** — 이 파일은 그
파이프라인을 건드리지 않고, 별도 출력(`CARDS_FILE`)만 만든다. 두 용도를 한
함수에 합치지 않은 이유가 그것이다.
"""
import argparse
import json
import time
from datetime import datetime

import requests

from analyze_lib import CLAUDE_API_KEY, get_news_headlines, load_json, save_json
from backtest import KRX_MARKET_CAP_TOP
from news_event_experiment import JUDGE_MODEL

CARDS_FILE = "news_event_cards.json"
UNIVERSE_SLEEP = 0.2
MAX_CARDS = 8  # 대시보드에 한 화면 분량만 — 전 종목을 나열하면 읽히지 않는다

# 카드에 실릴 수 있는 필드. 이 목록 밖의 키는 build_card가 버린다.
# 대시보드(index.html)의 NEWSCARD_FIELDS와 같은 집합이어야 한다.
CARD_FIELDS = ("market", "name", "event_type", "summary", "headlines")

# 이 필드들이 모델 응답에 섞여 나오면 카드에서 제거한다. 프롬프트에서 요구하지
# 않지만 모델이 습관적으로 붙일 수 있고, 하나라도 새어나가면 "예측 아님"이라는
# 이 카드의 전제가 깨진다.
FORBIDDEN_FIELDS = ("direction", "confidence", "action", "recommendation",
                    "target_weight_pct", "signal", "buy", "sell", "score",
                    "호재", "악재", "판단")


def build_explanation_prompt(market, headlines):
    """사실 설명만 요구하는 프롬프트. 방향/확신도를 묻지 않는다 —
    묻지 않으면 답에도 안 나온다는 게 첫 번째 방어선이고,
    strip_forbidden()이 두 번째 방어선이다."""
    headline_text = "\n".join(f"- {h}" for h in headlines)
    return (
        "너는 주식 뉴스 헤드라인을 읽고 '무슨 일이 있었는지'를 요약하는 설명자다.\n"
        "**주가 예측이나 매매 판단은 하지 않는다.** 좋은 소식인지 나쁜 소식인지도\n"
        "판정하지 마라 - 사실만 전달한다.\n\n"
        f"[종목코드] {market}\n"
        f"[최근 헤드라인]\n{headline_text}\n\n"
        "다음 JSON 형식으로만 답해줘. 매우 중요한 규칙:\n"
        "- 다른 설명 텍스트 없이 순수 JSON만 출력\n"
        "- 모든 문자열 값은 큰따옴표로 감싸고, 문자열 안에 줄바꿈이나 큰따옴표를 넣지 마\n"
        "- summary는 한두 문장. '무엇이 발표/공시/보도되었다'는 사실만 적는다.\n"
        "- summary에 전망, 기대감, 수혜, 호재/악재, 매수/매도, 목표가 같은 표현을 쓰지 마라.\n"
        "- 헤드라인에 없는 내용을 추측해서 채우지 마라.\n\n"
        "{\n"
        '  "event_type": "실적발표 또는 공시 또는 M&A 또는 규제 또는 지정학/거시 또는 기타",\n'
        '  "summary": "무슨 일이 있었는지에 대한 한두 문장 사실 설명"\n'
        "}"
    )


def strip_forbidden(raw):
    """모델 응답에서 예측성 필드를 제거하고 허용 필드만 남긴다.
    반환: (정제된 dict, 제거된 필드 목록)."""
    removed = [k for k in raw if k in FORBIDDEN_FIELDS]
    cleaned = {k: v for k, v in raw.items() if k not in FORBIDDEN_FIELDS}
    return cleaned, removed


def ask_explanation(market, headlines):
    prompt = build_explanation_prompt(market, headlines)
    for attempt in range(2):
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": JUDGE_MODEL, "max_tokens": 400,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            data = resp.json()
            if "content" not in data:
                return None
            text = data["content"][0]["text"].strip()
            text = text.replace("```json", "").replace("```", "").strip()
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1:
                text = text[s:e + 1]
            return json.loads(text)
        except Exception:
            if attempt == 0:
                continue
            return None
    return None


def build_card(market, headlines, judgment):
    """허용 필드만 담은 카드를 만든다. 대시보드 렌더러의 화이트리스트와
    같은 집합이라, 여기서 안 넣으면 저기서도 못 그린다(이중 차단)."""
    cleaned, removed = strip_forbidden(judgment)
    card = {
        "market": market,
        "name": market,
        "event_type": cleaned.get("event_type", "기타"),
        "summary": cleaned.get("summary", ""),
        "headlines": headlines,
    }
    return {k: v for k, v in card.items() if k in CARD_FIELDS}, removed


def run(args):
    today = datetime.now().strftime("%Y-%m-%d")
    cards, stripped_total = [], []

    for market in KRX_MARKET_CAP_TOP:
        if len(cards) >= args.max_cards:
            break
        headlines = get_news_headlines(market)
        time.sleep(UNIVERSE_SLEEP)
        if not headlines:
            continue
        judgment = ask_explanation(market, headlines)
        if judgment is None:
            print(f"⚠️ {market}: 설명 생성 실패 - 건너뜀")
            continue
        card, removed = build_card(market, headlines, judgment)
        if removed:
            stripped_total.extend(removed)
            print(f"   ℹ️ {market}: 예측성 필드 제거됨 {removed}")
        cards.append(card)
        print(f"📄 {market} [{card['event_type']}] {card['summary'][:60]}")

    out = {
        "generated_at": today,
        "schema": "explanation_only_v3.2",
        "note": ("사실 설명 전용. 방향 예측/확신도/매매 제안 필드가 스키마에 없다 — "
                 "누락이 아니라 설계(CLAUDE.md v3.2)."),
        "cards": cards,
    }
    save_json(CARDS_FILE, out)
    print(f"\n카드 {len(cards)}건 생성 → {CARDS_FILE}")
    if stripped_total:
        print(f"제거된 예측성 필드 누적: {sorted(set(stripped_total))}")


def main():
    p = argparse.ArgumentParser(description="뉴스 사건 설명 카드 생성 (예측 아님)")
    p.add_argument("--max-cards", type=int, default=MAX_CARDS)
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        run_self_test()
        return
    run(a)


def run_self_test():
    print("=== news_event_cards.py 자체 검증 (네트워크 미사용) ===\n")

    # 1) 프롬프트가 방향/확신도를 요구하지 않는지
    prompt = build_explanation_prompt("005930", ["테스트 헤드라인"])
    for banned in ('"direction"', '"confidence"', "호재 또는 악재", "확신도"):
        assert banned not in prompt, f"프롬프트가 여전히 {banned}를 요구함"
    for must in ("주가 예측이나 매매 판단은 하지 않는다", "사실만", "event_type", "summary"):
        assert must in prompt, f"프롬프트에 '{must}' 없음"
    print("[1] 프롬프트: 방향/확신도 요구 없음, 사실 설명만 요구 확인")

    # 2) 모델이 예측성 필드를 붙여 와도 카드에서 제거되는지 (2차 방어선)
    dirty = {"event_type": "실적발표", "summary": "실적이 발표됐다",
             "direction": "호재", "confidence": 88, "action": "매수"}
    card, removed = build_card("005930", ["h1"], dirty)
    print(f"[2] 오염된 응답 {sorted(dirty)} -> 카드 {sorted(card)} / 제거 {sorted(removed)}")
    assert set(removed) == {"direction", "confidence", "action"}
    for f in FORBIDDEN_FIELDS:
        assert f not in card, f"카드에 금지 필드 {f}가 남음"
    assert set(card) <= set(CARD_FIELDS), "허용 필드 밖의 키가 카드에 있음"

    # 3) 카드 필드 집합이 대시보드 화이트리스트와 일치하는지 (이중 차단의 전제)
    html = open("index.html", encoding="utf-8").read()
    import re
    m = re.search(r"NEWSCARD_FIELDS = \[(.*?)\]", html, re.S)
    dash = {x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()}
    print(f"[3] 생성기 필드={sorted(CARD_FIELDS)} / 대시보드 필드={sorted(dash)}")
    assert dash == set(CARD_FIELDS), "생성기와 대시보드 화이트리스트가 어긋남"

    # 4) 실시간 캘리브레이션 트랙을 건드리지 않는지
    print(f"[4] 출력 파일={CARDS_FILE}")
    assert CARDS_FILE != "news_event_calibration_log.json", "실시간 트랙 파일과 달라야 함"
    # 파일명이 '언급'됐는지가 아니라 실제로 '열거나 저장'하는지를 본다 —
    # 단순 문자열 검색은 이 self-test 자신의 단언문에도 걸린다(실제로 걸렸다).
    src = open("news_event_cards.py", encoding="utf-8").read()
    live = "news_event_calibration_log"
    accessors = [f'open("{live}', f"open('{live}", f'load_json("{live}',
                 f"load_json('{live}", f'save_json("{live}', f"save_json('{live}"]
    hits = [a for a in accessors if a in src]
    print(f"[4] 실시간 트랙 파일 접근 코드: {hits or '없음'}")
    assert not hits, f"실시간 트랙 로그를 읽거나 쓰면 안 됨: {hits}"

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    main()
