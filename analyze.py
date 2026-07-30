import requests
import math
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime

TELEGRAM_TOKEN = "8978432332:AAH451qYm5sjhbVgYwYY3G4rfxeUowiIlNc"
TELEGRAM_CHAT_ID = "8964780804"
CLAUDE_API_KEY = "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"
PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "trade_history.json"
TOTAL_BUDGET = 100000
MIN_CASH_RESERVE_RATIO = 0.2

STRATEGY_ALLOCATION = {"장기": 0.4, "스윙": 0.4, "단타": 0.2}
MAX_POSITIONS_PER_STRATEGY = {"장기": 1, "스윙": 1, "단타": 1}
EXCLUDE_MARKETS = {"KRW-USDT", "KRW-USDC", "KRW-USDE", "KRW-USDS", "KRW-DAI"}
US_STOCKS = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]
POSITIVE_WORDS = ["surge", "rally", "gain", "bullish", "record", "growth", "beat", "strong"]
NEGATIVE_WORDS = ["crash", "plunge", "bearish", "loss", "fall", "concern", "risk", "weak", "drop"]

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
    else:
        return "장기"

def get_krw_candles(market, count=60):
    data = requests.get("https://api.upbit.com/v1/candles/days", params={"market": market, "count": count}).json()
    data.reverse()
    return data

def get_all_krw_markets():
    data = requests.get("https://api.upbit.com/v1/market/all").json()
    return [m['market'] for m in data if m['market'].startswith("KRW-") and m['market'] not in EXCLUDE_MARKETS]

def get_krw_price(market):
    data = requests.get("https://api.upbit.com/v1/ticker", params={"markets": market}).json()
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
            rsi = calc_rsi(closes)
            upper, mid, lower = calc_bollinger(closes)
            price = closes[-1]
            avg_vol = sum(volumes[-5:]) / 5
            score = 0
            if 30 <= rsi <= 45:
                score += 2
            if price <= lower * 1.03:
                score += 2
            if volumes[-1] > avg_vol * 1.3:
                score += 1
            if score >= 3:
                results.append({"market": market, "asset_class": "crypto", "score": score, "rsi": rsi, "price": price, "raw_closes": closes})
        except Exception:
            continue
    results.sort(key=lambda x: -x["score"])
    return results[:top_n]

def get_us_closes(ticker, count=60):
    resp = requests.get(f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d", timeout=10)
    lines = resp.text.strip().split("\n")[1:]
    return [float(l.split(",")[4]) for l in lines if len(l.split(",")) >= 5][-count:]

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
            rsi = calc_rsi(closes)
            upper, mid, lower = calc_bollinger(closes)
            price = closes[-1]
            score = 0
            if 30 <= rsi <= 45:
                score += 2
            if price <= lower * 1.03:
                score += 2
            if score >= 2:
                results.append({"market": ticker, "asset_class": "stock", "score": score, "rsi": rsi, "price": price, "raw_closes": closes})
        except Exception:
            continue
    results.sort(key=lambda x: -x["score"])
    return results[:top_n]

def get_news_sentiment(query):
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        titles = [item.find("title").text for item in root.findall(".//item")][:10]
    except Exception:
        return "뉴스 조회 실패", []
    pos = sum(1 for t in titles for w in POSITIVE_WORDS if w in t.lower())
    neg = sum(1 for t in titles for w in NEGATIVE_WORDS if w in t.lower())
    if pos + neg == 0:
        mood = "중립"
    elif pos > neg:
        mood = f"긍정 우세 ({pos}/{neg})"
    elif neg > pos:
        mood = f"부정 우세 ({pos}/{neg})"
    else:
        mood = "혼조"
    return mood, titles[:5]

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
    return get_krw_price(market) if asset_class == "crypto" else get_us_price(market)

def ask_claude(context_text):
    try:
        prompt_text = (
            "다음은 오늘의 시장 데이터입니다.\n\n"
            + context_text
            + "\n\n이 데이터를 종합해서 아래 항목을 작성해줘:\n"
            "1. 전체 시장 상황 요약 (3줄 이내)\n"
            "2. 가장 유망한 후보와 이유\n"
            "3. 주의할 리스크\n"
            "4. 포트폴리오 비중 조정 제안 (장기/스윙/단타)\n"
            "확정 예측이 아니라 참고용 분석임을 명시해줘. 한국어로 작성해줘."
        )
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt_text}]
            },
            timeout=30
        )
        data = response.json()
        return data["content"][0]["text"]
    except Exception as e:
        return f"AI 분석 실패: {e}"

def run():
    portfolio = load_json(PORTFOLIO_FILE, {"cash": TOTAL_BUDGET, "positions": []})
    history = load_json(HISTORY_FILE, {"trades": []})
    today = datetime.now().strftime("%Y-%m-%d")
    report = [f"📅 {today} 통합 포트폴리오 리포트", ""]

    still_holding = []
    for pos in portfolio["positions"]:
        try:
            asset_class = pos.get("asset_class", "crypto")
            strategy_type = pos.get("strategy_type", "스윙")
            expected_days = pos.get("expected_days", 7)
            entry_price = pos.get("entry_price")
            amount_krw = pos.get("amount_krw", 0)
            market = pos["market"]
            entry_date = datetime.strptime(pos["entry_date"], "%Y-%m-%d")
            days_held = (datetime.now() - entry_date).days
            price = get_current_price(asset_class, market)
            ret = (price - entry_price) / entry_price * 100

            if days_held >= expected_days:
                portfolio["cash"] += amount_krw * (1 + ret / 100)
                history["trades"].append({"market": market, "asset_class": asset_class, "strategy_type": strategy_type, "entry_date": pos["entry_date"], "exit_date": today, "return_pct": ret})
                report.append(f"✅ 청산 [{strategy_type}] {market}: {ret:+.2f}% ({days_held}일)")
            else:
                report.append(f"📌 보유 [{strategy_type}] {market} ({days_held}/{expected_days}일) {ret:+.2f}%")
                still_holding.append(pos)
        except Exception as e:
            report.append(f"⚠️ {pos.get('market','?')} 처리 오류: {e}")
            still_holding.append(pos)
    portfolio["positions"] = still_holding

    for strat in STRATEGY_ALLOCATION:
        trades = [t for t in history["trades"] if t.get("strategy_type") == strat]
        if trades:
            avg = sum(t["return_pct"] for t in trades) / len(trades)
            win = sum(1 for t in trades if t["return_pct"] > 0) / len(trades) * 100
            report.append(f"📈 [{strat}] n={len(trades)} 평균 {avg:+.2f}% 승률 {win:.0f}%")

    held_by_strategy = {s: [] for s in STRATEGY_ALLOCATION}
    for p in portfolio["positions"]:
        held_by_strategy[p.get("strategy_type", "스윙")].append(p["market"])

    min_cash = TOTAL_BUDGET * MIN_CASH_RESERVE_RATIO
    held_all = [p["market"] for p in portfolio["positions"]]
    ai_context_parts = []

    if portfolio["cash"] > min_cash:
        crypto_cands = scan_crypto(exclude=held_all, top_n=3)
        stock_cands = scan_stocks(exclude=held_all, top_n=2)
        all_cands = crypto_cands + stock_cands

        for c in all_cands:
            c["expected_days"] = estimate_holding_period(c["raw_closes"])
            c["strategy_type"] = classify_strategy(c["expected_days"])
            mood, headlines = get_news_sentiment(c["market"].replace("KRW-", ""))
            c["news_mood"] = mood
            ai_context_parts.append(f"- {c['market']} ({c['asset_class']}): 점수 {c['score']}, RSI {c['rsi']:.0f}, 예상기간 {c['expected_days']}일, 뉴스분위기 {mood}")

        for strat, alloc_ratio in STRATEGY_ALLOCATION.items():
            slots_left = MAX_POSITIONS_PER_STRATEGY[strat] - len(held_by_strategy[strat])
            if slots_left <= 0:
                continue
            strat_budget = (portfolio["cash"] - min_cash) * alloc_ratio
            strat_cands = [c for c in all_cands if c["strategy_type"] == strat][:slots_left]
            for c in strat_cands:
                amount = round(strat_budget / len(strat_cands))
                if amount <= 0 or amount > portfolio["cash"] - min_cash:
                    continue
                portfolio["positions"].append({"market": c["market"], "asset_class": c["asset_class"], "strategy_type": strat, "entry_price": c["price"], "entry_date": today, "expected_days": c["expected_days"], "amount_krw": amount})
                portfolio["cash"] -= amount
                report.append(f"🆕 [{strat}] {c['market']} 배분 {amount:,.0f}원 / 예상 {c['expected_days']}일 / 뉴스: {c['news_mood']}")

    report.append("")
    report.append(f"💰 현금: {portfolio['cash']:,.0f}원 / 보유 {len(portfolio['positions'])}개")

    if ai_context_parts:
        context_text = "\n".join(ai_context_parts)
        ai_opinion = ask_claude(context_text)
        report.append("")
        report.append("🤖 AI 종합 판단")
        report.append(ai_opinion)

    save_json(PORTFOLIO_FILE, portfolio)
    save_json(HISTORY_FILE, history)
    return "\n".join(report)

def send_telegram(msg):
    for i in range(0, len(msg), 4000):
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg[i:i+4000]})

if __name__ == "__main__":
    try:
        result = run()
        print(result)
        send_telegram(result)
    except Exception as e:
        send_telegram(f"❌ 실행 오류: {e}")
