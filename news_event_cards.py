"""[v3.2 활성 기능] 뉴스 사건 설명 + 정량 이상행동 카드 생성 (2026-08-03, 2026-08-09 확장).

**예측이 아니다.** "오늘 이 종목에 이런 뉴스/이례적 움직임이 있었다"는 사실 설명만
만든다. 출력 스키마에 `direction`/`confidence`/`action` 같은 필드가 **아예 없다** —
누락이 아니라 설계다. 방향 판단은 §2.1 게이트 미통과로 중단됐다(CLAUDE.md v3.2).

**2026-08-09 방향성 세션 지시로 두 가지가 바뀌었다:**

1. **스코프 축소** — 예전엔 `KRX_MARKET_CAP_TOP`(코스피/코스닥 대형주 전체)를 훑었다.
   지금은 **보유종목(`real_portfolio.json`) + 관심종목(`watchlist.json`, 사람이 수기
   입력)으로만 필터링**한다. 삼성전자·하이닉스 같은 비보유 대형주 헤드라인은 더 이상
   나오지 않는다 — 보유하거나 관심 등록한 종목이 아니면 애초에 조회 대상이 아니다.

2. **이상행동 감시 흡수** — "별도 기능으로 만들지 말라"는 지시에 따라, 정량 이상행동
   (거래량 급변/가격 갭/급등락)을 **같은 카드 스키마**(`CARD_FIELDS`)로 만든다.
   차이는 생성 경로뿐이다: 뉴스 카드는 헤드라인을 Claude에 보내 사실 요약을 받고
   (`ask_explanation`), 이상행동 카드는 **AI를 전혀 거치지 않고** 캔들 데이터를
   산술로만 판정한다(`detect_anomalies`) — `autoexec.py`의 세 규칙과 같은 성격이다.
   `event_type`이 `"이상행동"`이면 이 경로로 만들어진 카드라는 뜻이다.

**기존 파이프라인 재사용**: 헤드라인 수집(`get_news_headlines`)과 사건유형 분류
(실적발표/공시/M&A/규제/지정학/거시/기타)는 Phase 2에서 만든 것을 그대로 쓴다.

**실시간 캘리브레이션 트랙과는 별개다.** `news_event_experiment.py`(→
`news_event_calibration_log.json`)는 방향 판단의 캘리브레이션을 계속 검증하기 위해
**그대로 돈다** — 이 파일은 그 파이프라인을 건드리지 않고, 별도 출력(`CARDS_FILE`)만
만든다.
"""
import argparse
import json
import time
from datetime import datetime, timezone

import requests

from analyze_lib import (
    CLAUDE_API_KEY, FORBIDDEN_FIELDS_BASE, FORBIDDEN_PHRASES_BASE,
    get_krx_candles, get_news_headlines, get_us_candles, load_json, save_json,
)
from news_event_experiment import JUDGE_MODEL

CARDS_FILE = "news_event_cards.json"
REAL_PORTFOLIO_FILE = "real_portfolio.json"
WATCHLIST_FILE = "watchlist.json"
UNIVERSE_SLEEP = 0.2
MAX_CARDS = 8  # 대시보드에 한 화면 분량만 — 전 종목을 나열하면 읽히지 않는다

# 카드에 실릴 수 있는 필드. 이 목록 밖의 키는 build_card/build_anomaly_card가 버린다.
# 대시보드(index.html)의 NEWSCARD_FIELDS와 같은 집합이어야 한다.
CARD_FIELDS = ("market", "name", "event_type", "summary", "headlines")

# 이 필드들이 모델 응답에 섞여 나오면 카드에서 제거한다. 프롬프트에서 요구하지
# 않지만 모델이 습관적으로 붙일 수 있고, 하나라도 새어나가면 "예측 아님"이라는
# 이 카드의 전제가 깨진다. 이상행동 카드는 AI를 안 거치므로 이 목록과 무관하다.
# analyze_lib.FORBIDDEN_FIELDS_BASE에 이 카드 고유 필드("호재"/"악재"/"판단")만 더한다.
FORBIDDEN_FIELDS = FORBIDDEN_FIELDS_BASE + ("호재", "악재", "판단")

# 2026-08-10: summary "문구" 자체는 지금까지 검사한 적이 없었다 — 프롬프트가
# "전망/기대감/수혜/호재·악재/매수·매도/목표가 같은 표현을 쓰지 마라"고 요청은
# 하지만 아무것도 런타임에서 강제하지 않았고, 실제로 모델이 "목표주가를 상향
# 조정했다"처럼 프롬프트가 막으려던 표현의 동의어를 써서 그대로 커밋된 사례가
# post_trade_review.py 개발 중 발견됐다(§5 "최근 뉴스 연결"이 이 파일의 summary를
# 그대로 인용하다가 자체 감사에 걸림). analyze_lib.FORBIDDEN_PHRASES_BASE에
# rule_trigger_report.py와 같은 추가 항목("매수"/"보입니다")을 더해 재사용한다.
FORBIDDEN_PHRASES = FORBIDDEN_PHRASES_BASE + ("매수", "보입니다")

# 이상행동 판정 임계값. 방향성 세션 지시로 신설 — 결과를 보고 사후에 맞추지 않는다
# (autoexec.py의 규칙 파라미터, portfolio_report.py의 THRESHOLDS와 같은 원칙).
# 초기값이며 튜닝 대상이다.
VOLUME_SPIKE_MULTIPLE = 2.0    # 거래량이 20일 평균의 이 배수 이상이면 발동
PRICE_GAP_PCT = 3.0            # 전일 종가 대비 시가 갭이 이 %(절대값) 이상이면 발동
VOLATILITY_MULTIPLE = 2.0      # 당일 등락폭이 최근 20일 변동성의 이 배수 이상이면 발동
ANOMALY_WINDOW = 20            # 거래량 평균/변동성 계산에 쓰는 과거 거래일수


# ── 대상 종목 선정 (2026-08-09 스코프 축소) ─────────────────────────────────

def build_universe():
    """보유종목 + 관심종목만 대상으로 한다. 시장 전체 스캔은 하지 않는다.

    반환: [{"symbol": ..., "name": ..., "market_country": "KR"|"US"|None}, ...]
    (market_country는 real_portfolio.json에 있으면 채우고, 관심종목 전용 심볼은
    None — 캔들 조회 시 심볼 형태로 KR/US를 추정한다, _is_krx_symbol 참고)"""
    real = load_json(REAL_PORTFOLIO_FILE, {"positions": []})
    watchlist = load_json(WATCHLIST_FILE, {"symbols": []})

    universe, seen = [], set()
    for p in real.get("positions", []):
        sym = p.get("symbol")
        if not sym or sym in seen:
            continue
        seen.add(sym)
        universe.append({"symbol": sym, "name": p.get("name", sym),
                         "market_country": p.get("market_country")})

    for sym in watchlist.get("symbols", []):
        if not sym or sym in seen:
            continue
        seen.add(sym)
        universe.append({"symbol": sym, "name": sym, "market_country": None})

    return universe


def _is_krx_symbol(symbol):
    """종목코드 형태로 KR/US 추정 — KRX는 6자리 숫자, 그 외는 해외 티커로 취급."""
    return symbol.isdigit() and len(symbol) == 6


# ── 이상행동 감시 (결정론적 산술, AI 미개입) ────────────────────────────────

def fetch_candles_for_anomaly(symbol, market_country=None, count=None):
    """KR/US 판별 후 캔들 조회. 실패해도 예외를 올리지 않고 None — 이상행동
    점검을 건너뛸 뿐 카드 생성 전체를 막지 않는다(뉴스 카드와 같은 관용)."""
    count = count or (ANOMALY_WINDOW + 5)
    is_kr = market_country == "KR" or (market_country is None and _is_krx_symbol(symbol))
    try:
        if is_kr:
            return get_krx_candles(symbol, count=count)
        return get_us_candles(symbol, count=count)
    except Exception as e:
        print(f"⚠️ {symbol}: 시세 조회 실패 - 이상행동 점검 생략 ({e})")
        return None


def detect_anomalies(candles):
    """순수 산술 판정 — autoexec.py의 세 규칙과 같은 성격이다. AI가 개입하지
    않으므로 §2.1 통계 게이트 적용 대상이 아니다(CLAUDE.md v3.2 (a) 원칙).

    candles: 과거->현재 순서의 OHLCV 딕셔너리 리스트(get_krx_candles/get_us_candles
    형식 — open/high/low/close/volume 키). 반환: 발동한 사실 문장 리스트(빈 리스트면
    이상행동 없음). "위험"/"매도 검토" 같은 판단 문구는 절대 넣지 않는다 — 관측 수치와
    배수만 서술한다."""
    facts = []
    if not candles or len(candles) < ANOMALY_WINDOW + 2:
        return facts

    today, prev = candles[-1], candles[-2]
    window = candles[-(ANOMALY_WINDOW + 1):-1]  # 오늘을 제외한 최근 ANOMALY_WINDOW일

    # 1) 거래량 급변 — 20일 평균 대비 배수
    vols = [c.get("volume", 0) or 0 for c in window]
    avg_vol = sum(vols) / len(vols) if vols else 0
    today_vol = today.get("volume", 0) or 0
    if avg_vol > 0:
        vol_mult = today_vol / avg_vol
        if vol_mult >= VOLUME_SPIKE_MULTIPLE:
            facts.append(f"거래량 20일 평균 대비 {vol_mult:.1f}배")

    # 2) 가격 갭 — 전일 종가 대비 당일 시가
    prev_close, today_open = prev.get("close"), today.get("open")
    if prev_close:
        gap_pct = (today_open - prev_close) / prev_close * 100
        if abs(gap_pct) >= PRICE_GAP_PCT:
            facts.append(f"전일 종가 대비 시가 갭 {gap_pct:+.1f}%")

    # 3) 급등락 — 당일 등락폭을 최근 20일 변동성과 비교한 배수
    closes = [c["close"] for c in window]
    rets = [(closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes)) if closes[i - 1]]
    if len(rets) >= 5 and prev_close:
        mean_r = sum(rets) / len(rets)
        std_r = (sum((r - mean_r) ** 2 for r in rets) / len(rets)) ** 0.5
        today_ret_pct = (today.get("close", prev_close) - prev_close) / prev_close * 100
        if std_r > 0:
            move_mult = abs(today_ret_pct / 100) / std_r
            if move_mult >= VOLATILITY_MULTIPLE:
                facts.append(f"당일 {today_ret_pct:+.1f}% (최근 20일 변동성 대비 {move_mult:.1f}배)")

    return facts


def build_anomaly_card(symbol, name, facts):
    """이상행동 사실을 뉴스 카드와 같은 스키마로 담는다. headlines는 뉴스가 아니므로
    빈 리스트 — 대시보드 렌더러는 headlines가 비어 있어도 정상 동작한다."""
    return {"market": symbol, "name": name, "event_type": "이상행동",
            "summary": ", ".join(facts), "headlines": []}


# ── 뉴스 사건 설명 카드 (기존 로직, 변경 없음) ──────────────────────────────

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
    for attempt in range(2):  # 실패하면 한 번 더 시도
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


def scrub_summary_phrases(summary):
    """summary 문자열에 금지 문구가 있으면 통째로 안전한 자리표시자로 바꾼다.
    문구만 잘라내면 남은 문장이 어색하게 이어 붙거나 의미가 왜곡될 수 있어서
    (예: "...목표주가를 상향 조정했다" 중 "목표주가"만 지우면 비문이 됨),
    부분 편집 대신 전체 교체를 택한다 — 틀린 요약보다 빈 요약이 낫다는 이
    저장소의 기존 원칙(PER "데이터 소스 미연결" 등)과 같다.
    반환: (정제된 summary, 감지된 문구) — 후자가 None이면 위반 없음."""
    for ph in FORBIDDEN_PHRASES:
        if ph in summary:
            return "[요약 생략 - 금지 문구 감지로 검수 실패]", ph
    return summary, None


def build_card(market, name, headlines, judgment):
    """허용 필드만 담은 카드를 만든다. 대시보드 렌더러의 화이트리스트와
    같은 집합이라, 여기서 안 넣으면 저기서도 못 그린다(이중 차단)."""
    cleaned, removed = strip_forbidden(judgment)
    summary, hit_phrase = scrub_summary_phrases(cleaned.get("summary", ""))
    if hit_phrase:
        removed = removed + [f"summary:'{hit_phrase}'"]
    card = {
        "market": market,
        "name": name,
        "event_type": cleaned.get("event_type", "기타"),
        "summary": summary,
        "headlines": headlines,
    }
    return {k: v for k, v in card.items() if k in CARD_FIELDS}, removed


# ── 실행 ─────────────────────────────────────────────────────────────────

def run(args):
    # 2026-08-10 방향성 세션 지시: 대시보드 기준시점 불일치 최소 조치 — 날짜만으론
    # 이 파일의 갱신 주기(1일 1회)를 다른 패널과 비교할 수 없다. 시:분까지 담는다
    # (real_portfolio.json의 synced_at과 같은 ISO+UTC 패턴).
    generated_at = datetime.now(timezone.utc).isoformat()
    cards, stripped_total = [], []
    universe = build_universe()
    print(f"대상 종목(보유+관심) {len(universe)}건: {[u['symbol'] for u in universe]}")

    for u in universe:
        symbol, name = u["symbol"], u["name"]
        if len(cards) >= args.max_cards:
            break

        # 이상행동 감시 — 결정론적 산술, AI 미개입. 뉴스보다 먼저 확인한다.
        candles = fetch_candles_for_anomaly(symbol, u["market_country"])
        anomaly_facts = detect_anomalies(candles) if candles else []
        if anomaly_facts:
            cards.append(build_anomaly_card(symbol, name, anomaly_facts))
            print(f"📊 {symbol} [이상행동] {', '.join(anomaly_facts)}")
            if len(cards) >= args.max_cards:
                break

        # 뉴스 사건 설명 카드 (기존 로직)
        headlines = get_news_headlines(symbol)
        time.sleep(UNIVERSE_SLEEP)
        if not headlines:
            continue
        judgment = ask_explanation(symbol, headlines)
        if judgment is None:
            print(f"⚠️ {symbol}: 설명 생성 실패 - 건너뜀")
            continue
        card, removed = build_card(symbol, name, headlines, judgment)
        if removed:
            stripped_total.extend(removed)
            print(f"   ℹ️ {symbol}: 예측성 필드 제거됨 {removed}")
        cards.append(card)
        print(f"📄 {symbol} [{card['event_type']}] {card['summary'][:60]}")

    out = {
        "generated_at": generated_at,
        "schema": "explanation_only_v3.2",
        "note": ("사실 설명 전용(뉴스 사건 + 정량 이상행동). 방향 예측/확신도/매매 제안 "
                 "필드가 스키마에 없다 - 누락이 아니라 설계(CLAUDE.md v3.2). 대상은 "
                 "보유종목+관심종목으로 한정(2026-08-09 스코프 축소)."),
        "cards": cards,
    }
    save_json(CARDS_FILE, out)
    print(f"\n카드 {len(cards)}건 생성 → {CARDS_FILE}")
    if stripped_total:
        print(f"제거된 예측성 필드 누적: {sorted(set(stripped_total))}")


def main():
    p = argparse.ArgumentParser(description="뉴스 사건 설명 + 이상행동 카드 생성 (예측 아님)")
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
    card, removed = build_card("005930", "삼성전자", ["h1"], dirty)
    print(f"[2] 오염된 응답 {sorted(dirty)} -> 카드 {sorted(card)} / 제거 {sorted(removed)}")
    assert set(removed) == {"direction", "confidence", "action"}
    for f in FORBIDDEN_FIELDS:
        assert f not in card, f"카드에 금지 필드 {f}가 남음"
    assert set(card) <= set(CARD_FIELDS), "허용 필드 밖의 키가 카드에 있음"

    # 2b) [2026-08-10] summary "문구" 자체도 검사하는지 — 필드 제거와 별개로,
    # post_trade_review.py 개발 중 실제로 "목표주가를 상향 조정했다"가 커밋된
    # 카드에 남아 있던 걸 발견해 추가한 방어선.
    dirty_phrase = {"event_type": "공시", "summary": "회사가 목표주가를 상향 조정했다"}
    card2, removed2 = build_card("005930", "삼성전자", ["h1"], dirty_phrase)
    print(f"[2b] 금지 문구 포함 summary -> {card2['summary']!r} / 제거 {removed2}")
    assert card2["summary"] == "[요약 생략 - 금지 문구 감지로 검수 실패]"
    assert any("목표주가" in r for r in removed2)
    for ph in FORBIDDEN_PHRASES:
        assert ph not in card2["summary"], f"교체된 summary에도 금지 문구 '{ph}'가 남음"
    clean_phrase = {"event_type": "공시", "summary": "회사가 자사주 매입 계획을 발표했다"}
    card3, removed3 = build_card("005930", "삼성전자", ["h1"], clean_phrase)
    assert card3["summary"] == clean_phrase["summary"], "정상 문구까지 지워지면 안 됨"
    assert not any("summary:" in r for r in removed3)
    print("[2b] 정상 summary는 그대로 유지되는지 확인")

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
    src = open("news_event_cards.py", encoding="utf-8").read()
    live = "news_event_calibration_log"
    accessors = [f'open("{live}', f"open('{live}", f'load_json("{live}',
                 f"load_json('{live}", f'save_json("{live}', f"save_json('{live}"]
    hits = [a for a in accessors if a in src]
    print(f"[4] 실시간 트랙 파일 접근 코드: {hits or '없음'}")
    assert not hits, f"실시간 트랙 로그를 읽거나 쓰면 안 됨: {hits}"

    # 5) [2026-08-09] 대상 종목이 보유+관심으로만 좁혀지는지 (시장 전체 스캔 아님)
    # self-test가 __main__으로 실행되므로 "news_event_cards.load_json" 문자열로
    # patch하면 별도 모듈 인스턴스가 다시 임포트돼 실제로 쓰이는 이름을 패치하지
    # 못한다(autoexec.py self-test에서 이미 겪은 함정) - 현재 모듈 객체를 직접 쓴다.
    import sys
    import unittest.mock as mock
    mod = sys.modules[__name__]
    fake_real = {"positions": [{"symbol": "005930", "name": "삼성전자", "market_country": "KR"},
                               {"symbol": "NVDA", "name": "엔비디아", "market_country": "US"}]}
    fake_watch = {"symbols": ["000660", "005930"]}  # 005930은 보유와 중복 - dedup 확인용
    with mock.patch.object(mod, "load_json", side_effect=lambda path, default:
                            fake_real if path == REAL_PORTFOLIO_FILE else
                            fake_watch if path == WATCHLIST_FILE else default):
        universe = build_universe()
    syms = [u["symbol"] for u in universe]
    print(f"[5] 대상 종목: {syms}")
    assert syms == ["005930", "NVDA", "000660"], f"보유+관심 합집합(중복제거)이어야 함: {syms}"
    # 식별자 자체가 아니라 "임포트해서 쓰는지"만 본다 - 위 docstring이 변경 이력을
    # 설명하려고 그 이름을 언급하는 것까지 걸리면(원본 self-test가 실제로 겪은 함정)
    # 문서화를 못 하게 되므로, import 구문 존재 여부로만 판정한다. 검사 문자열도
    # 조각내서 만든다 - 안 그러면 이 줄 자신의 소스 텍스트가 스스로 걸린다.
    banned_import = "from " + "backtest import"
    assert banned_import not in open("news_event_cards.py", encoding="utf-8").read(), \
        "시장 전체 유니버스(backtest.py) 임포트가 남아 있으면 안 됨"

    # 6) [2026-08-09] 이상행동 판정 — 순수 산술, 임계값 초과 시에만 발동
    def make_candles(n, base_price=10000, base_vol=1000):
        return [{"open": base_price, "high": base_price * 1.01, "low": base_price * 0.99,
                 "close": base_price, "volume": base_vol} for _ in range(n)]

    normal = make_candles(25)
    assert detect_anomalies(normal) == [], "평상시 데이터에서 이상행동이 발동하면 안 됨"
    print("[6] 평상시 데이터 -> 이상행동 0건 확인")

    spike = make_candles(25)
    spike[-1] = dict(spike[-1], volume=spike[-2]["volume"] * 5)
    facts = detect_anomalies(spike)
    print(f"[6] 거래량 5배 주입 -> {facts}")
    assert any("거래량" in f for f in facts), "거래량 급변이 감지되지 않음"

    gap = make_candles(25)
    gap[-1] = dict(gap[-1], open=gap[-2]["close"] * 1.05)  # 전일 종가 대비 +5% 갭
    facts_gap = detect_anomalies(gap)
    print(f"[6] +5% 갭 주입 -> {facts_gap}")
    assert any("갭" in f for f in facts_gap), "가격 갭이 감지되지 않음"

    # 7) 이상행동 카드도 뉴스 카드와 같은 스키마/금지어 규율을 따르는지
    acard = build_anomaly_card("005930", "삼성전자", ["거래량 20일 평균 대비 3.2배", "당일 -8.1%"])
    print(f"[7] 이상행동 카드: {acard}")
    assert set(acard) <= set(CARD_FIELDS)
    assert acard["event_type"] == "이상행동"
    for banned in ("위험", "매도", "매수", "검토", "추천"):
        assert banned not in acard["summary"], f"이상행동 요약에 판단 문구 '{banned}' 있음"

    # 8) 데이터가 짧으면(20일 미만) 조용히 빈 리스트 (오탐 방지)
    short = make_candles(10)
    assert detect_anomalies(short) == [], "데이터 부족 시 이상행동을 발동하면 안 됨"
    print("[8] 데이터 부족(10일) -> 이상행동 0건 확인")

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    main()
