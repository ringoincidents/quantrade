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

def ask_claude_decision(held_positions, candidates, news_by_market):
    holdings_text = "\n".join([
        f"- {p['market']} ({p.get('strategy_type','스윙')}): 진입가 {p['entry_price']}, 현재 {p.get('current_price','?')}, 수익률 {p.get('current_return', 0):+.2f}%"
        for p in held_positions
    ]) or "없음"

    candidates_text = "\n".join([
        f"- {c['market']} ({c['asset_class']}): 점수 {c['score']}, RSI {c['rsi']:.0f}, 예상보유 {c['expected_days']}일, 뉴스분위기 {news_by_market.get(c['market'], '정보없음')}"
        for c in candidates
    ]) or "없음"

    prompt_text = f"""너는 개인 투자자를 위한 퀀트 자산관리 AI야. 아래 정보를 보고 실제 결정을 내려줘.

[현재 보유 포지션]
{holdings_text}

[신규 진입 후보]
{candidates_text}

다음 JSON 형식으로만 답해줘. 다른 설명 텍스트 없이 JSON만:

{{
  "market_summary": "전체 시장 상황 2-3문장 요약",
  "decisions": [
    {{
      "market": "종목코드",
      "action": "매도 또는 매수 또는 보유 또는 비중조정",
      "target_weight_pct": 0에서100사이숫자 (매수/비중조정일 때만, 아니면 null),
      "reasoning": "이 결정을 내린 구체적 이유 2-3문장"
    }}
  ]
}}

보유 포지션 중 명확히 안 좋은 신호가 있으면 조기 매도를 제안해도 돼. 신규 후보 중 정말 괜찮은 것만 매수 결정해. 확정 예측이 아니라 참고용 판단임을 reasoning에 자연스럽게 녹여줘."""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt_text}]
            },
            timeout=30
        )
        raw_text = response.json()["content"][0]["text"]
        cleaned = raw_text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception as e:
        return {"market_summary": f"AI 판단 실패: {e}", "decisions": []}


def run():
    portfolio = load_json(PORTFOLIO_FILE, {"cash": TOTAL_BUDGET, "positions": []})
    history = load_json(HISTORY_FILE, {"trades": []})
    today = datetime.now().strftime("%Y-%m-%d")
    report = [f"📅 {today} 통합 포트폴리오 리포트", ""]

    # 1. 보유 포지션 현재가/수익률 갱신
    for pos in portfolio["positions"]:
        asset_class = pos.get("asset_class", "crypto")
        price = get_current_price(asset_class, pos["market"])
        pos["current_price"] = price
        pos["current_return"] = (price - pos["entry_price"]) / pos["entry_price"] * 100

    # 2. 신규 후보 스캔
    held_all = [p["market"] for p in portfolio["positions"]]
    crypto_cands = scan_crypto(exclude=held_all, top_n=3)
    stock_cands = scan_stocks(exclude=held_all, top_n=2)
    all_cands = crypto_cands + stock_cands

    news_by_market = {}
    for c in all_cands:
        c["expected_days"] = estimate_holding_period(c["raw_closes"])
        c["strategy_type"] = classify_strategy(c["expected_days"])
        mood, _ = get_news_sentiment(c["market"].replace("KRW-", ""))
        news_by_market[c["market"]] = mood

    # 3. AI에게 결정 요청
    ai_result = ask_claude_decision(portfolio["positions"], all_cands, news_by_market)
    report.append("🤖 AI 시장 요약")
    report.append(ai_result.get("market_summary", "요약 없음"))
    report.append("")

    decisions = ai_result.get("decisions", [])
    decision_map = {d["market"]: d for d in decisions}

    # 4. AI 결정 실행 — 매도
    still_holding = []
    for pos in portfolio["positions"]:
        market = pos["market"]
        decision = decision_map.get(market)
        if decision and decision["action"] == "매도":
            ret = pos["current_return"]
            portfolio["cash"] += pos["amount_krw"] * (1 + ret / 100)
            history["trades"].append({
                "market": market, "asset_class": pos.get("asset_class", "crypto"),
                "strategy_type": pos.get("strategy_type", "스윙"),
                "entry_date": pos["entry_date"], "exit_date": today, "return_pct": ret
            })
            report.append(f"✅ AI 매도 결정: {market} (수익률 {ret:+.2f}%)")
            report.append(f"   이유: {decision['reasoning']}")
        else:
            days_held = (datetime.now() - datetime.strptime(pos["entry_date"], "%Y-%m-%d")).days
            report.append(f"📌 보유 유지: {market} ({days_held}일) {pos['current_return']:+.2f}%")
            if decision:
                report.append(f"   AI 코멘트: {decision['reasoning']}")
            still_holding.append(pos)
    portfolio["positions"] = still_holding

    # 5. AI 결정 실행 — 매수 (target_weight_pct 반영)
    min_cash = TOTAL_BUDGET * MIN_CASH_RESERVE_RATIO
    available = portfolio["cash"] - min_cash

    for c in all_cands:
        decision = decision_map.get(c["market"])
        if decision and decision["action"] in ("매수", "비중조정") and available > 0:
            weight_pct = decision.get("target_weight_pct") or 20
            amount = round(available * (weight_pct / 100))
            amount = min(amount, available)
            if amount <= 0:
                continue
            portfolio["positions"].append({
                "market": c["market"], "asset_class": c["asset_class"],
                "strategy_type": c["strategy_type"], "entry_price": c["price"],
                "entry_date": today, "expected_days": c["expected_days"],
                "amount_krw": amount
            })
            portfolio["cash"] -= amount
            available -= amount
            report.append("")
            report.append(f"🆕 AI 매수 결정: {c['market']} (비중 {weight_pct}%, {amount:,.0f}원)")
            report.append(f"   이유: {decision['reasoning']}")

    report.append("")
    report.append(f"💰 현금: {portfolio['cash']:,.0f}원 / 보유 {len(portfolio['positions'])}개")

    save_json(PORTFOLIO_FILE, portfolio)
    save_json(HISTORY_FILE, history)
    return "\n".join(report)

