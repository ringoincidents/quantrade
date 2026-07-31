import requests
import math
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

EXCLUDE_MARKETS = {"KRW-USDT", "KRW-USDC", "KRW-USDE", "KRW-USDS", "KRW-DAI"}
US_STOCKS = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]
POSITIVE_WORDS = ["surge", "rally", "gain", "bullish", "record", "growth", "beat", "strong"]
NEGATIVE_WORDS = ["crash", "plunge", "bearish", "loss", "fall", "concern", "risk", "weak", "drop"]
HARD_STOP_LOSS = {"단타": -5, "스윙": -10, "장기": -25}

# 종합계획서 v3 §2 "거래비용/슬리피지가 백테스트 계산에서 빠져 있음" 대응.
# 매수/매도 각각에 편도로 적용되는 가정치(%) — 왕복 시 두 번 적용됨.
# 실측치 확보 전까지의 잠정 가정이며, 백테스트 결과 해석 시 이 가정에 의존한다는 점을 감안할 것.
TRADING_COSTS = {
    "crypto": {"fee_pct": 0.05, "slippage_pct": 0.1},   # 업비트 수수료 + 가정 슬리피지
    "krx": {"fee_pct": 0.015, "slippage_pct": 0.1},     # 토스증권 온라인 수수료 + 가정 슬리피지
    "stock": {"fee_pct": 0.25, "slippage_pct": 0.1},    # 해외주식 매매수수료 가정치 + 슬리피지
}

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")


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

def classify_strategy(expected_days):
    if expected_days <= 6:
        return "단타"
    elif expected_days <= 20:
        return "스윙"
    return "장기"

def entry_score(closes, volumes=None):
    """스캔/백테스트가 공유하는 진입 판단 규칙. 라이브 스캔과 과거 시뮬레이션이
    서로 다른 로직으로 갈라지지 않도록 여기서 한 곳에만 둔다."""
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
    resp = requests.get(f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d", timeout=10, headers=HTTP_HEADERS)
    lines = resp.text.strip().split("\n")[1:]
    closes = [float(l.split(",")[4]) for l in lines if len(l.split(",")) >= 5]
    if not closes:
        raise ValueError(f"stooq 응답에서 시세를 못 찾음 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    return closes[-count:]

def get_us_price(ticker):
    return get_us_closes(ticker, 5)[-1]

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
        r"\['(\d{8})',\s*([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+)",
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


def ask_claude_decision(held_positions, candidates, news_by_market):
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

    prompt_text = (
        "너는 개인 투자자를 위한 퀀트 자산관리 AI야. 아래 정보를 보고 실제 결정을 내려줘.\n\n"
        f"[매매 판단 대상 보유 포지션]\n{holdings_text}\n\n"
        f"[사용자 확신 장기보유 종목 - 참고만]\n{conviction_text}\n\n"
        f"[신규 진입 후보]\n{candidates_text}\n\n"
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
