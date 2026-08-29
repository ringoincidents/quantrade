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
    build_common_event, get_krx_candles, get_news_headlines, get_us_candles,
    historical_percentile, load_json, rolling_volatility_series, save_json,
    validate_common_event,
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
ANOMALY_WINDOW = 20            # 거래량 평균/변동성 계산에 쓰는 과거 거래일수

# 2026-08-29 A2 Step 2(PM 지시, A2_Intelligence_Layer_Design.md §2-3): 변동성
# 급증 판정을 market_indicators.py와 같은 "백분위" 방식으로 통일했다. 예전
# VOLATILITY_MULTIPLE(당일 등락폭이 최근 20일 변동성의 N배)은 폐기 — 같은
# 이름의 다른 계산식이 서로 다른 파일에 있던 상태를 없앤 것이다. 값 90은
# 설계 문서 §2-2 제안 그대로(사전 등록, 결과를 보고 맞추지 않음) — 초기값이며
# 튜닝 대상이다.
VOLATILITY_PERCENTILE_THRESHOLD = 90
# 백분위 계산은 과거 분포 표본이 충분해야 의미가 있다 - market_indicators.py의
# STATE_LOOKBACK_CANDLES와 같은 값(300)을 써서 같은 방식을 그대로 재현한다.
# 값을 공유 상수로 묶지 않고 각자 정의한 이유: "계산 방식(함수)"을 공유하는 게
# 이번 통일의 핵심이고, 조회 개수는 각 파일이 자기 호출부 사정에 맞춰 정할 수
# 있게 남겨둔다(우연히 지금은 같은 숫자일 뿐).
ANOMALY_VOL_LOOKBACK_CANDLES = 300


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


def build_event_asset(symbol, name, market_country):
    """공통 스키마(§1-1)의 asset 객체를 만든다 — {symbol, name, market_country,
    currency}. currency는 이 파일에 별도 데이터 소스가 없어 시장국가로부터
    추정한다 — fetch_candles_for_anomaly가 KR/US를 판별하는 것과 정확히 같은
    이분법(심볼이 KRX 6자리 숫자면 KR, 아니면 US)을 재사용해 "이 캔들이 어느
    시장 걸로 조회됐는지"와 "이 이벤트의 통화가 뭔지"가 항상 일치하게 한다."""
    is_kr = market_country == "KR" or (market_country is None and _is_krx_symbol(symbol))
    currency = "KRW" if is_kr else "USD"
    return {"symbol": symbol, "name": name, "market_country": market_country,
            "currency": currency}


# ── 이상행동 감시 (결정론적 산술, AI 미개입) ────────────────────────────────

def fetch_candles_for_anomaly(symbol, market_country=None, count=None):
    """KR/US 판별 후 캔들 조회. 실패해도 예외를 올리지 않고 None — 이상행동
    점검을 건너뛸 뿐 카드 생성 전체를 막지 않는다(뉴스 카드와 같은 관용).

    2026-08-29: 기본 조회 개수를 ANOMALY_WINDOW+5(25)에서
    ANOMALY_VOL_LOOKBACK_CANDLES(300)로 늘렸다 — 변동성 백분위 판정(A2 Step 2)이
    과거 분포 표본을 필요로 하기 때문. 거래량/가격갭 판정은 어차피 캔들 끝부분만
    보므로 표본이 늘어도 영향 없다."""
    count = count or ANOMALY_VOL_LOOKBACK_CANDLES
    is_kr = market_country == "KR" or (market_country is None and _is_krx_symbol(symbol))
    try:
        if is_kr:
            return get_krx_candles(symbol, count=count)
        return get_us_candles(symbol, count=count)
    except Exception as e:
        print(f"⚠️ {symbol}: 시세 조회 실패 - 이상행동 점검 생략 ({e})")
        return None


def _candle_timestamp(candle):
    """캔들의 거래일을 이벤트 timestamp로 쓴다(A2 설계 §1-4) — 일봉 데이터라
    시:분 정보가 없으므로 자정 UTC로 채운다. 스크립트 실행 시각("지금")이
    아니라 실제 관측(거래) 시각을 쓰는 게 §1-4의 취지에 맞다. candle에 date가
    없으면(방어적) 실행 시각으로 폴백한다."""
    date = candle.get("date")
    if date:
        return f"{date}T00:00:00+00:00"
    return datetime.now(timezone.utc).isoformat()


def detect_anomalies(candles, asset=None):
    """순수 산술 판정 — autoexec.py의 세 규칙과 같은 성격이다. AI가 개입하지
    않으므로 §2.1 통계 게이트 적용 대상이 아니다(CLAUDE.md v3.2 (a) 원칙).

    candles: 과거->현재 순서의 OHLCV 딕셔너리 리스트(get_krx_candles/get_us_candles
    형식 — open/high/low/close/volume/date 키).
    asset: {symbol, name, market_country, currency} 형태로 주어지면(A2 Step 2)
    공통 스키마(9필드) change_events도 함께 만든다 — build_common_event()가
    생성 시점에 스키마를 검증하므로 여기서 만들어지는 이벤트는 이미 사전
    검증을 통과한 것이다. asset이 None이면(기존 호출부와의 하위 호환)
    change_events는 항상 빈 리스트 — facts만 쓰던 기존 동작 그대로.

    반환: (facts, change_events) 튜플.
      - facts: 발동한 사실 문장 리스트(기존 그대로 — build_anomaly_card가
        표시용으로 그대로 쓴다). "위험"/"매도 검토" 같은 판단 문구는 절대
        넣지 않는다 — 관측 수치와 배수/백분위만 서술한다.
      - change_events: 같은 계산에서 같이 나오는 공통 스키마 이벤트 목록
        (A2_Intelligence_Layer_Design.md §2-1 "문장 생성을 없애는 게 아니라
        문장 뒤에 숫자를 남긴다" 그대로 — 계산을 두 번 하지 않는다).

    2026-08-29 A2 Step 2: 변동성 급증 판정을 market_indicators.py와 같은
    "백분위" 방식으로 통일했다(PM 지시) — 예전 VOLATILITY_MULTIPLE(당일
    등락폭이 최근 20일 변동성의 N배)은 폐기, rolling_volatility_series/
    historical_percentile(analyze_lib.py로 이전, market_indicators.py와 공유)를
    재사용해 "최근 20일 변동성이 과거 분포에서 몇 백분위인가"로 판정한다.
    사실 문장의 표현도 "배수"에서 "백분위"로 바뀌었다."""
    facts = []
    change_events = []
    if not candles or len(candles) < ANOMALY_WINDOW + 2:
        return facts, change_events

    today, prev = candles[-1], candles[-2]
    window = candles[-(ANOMALY_WINDOW + 1):-1]  # 오늘을 제외한 최근 ANOMALY_WINDOW일
    event_ts = _candle_timestamp(today)

    def emit(event_type, observed_value, baseline, change):
        if asset is None:
            return
        change_events.append(build_common_event(
            timestamp=event_ts, asset=asset, source="news_event_cards.anomaly",
            event_type=event_type, reliability=1.0,  # 산술 판정 - §3-1 "산술 기반은 1.0"
            observed_value=observed_value, baseline=baseline, change=change,
        ))

    # 1) 거래량 급변 — 20일 평균 대비 배수
    vols = [c.get("volume", 0) or 0 for c in window]
    avg_vol = sum(vols) / len(vols) if vols else 0
    today_vol = today.get("volume", 0) or 0
    if avg_vol > 0:
        vol_mult = today_vol / avg_vol
        if vol_mult >= VOLUME_SPIKE_MULTIPLE:
            facts.append(f"거래량 20일 평균 대비 {vol_mult:.1f}배")
            emit("거래량_급증", today_vol, avg_vol, round(vol_mult, 2))

    # 2) 가격 갭 — 전일 종가 대비 당일 시가
    prev_close, today_open = prev.get("close"), today.get("open")
    if prev_close:
        gap_pct = (today_open - prev_close) / prev_close * 100
        if abs(gap_pct) >= PRICE_GAP_PCT:
            facts.append(f"전일 종가 대비 시가 갭 {gap_pct:+.1f}%")
            emit("가격_갭", today_open, prev_close, round(gap_pct, 2))

    # 3) 변동성 급증 — 최근 ANOMALY_WINDOW일 변동성의 과거 분포 내 백분위
    #    (market_indicators.py와 동일 방식). 표본(vol_series)이 너무 적으면
    #    백분위가 의미 없어 조용히 건너뛴다 — 데이터 부족 시 발동 안 하는
    #    기존 관용 그대로.
    all_closes = [c["close"] for c in candles]
    vol_series = rolling_volatility_series(all_closes, ANOMALY_WINDOW)
    vol_percentile = historical_percentile(vol_series) if len(vol_series) >= 20 else None
    if vol_percentile is not None and vol_percentile >= VOLATILITY_PERCENTILE_THRESHOLD:
        vol_pct_today = round(vol_series[-1] * 100, 2)
        facts.append(f"최근 20일 변동성이 과거 분포 대비 {vol_percentile:.0f}백분위")
        # baseline: 백분위 자체가 이미 과거 분포 대비 위치라 baseline 값 자체는
        # 없음(§2-2) - 스키마상 null 허용. change에는 배율 대신 백분위를 재사용.
        emit("변동성_급증", vol_pct_today, None, vol_percentile)

    return facts, change_events


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
                # 2026-08-28: 키 순 형태 원문은 절대 로그에 남기지 않는다 —
                # 상태 코드/에러 본문만 남겨서 인증 실패인지 다른 원인인지
                # 구분할 수 있게 한다(git history 노출 대응 키 재발급 검증 중
                # 이 분기가 아무 단서 없이 조용히 None을 반환해 원인 파악이
                # 막혔던 사례가 있었다).
                print(f"⚠️ {market}: Claude API 응답에 content 없음 "
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
            print(f"⚠️ {market}: Claude API 호출 예외 ({type(e).__name__}: {e})")
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
    cards, stripped_total, change_events = [], [], []
    universe = build_universe()
    print(f"대상 종목(보유+관심) {len(universe)}건: {[u['symbol'] for u in universe]}")

    for u in universe:
        symbol, name = u["symbol"], u["name"]
        if len(cards) >= args.max_cards:
            break

        # 이상행동 감시 — 결정론적 산술, AI 미개입. 뉴스보다 먼저 확인한다.
        # 2026-08-29 A2 Step 2: asset을 넘겨 change_events도 같이 받는다(공통
        # 스키마, build_common_event가 생성 시점에 사전 검증) — facts는 기존
        # 그대로 카드 표시용.
        candles = fetch_candles_for_anomaly(symbol, u["market_country"])
        asset = build_event_asset(symbol, name, u["market_country"])
        anomaly_facts, anomaly_events = detect_anomalies(candles, asset=asset) if candles else ([], [])
        change_events.extend(anomaly_events)
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
        # 2026-08-29 A2 Step 2 신설: 이상행동 카드와 같은 계산에서 나온 공통
        # 스키마(9필드) 이벤트 목록(A2_Intelligence_Layer_Design.md §1-4 예시
        # 그대로 - 최상위 generated_at/schema는 그대로 두고 그 아래 별도
        # 배열로 추가). cards의 "이상행동" 카드는 표시용 문장이고, 이건 Step
        # 3(Prioritization)/Step 4(Portfolio Relevance)가 소비할 구조화 데이터.
        # 뉴스 사건 설명 카드(AI 판단 경로)는 이번 Step 2 범위가 아니라 아직
        # change_events를 만들지 않는다.
        "change_events": change_events,
    }
    save_json(CARDS_FILE, out)
    print(f"\n카드 {len(cards)}건 생성 → {CARDS_FILE} (change_events {len(change_events)}건)")
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

    # 6) [2026-08-09, 2026-08-29 A2 Step 2] 이상행동 판정 — 순수 산술, 임계값
    #    초과 시에만 발동. detect_anomalies가 이제 (facts, change_events) 튜플을
    #    반환한다 - asset을 안 주면(하위 호환 경로) change_events는 항상 빈 리스트.
    def make_candles(n, base_price=10000, base_vol=1000, start="2026-01-01"):
        from datetime import date, timedelta
        d0 = date.fromisoformat(start)
        return [{"date": (d0 + timedelta(days=i)).isoformat(),
                 "open": base_price, "high": base_price * 1.01, "low": base_price * 0.99,
                 "close": base_price, "volume": base_vol} for i in range(n)]

    test_asset = build_event_asset("005930", "삼성전자", "KR")

    normal = make_candles(25)
    facts0, events0 = detect_anomalies(normal, asset=test_asset)
    print(f"[6] 평상시 데이터 -> facts={facts0}, change_events={len(events0)}건")
    assert facts0 == [] and events0 == [], "평상시 데이터에서 이상행동이 발동하면 안 됨"

    spike = make_candles(25)
    spike[-1] = dict(spike[-1], volume=spike[-2]["volume"] * 5)
    facts_novol, events_noasset = detect_anomalies(spike)  # asset 없음 - 하위 호환 경로
    print(f"[6] 거래량 5배 주입(asset 없음) -> facts={facts_novol}, change_events={events_noasset}")
    assert any("거래량" in f for f in facts_novol), "거래량 급변이 감지되지 않음"
    assert events_noasset == [], "asset을 안 줬는데 change_events가 생기면 안 됨(하위 호환)"

    facts_vol, events_vol = detect_anomalies(spike, asset=test_asset)
    print(f"[6] 거래량 5배 주입(asset 있음) -> change_events={events_vol}")
    assert len(events_vol) == 1 and events_vol[0]["event_type"] == "거래량_급증"
    assert validate_common_event(events_vol[0]) == [], "거래량_급증 이벤트가 스키마 사전 검증을 통과 못 함"

    gap = make_candles(25)
    gap[-1] = dict(gap[-1], open=gap[-2]["close"] * 1.05)  # 전일 종가 대비 +5% 갭
    facts_gap, events_gap = detect_anomalies(gap, asset=test_asset)
    print(f"[6] +5% 갭 주입 -> facts={facts_gap}, change_events={events_gap}")
    assert any("갭" in f for f in facts_gap), "가격 갭이 감지되지 않음"
    assert any(e["event_type"] == "가격_갭" for e in events_gap)
    assert all(validate_common_event(e) == [] for e in events_gap)

    # 6b) [2026-08-29 A2 Step 2] 변동성 급증 — market_indicators.py와 같은 백분위
    #    방식(PM 지시로 VOLATILITY_MULTIPLE 배율 방식을 대체). 진폭이 갈수록
    #    커지는 합성 시계열이면 마지막 구간의 변동성이 과거 분포 최상단에
    #    있어야 한다(market_indicators.py self-test와 같은 구성).
    import math
    vol_closes = [10000.0]
    for i in range(1, 340):
        amp = 0.001 + (i / 340) * 0.08
        vol_closes.append(vol_closes[-1] * (1 + amp * math.sin(i)))
    from datetime import date, timedelta
    d0 = date.fromisoformat("2025-01-01")
    vol_candles = [{"date": (d0 + timedelta(days=i)).isoformat(),
                     "open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1000}
                    for i, c in enumerate(vol_closes)]
    facts_pctl, events_pctl = detect_anomalies(vol_candles, asset=test_asset)
    print(f"[6b] 증가 변동성 합성 데이터 -> facts={facts_pctl}")
    assert any("백분위" in f for f in facts_pctl), "변동성 급증(백분위 방식)이 감지되지 않음"
    assert any(e["event_type"] == "변동성_급증" for e in events_pctl)
    vol_event = next(e for e in events_pctl if e["event_type"] == "변동성_급증")
    print(f"[6b] 변동성_급증 이벤트: observed_value={vol_event['observed_value']}, "
          f"baseline={vol_event['baseline']}, change(백분위)={vol_event['change']}")
    assert vol_event["baseline"] is None, "백분위 방식은 baseline이 없어야 함(§2-2)"
    assert vol_event["change"] >= VOLATILITY_PERCENTILE_THRESHOLD
    assert validate_common_event(vol_event) == []
    # 소스 텍스트 검색이 아니라 모듈 네임스페이스에 그 이름이 더 이상 정의돼
    # 있지 않은지를 본다 - 텍스트 검색이면 이 설명 주석/docstring 자체가 그
    # 이름을 언급하는 것까지 걸린다(다른 self-test가 겪은 자기지시적 함정과
    # 같은 종류). 폐기 여부의 진짜 기준은 "코드에 그 식별자가 정의돼 있는가"다.
    import sys
    mod = sys.modules[__name__]
    assert not hasattr(mod, "VOLATILITY_MULTIPLE"), \
        "폐기된 변동성 배율 상수가 모듈에 여전히 정의돼 있으면 안 됨(백분위 방식으로 대체, §2-3)"

    # 7) 이상행동 카드도 뉴스 카드와 같은 스키마/금지어 규율을 따르는지
    acard = build_anomaly_card("005930", "삼성전자", ["거래량 20일 평균 대비 3.2배", "당일 -8.1%"])
    print(f"[7] 이상행동 카드: {acard}")
    assert set(acard) <= set(CARD_FIELDS)
    assert acard["event_type"] == "이상행동"
    for banned in ("위험", "매도", "매수", "검토", "추천"):
        assert banned not in acard["summary"], f"이상행동 요약에 판단 문구 '{banned}' 있음"

    # 8) 데이터가 짧으면(20일 미만) 조용히 빈 리스트 (오탐 방지)
    short = make_candles(10)
    facts_short, events_short = detect_anomalies(short, asset=test_asset)
    assert facts_short == [] and events_short == [], "데이터 부족 시 이상행동을 발동하면 안 됨"
    print("[8] 데이터 부족(10일) -> 이상행동 0건 확인")

    # 9) build_event_asset — KR/US currency 추정이 fetch_candles_for_anomaly와
    #    같은 이분법을 쓰는지
    asset_kr = build_event_asset("005930", "삼성전자", "KR")
    asset_us_guess = build_event_asset("NVDA", "엔비디아", None)  # market_country 없음, 심볼로 US 추정
    print(f"[9] KR asset={asset_kr}, market_country 없는 비KRX심볼 asset={asset_us_guess}")
    assert asset_kr["currency"] == "KRW"
    assert asset_us_guess["currency"] == "USD"

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    main()
