import requests
import math
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

EXCLUDE_MARKETS = {"KRW-USDT", "KRW-USDC", "KRW-USDE", "KRW-USDS", "KRW-DAI"}
US_STOCKS = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]
POSITIVE_WORDS = ["surge", "rally", "gain", "bullish", "record", "growth", "beat", "strong"]
NEGATIVE_WORDS = ["crash", "plunge", "bearish", "loss", "fall", "concern", "risk", "weak", "drop"]
HARD_STOP_LOSS = {"단타": -5, "스윙": -10, "장기": -25}

# 포지션 사이징(2026-08-01 설계 확정). 라이브(analyze.py의 needs_approval)와
# 백테스트(backtest.py의 MDD 재계산)가 같은 숫자를 쓰도록 여기 한 곳에만 둔다.
# - AUTO_TIER_WEIGHT 미만: 자동 실행
# - AUTO_TIER_WEIGHT 이상: 사람 승인 필요
# - POSITION_WEIGHT_HARD_CAP 초과: 승인해도 차단(하드 상한, 매수 금액을 이 비중으로 clamp)
# 기존 LARGE_POSITION_THRESHOLD(0.25, 승인만 필요·상한 없음)를 대체 — 백테스트 gate가
# 명확히 미통과한 상태에서 자산 대부분을 검증 안 된 판단에 거는 걸 막기 위해 강화했다.
AUTO_TIER_WEIGHT = 0.10
POSITION_WEIGHT_HARD_CAP = 0.20

# 종합계획서 v3 §2 "거래비용/슬리피지가 백테스트 계산에서 빠져 있음" 대응.
# 매수/매도 각각에 편도로 적용되는 가정치(%) — 왕복 시 두 번 적용됨.
# 실측치 확보 전까지의 잠정 가정이며, 백테스트 결과 해석 시 이 가정에 의존한다는 점을 감안할 것.
TRADING_COSTS = {
    "crypto": {"fee_pct": 0.05, "slippage_pct": 0.1},   # 업비트 매수/매도 수수료 0.05%(실측) + 가정 슬리피지
    "krx": {"fee_pct": 0.015, "slippage_pct": 0.1, "sell_tax_pct": 0.18},
        # 토스증권 온라인 수수료(매수/매도 각 0.015%) + 가정 슬리피지 + 매도 시에만 붙는
        # 증권거래세+농특세(코스피 기준 약 0.18%; 코스닥은 이보다 낮지만 보수적으로 통일)
    "stock": {"fee_pct": 0.25, "slippage_pct": 0.1},    # 해외주식 매매수수료 가정치 + 슬리피지 (SEC 수수료 등은 미미해 생략)
}

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")

# 실계좌(토스) AI 제안 dry-run 게이트 (2026-08-01, 2026-08-02 TRACK_B_ENABLED에서 리네이밍).
# True(기본값)인 동안 ask_claude_decision은 real_portfolio.json 보유종목을 계속 참고해
# 매도/비중조정 제안을 만들지만, 그 제안은 pending_actions.json에 dry_run: true로만
# 기록되고 /approve를 눌러도 실제로는 아무것도 실행되지 않는다(실계좌엔 애초에 주문
# API가 없다 — CLAUDE.md "조회 전용" 원칙). 10월 말 게이트 통과 판정(claude.ai
# 방향성 세션) 전까지 이 값을 false로 바꾸지 말 것.
#
# 이름에 "TRACK_B"를 쓰지 않는 이유: CLAUDE.md가 "Track B"를 이미 별개의, 더 엄격한
# 의미(실주문 코드 + 자동트리거가 둘 다 존재하는 실거래 자동화 상태)로 정의해뒀다.
# TRACK_B_ENABLED라는 이름은 나중에 그 실제 마스터 스위치용으로 예약해두고, 지금은
# 만들지 않는다 — 아직 실주문 코드 자체가 없어서 그 스위치가 가리킬 대상이 없다.
AI_SUGGESTION_DRY_RUN = os.environ.get("AI_SUGGESTION_DRY_RUN", "true").lower() == "true"


def calc_ma(prices, window):
    return sum(prices[-window:]) / window

def calc_rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))

def calc_bollinger(prices, window=20, num_std=2):
    ma = calc_ma(prices, window)
    recent = prices[-window:]
    variance = sum((p - ma) ** 2 for p in recent) / window
    std = math.sqrt(variance)
    return ma + num_std * std, ma, ma - num_std * std

def estimate_holding_period(prices):
    if len(prices) < 25:
        return 7
    ma20_series = [calc_ma(prices[:i+1], 20) for i in range(19, len(prices))]
    lengths, cur = [], 1
    for i in range(1, len(ma20_series)):
        up_now = ma20_series[i] > ma20_series[i-1]
        up_prev = ma20_series[i-1] > ma20_series[i-2] if i > 1 else up_now
        if up_now == up_prev:
            cur += 1
        else:
            lengths.append(cur)
            cur = 1
    lengths.append(cur)
    avg = sum(lengths) / len(lengths) if lengths else 7
    return max(3, round(avg))

def is_golden_cross(closes, short=20, long=60):
    """단순이동평균 골든크로스 감지: 직전 봉까지는 short≤long이었다가
    이번 봉에서 short>long으로 상향 돌파했는지."""
    if len(closes) < long + 1:
        return False
    ma_short_now, ma_long_now = calc_ma(closes, short), calc_ma(closes, long)
    ma_short_prev, ma_long_prev = calc_ma(closes[:-1], short), calc_ma(closes[:-1], long)
    return ma_short_prev <= ma_long_prev and ma_short_now > ma_long_now

def calc_adx(highs, lows, closes, period=14):
    """추세 강도 근사치. calc_rsi와 동일하게 최근 period 구간을 단순평균해서
    구하는 간이 버전이며(Wilder 재귀평활은 생략), 25 이상이면 '추세가 있다'는
    게이트로만 쓴다 — 정밀한 ADX 값 자체가 목적이 아님."""
    n = len(closes)
    if n < period + 1:
        return 0
    plus_dms, minus_dms, trs = [], [], []
    for i in range(n - period, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dms.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dms.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    avg_tr = sum(trs) / len(trs)
    if avg_tr == 0:
        return 0
    plus_di = 100 * (sum(plus_dms) / len(plus_dms)) / avg_tr
    minus_di = 100 * (sum(minus_dms) / len(minus_dms)) / avg_tr
    denom = plus_di + minus_di
    if denom == 0:
        return 0
    return 100 * abs(plus_di - minus_di) / denom

def classify_strategy(expected_days):
    if expected_days <= 6:
        return "단타"
    elif expected_days <= 20:
        return "스윙"
    return "장기"

def entry_score(closes, volumes=None):
    """스캔/백테스트가 공유하는 관심종목 사전 필터. 라이브 스캔과 과거 시뮬레이션이
    서로 다른 로직으로 갈라지지 않도록 여기서 한 곳에만 둔다.

    Phase 2부터는 이 점수가 매수 근거가 아니다 — 하루에 전체 마켓(크립토만 80개+)을
    다 Claude에 보낼 수 없어서 후보를 추리는 실무적 사전 필터일 뿐이고, 실제 매수/매도
    판단은 ask_claude_decision이 뉴스 사건을 중심으로 내린다(계획서 v3 원칙 #4).
    HARD_STOP_LOSS만 여전히 AI 판단과 무관한 무조건 안전장치다."""
    rsi = calc_rsi(closes)
    upper, mid, lower = calc_bollinger(closes)
    price = closes[-1]
    score = 0
    if 30 <= rsi <= 45:
        score += 2
    if price <= lower * 1.03:
        score += 2
    if volumes is not None:
        avg_vol = sum(volumes[-5:]) / 5
        if volumes[-1] > avg_vol * 1.3:
            score += 1
    return score, rsi


def get_krw_candles(market, count=60):
    """일봉 조회. count<=200이면 단일 호출(기존 동작과 동일),
    그보다 크면 `to` 파라미터로 과거 방향 페이지네이션한다(백테스트의 장기 히스토리 조회용)."""
    all_candles = []
    to_param = None
    while len(all_candles) < count:
        batch_size = min(200, count - len(all_candles))
        params = {"market": market, "count": batch_size}
        if to_param:
            params["to"] = to_param
        batch = requests.get("https://api.upbit.com/v1/candles/days", params=params, timeout=10).json()
        if not batch:
            break
        all_candles.extend(batch)
        to_param = batch[-1]["candle_date_time_utc"]
        if len(batch) < batch_size:
            break
        if len(all_candles) < count:
            time.sleep(0.12)  # 업비트 rate limit 배려 - 다중 페이지네이션(백테스트의 대량 히스토리 조회)에서만 발생
    all_candles.reverse()
    return all_candles

def get_all_krw_markets():
    data = requests.get("https://api.upbit.com/v1/market/all", timeout=10).json()
    return [m['market'] for m in data if m['market'].startswith("KRW-") and m['market'] not in EXCLUDE_MARKETS]

def get_krw_price(market):
    data = requests.get("https://api.upbit.com/v1/ticker", params={"markets": market}, timeout=10).json()
    return data[0]['trade_price']

def scan_crypto(exclude, top_n=3):
    results = []
    for market in get_all_krw_markets()[:80]:
        if market in exclude:
            continue
        try:
            candles = get_krw_candles(market, 30)
            closes = [c['trade_price'] for c in candles]
            volumes = [c['candle_acc_trade_volume'] for c in candles]
            if len(closes) < 20:
                continue
            score, rsi = entry_score(closes, volumes)
            price = closes[-1]
            if score >= 3:
                results.append({"market": market, "asset_class": "crypto", "score": score, "rsi": rsi, "price": price, "raw_closes": closes})
        except Exception:
            continue
    results.sort(key=lambda x: -x["score"])
    return results[:top_n]


HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; quantrade-bot/1.0)"}


def get_us_closes(ticker, count=60):
    """미국주식 일봉 종가. stooq가 GitHub Actions IP에서 봇차단 JS 챌린지를 주는 것이
    확인되어(phase-1 백테스트, backtest_report.json에 미국주식 결과가 아예 안 잡힘 —
    CLAUDE.md 참고) Yahoo Finance 차트 API를 우선 시도하고, 실패하면 stooq로 폴백한다.
    Yahoo도 언젠가 같은 이유로 막힐 수 있고 이 환경에서는 실제 네트워크 검증이
    불가능했으므로, daily.yml/backtest.yml 실행 로그로 실제 동작을 확인할 것."""
    errors = []
    try:
        return _get_us_closes_yahoo(ticker, count)
    except Exception as e:
        errors.append(f"yahoo: {e}")
    try:
        return _get_us_closes_stooq(ticker, count)
    except Exception as e:
        errors.append(f"stooq: {e}")
    raise ValueError(f"{ticker} 시세 조회 실패 - " + " / ".join(errors))


def _get_us_closes_yahoo(ticker, count):
    end = datetime.now()
    start = end - timedelta(days=int(count * 1.6) + 30)
    params = {"period1": int(start.timestamp()), "period2": int(end.timestamp()), "interval": "1d"}
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}",
        params=params, timeout=10, headers=HTTP_HEADERS,
    )
    try:
        data = resp.json()
    except ValueError:
        raise ValueError(f"JSON 아님 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    result = (data.get("chart") or {}).get("result")
    if not result:
        err = (data.get("chart") or {}).get("error")
        raise ValueError(f"result 없음 (error={err}, status={resp.status_code})")
    closes_raw = result[0]["indicators"]["quote"][0]["close"]
    closes = [c for c in closes_raw if c is not None]
    if not closes:
        raise ValueError("유효한 종가 없음")
    return closes[-count:]


def _get_us_closes_stooq(ticker, count):
    resp = requests.get(f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d", timeout=10, headers=HTTP_HEADERS)
    lines = resp.text.strip().split("\n")
    if not lines or not lines[0].lower().startswith("date,"):
        raise ValueError(
            f"CSV 대신 다른 응답 - 클라우드 IP 차단(봇 감지) 가능성 "
            f"(status={resp.status_code}, body[:120]={resp.text[:120]!r})"
        )
    closes = [float(l.split(",")[4]) for l in lines[1:] if len(l.split(",")) >= 5]
    if not closes:
        raise ValueError(f"stooq 응답에서 시세를 못 찾음 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    return closes[-count:]

def get_us_price(ticker):
    return get_us_closes(ticker, 5)[-1]

def get_us_candles(ticker, count=60):
    """get_us_closes와 별개로 OHLC 전체가 필요한 소비자(백테스트의 ADX 계산 등)용.
    라이브 스캔(scan_stocks/get_us_price)은 계속 get_us_closes만 쓰므로 영향 없음.
    get_us_closes와 동일하게 Yahoo 우선, stooq 폴백 순서를 따른다."""
    errors = []
    try:
        return _get_us_candles_yahoo(ticker, count)
    except Exception as e:
        errors.append(f"yahoo: {e}")
    try:
        return _get_us_candles_stooq(ticker, count)
    except Exception as e:
        errors.append(f"stooq: {e}")
    raise ValueError(f"{ticker} OHLC 조회 실패 - " + " / ".join(errors))


def _get_us_candles_yahoo(ticker, count):
    end = datetime.now()
    start = end - timedelta(days=int(count * 1.6) + 30)
    params = {"period1": int(start.timestamp()), "period2": int(end.timestamp()), "interval": "1d"}
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}",
        params=params, timeout=10, headers=HTTP_HEADERS,
    )
    try:
        data = resp.json()
    except ValueError:
        raise ValueError(f"JSON 아님 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    result = (data.get("chart") or {}).get("result")
    if not result:
        err = (data.get("chart") or {}).get("error")
        raise ValueError(f"result 없음 (error={err}, status={resp.status_code})")
    timestamps = result[0].get("timestamp") or []
    quote = result[0]["indicators"]["quote"][0]
    candles = []
    for i, ts in enumerate(timestamps):
        o, h, l, c = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i]
        if None in (o, h, l, c):
            continue
        candles.append({
            "date": datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
            "open": o, "high": h, "low": l, "close": c, "volume": quote["volume"][i] or 0,
        })
    if not candles:
        raise ValueError("유효한 OHLC 없음")
    return candles[-count:]


def _get_us_candles_stooq(ticker, count):
    resp = requests.get(f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d", timeout=10, headers=HTTP_HEADERS)
    lines = resp.text.strip().split("\n")
    if not lines or not lines[0].lower().startswith("date,"):
        raise ValueError(
            f"CSV 대신 다른 응답 - 클라우드 IP 차단(봇 감지) 가능성 "
            f"(status={resp.status_code}, body[:120]={resp.text[:120]!r})"
        )
    candles = []
    for l in lines[1:]:
        parts = l.split(",")
        if len(parts) < 6:
            continue
        candles.append({"date": parts[0], "open": float(parts[1]), "high": float(parts[2]),
                         "low": float(parts[3]), "close": float(parts[4]), "volume": float(parts[5])})
    if not candles:
        raise ValueError(f"stooq 응답에서 시세를 못 찾음 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    return candles[-count:]

def scan_stocks(exclude, top_n=2):
    results = []
    for ticker in US_STOCKS:
        if ticker in exclude:
            continue
        try:
            closes = get_us_closes(ticker, 30)
            if len(closes) < 20:
                continue
            score, rsi = entry_score(closes)
            price = closes[-1]
            if score >= 2:
                results.append({"market": ticker, "asset_class": "stock", "score": score, "rsi": rsi, "price": price, "raw_closes": closes})
        except Exception:
            continue
    results.sort(key=lambda x: -x["score"])
    return results[:top_n]


def get_krx_price(code):
    url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
    data = requests.get(url, timeout=10).json()
    return float(data["datas"][0]["closePrice"].replace(",", ""))

def get_krx_candles(code, count=750):
    """국내 주식 일봉 히스토리. 토스증권 API 연동 전까지는 네이버 금융 시세를
    과거 데이터 소스로 사용한다(계획서 v3 §3.2). 응답이 순수 JSON이 아닌
    JS 배열 리터럴이라 정규식으로 행만 추출한다."""
    end = datetime.now()
    start = end - timedelta(days=int(count * 1.6) + 30)  # 주말/휴장일 감안한 여유
    params = {
        "symbol": code, "requestType": 1,
        "startTime": start.strftime("%Y%m%d"), "endTime": end.strftime("%Y%m%d"),
        "timeframe": "day",
    }
    resp = requests.get("https://api.finance.naver.com/siseJson.naver", params=params, timeout=10, headers=HTTP_HEADERS)
    rows = re.findall(
        r"\[[\"'](\d{8})[\"'],\s*([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+)",
        resp.text,
    )
    if not rows:
        raise ValueError(f"네이버 시세 응답에서 데이터를 못 찾음 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    candles = [
        {"date": r[0], "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
         "close": float(r[4]), "volume": float(r[5])}
        for r in rows
    ]
    return candles[-count:]


def get_news_sentiment(query):
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        titles = [item.find("title").text for item in root.findall(".//item")][:10]
    except Exception:
        return "뉴스 조회 실패"
    pos = sum(1 for t in titles for w in POSITIVE_WORDS if w in t.lower())
    neg = sum(1 for t in titles for w in NEGATIVE_WORDS if w in t.lower())
    if pos + neg == 0:
        return "중립"
    if pos > neg:
        return f"긍정 우세 ({pos}/{neg})"
    if neg > pos:
        return f"부정 우세 ({pos}/{neg})"
    return "혼조"


def get_news_headlines(query, limit=5):
    """[실험 단계 전용 — ask_claude_decision/analyze.py의 실제 승인 흐름에는
    연결돼 있지 않다] 뉴스 헤드라인 원문을 가져온다 — 사건 추출용(계획서 v3
    원칙 #4: "뉴스는 감성이 아니라 사건 단위로 분석해야 의미가 있다").

    2026-08-01: get_news_sentiment를 대체해 ask_claude_decision에 직접
    연결했었으나, 검증되지 않은 변경을 실제 승인 흐름에 바로 반영한 것 자체가
    "안전장치·승인기준은 검증 전 변경 금지" 원칙 위반이라 되돌렸다. 이 함수와
    _format_news는 삭제하지 않고 별도 실험 스크립트(news_event_experiment.py)
    전용으로 남겨둔다 — 캘리브레이션 결과가 나온 뒤에 언제/어떻게 실제 흐름에
    다시 연결할지 별도로 논의한다. 그 전까지 라이브 뉴스 판단은
    get_news_sentiment(감성 단어 카운트)가 담당한다.

    2026-08-01 추가 변경: Phase 2가 KRX 중심(계획서 원칙)이라 쿼리 로케일을
    en-US에서 ko-KR로 바꿨다 — 실적발표/공시/M&A/규제 같은 사건 뉴스는 거의
    다 한국어로 나오므로 영어 로케일로는 관련 기사를 거의 못 찾는다.
    get_news_sentiment는 여전히 라이브 경로라 로케일을 그대로 두고 건드리지
    않았다(분리 원칙). query는 종목코드(예: "005930") 그대로 넘기면 되는데,
    한국 금융 기사는 관례적으로 회사명 옆에 "(코드)"를 병기하는 경우가 많아
    코드만으로도 어느 정도 매칭이 되지만, 회사명 매핑이 없어 코드만 못 실린
    기사는 놓친다 — 재현율을 더 높이려면 종목코드→회사명 매핑이 필요하고,
    이건 이 세션 스코프 밖으로 남겨둔다(Naver 실시간시세 API가 이름 필드를
    주는지는 이 샌드박스에서 네트워크가 막혀 있어 확인하지 못했다).

    반환값: 성공 시 헤드라인 리스트(빈 리스트=진짜 관련 뉴스 없음), 조회 자체가
    실패하면 None(네트워크 실패와 "뉴스 없음"을 구분해야 프롬프트에서 다르게
    표현할 수 있다)."""
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        titles = [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
        return titles[:limit]
    except Exception:
        return None


def load_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            return default
    return default

def save_json(path, data):
    json.dump(data, open(path, "w"), indent=2, ensure_ascii=False)

def get_current_price(asset_class, market):
    if asset_class == "crypto":
        return get_krw_price(market)
    elif asset_class == "krx":
        return get_krx_price(market)
    else:
        return get_us_price(market)


def _format_news(headlines):
    """[실험 단계 전용] get_news_headlines의 출력(헤드라인 리스트/None/빈 리스트)을
    사람이 읽을 문자열로 바꾸는 포맷터. get_news_headlines와 마찬가지로 현재
    ask_claude_decision에서는 쓰지 않는다 — 짝을 이루는 함수라 같이 남겨둔다."""
    if headlines is None:
        return "뉴스 조회 실패"
    if not headlines:
        return "관련 뉴스 없음"
    return " / ".join(headlines)


def ask_claude_decision(held_positions, candidates, news_by_market, real_positions=None):
    real_positions = real_positions or []
    tradeable = [p for p in held_positions if not p.get("conviction")]
    conviction_holds = [p for p in held_positions if p.get("conviction")]

    holdings_text = "\n".join([
        f"- {p['market']} ({p.get('strategy_type','스윙')}): 진입가 {p['entry_price']}, 현재 {p.get('current_price','?')}, 수익률 {p.get('current_return', 0):+.2f}%"
        for p in tradeable
    ]) or "없음"

    conviction_text = "\n".join([
        f"- {p['market']}: 수익률 {p.get('current_return', 0):+.2f}% (사용자 확신 장기보유, 매도 판단 대상 아님)"
        for p in conviction_holds
    ]) or "없음"

    candidates_text = "\n".join([
        f"- {c['market']} ({c['asset_class']}): 점수 {c['score']}, RSI {c['rsi']:.0f}, 예상보유 {c['expected_days']}일, 뉴스분위기 {news_by_market.get(c['market'], '정보없음')}"
        for c in candidates
    ]) or "없음"

    # 실계좌(토스) 보유종목 — 계좌번호 등 식별정보는 절대 넘기지 않는다. 종목명/수량/현재가/
    # 수익률만 전달(analyze.py에서 이미 필터링해서 넘어옴).
    real_text = "\n".join([
        f"- {p['name']} ({p['symbol']}): 수량 {p['quantity']}, 현재가 {p['current_price']}, 수익률 {p.get('return_pct', 0):+.2f}%"
        for p in real_positions
    ]) or "없음"

    prompt_text = (
        "너는 개인 투자자를 위한 퀀트 자산관리 AI야. 아래 정보를 보고 실제 결정을 내려줘.\n\n"
        f"[매매 판단 대상 보유 포지션]\n{holdings_text}\n\n"
        f"[사용자 확신 장기보유 종목 - 참고만]\n{conviction_text}\n\n"
        f"[신규 진입 후보]\n{candidates_text}\n\n"
        f"[실계좌 보유종목 - 조회전용, 매도 또는 비중조정만 판단(매수 불가)]\n{real_text}\n\n"
        "실계좌 종목에 대한 결정은 market 필드를 반드시 'REAL:종목코드' 형식으로 써(예: REAL:005930). "
        "action은 매도 또는 비중조정만 가능하고, 보유가 적절한 실계좌 종목은 별도 decision을 만들지 마.\n\n"
        "다음 JSON 형식으로만 답해줘. 매우 중요한 규칙:\n"
        "- 다른 설명 텍스트 없이 순수 JSON만 출력\n"
        "- 모든 문자열 값은 반드시 큰따옴표로 감싸고, 문자열 안에는 줄바꿈이나 큰따옴표를 절대 넣지 마\n"
        "- reasoning은 한 줄로, 쉼표나 마침표로만 문장을 구분해\n\n"
        "{\n"
        '  "market_summary": "전체 시장 상황 한 줄 요약",\n'
        '  "decisions": [\n'
        "    {\n"
        '      "market": "종목코드",\n'
        '      "action": "매도 또는 매수 또는 보유 또는 비중조정",\n'
        '      "target_weight_pct": 0에서100사이숫자 또는 null,\n'
        '      "reasoning": "한 줄로 된 이유"\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    for attempt in range(2):  # 실패하면 한 번 더 시도
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-6", "max_tokens": 1500, "messages": [{"role": "user", "content": prompt_text}]},
                timeout=30
            )
            data = response.json()
            if "content" not in data:
                return {"market_summary": f"AI 응답 오류: {data}", "decisions": []}
            raw_text = data["content"][0]["text"]
            cleaned = raw_text.strip().replace("```json", "").replace("```", "").strip()
            # 혹시 앞뒤에 다른 텍스트가 섞였으면 { } 부분만 추출
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
            return json.loads(cleaned)
        except Exception as e:
            if attempt == 0:
                continue  # 한 번 더 시도
            return {"market_summary": f"AI 판단 실패: {e}", "decisions": []}
    return {"market_summary": "AI 판단 실패: 재시도 초과", "decisions": []}


def send_telegram(msg):
    if not msg:
        msg = "(빈 메시지)"
    for i in range(0, len(msg), 4000):
        try:
            resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                  data={"chat_id": TELEGRAM_CHAT_ID, "text": msg[i:i+4000]}, timeout=15)
            print("텔레그램 응답:", resp.json())
        except Exception as e:
            print("⚠️ 텔레그램 실패:", e)
