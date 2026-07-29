import requests
import math
import json
import os
from datetime import datetime, timedelta

TELEGRAM_TOKEN = "8978432332:AAH451qYm5sjhbVgYwYY3G4rfxeUowiIlNc"
TELEGRAM_CHAT_ID = "8964780804"
PORTFOLIO_FILE = "portfolio.json"
TOTAL_BUDGET = 100000  # 가상 총 예산 (원)
MAX_POSITIONS = 2       # 동시 보유 가능한 코인 개수
POSITION_SIZE = TOTAL_BUDGET / (MAX_POSITIONS + 1)  # 현금 슬롯 포함 분배

# ===== 데이터 수집 =====
def get_candles(market, count=60):
    url = "https://api.upbit.com/v1/candles/days"
    params = {"market": market, "count": count}
    data = requests.get(url, params=params).json()
    data.reverse()
    return data

def get_all_krw_markets():
    url = "https://api.upbit.com/v1/market/all"
    data = requests.get(url).json()
    return [m['market'] for m in data if m['market'].startswith("KRW-")]

def get_current_price(market):
    url = "https://api.upbit.com/v1/ticker"
    data = requests.get(url, params={"markets": market}).json()
    return data[0]['trade_price']

# ===== 지표 계산 =====
def calc_ma(prices, window):
    return sum(prices[-window:]) / window

def calc_rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change); losses.append(0)
        else:
            gains.append(0); losses.append(abs(change))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_bollinger(prices, window=20, num_std=2):
    ma = calc_ma(prices, window)
    recent = prices[-window:]
    variance = sum((p - ma) ** 2 for p in recent) / window
    std = math.sqrt(variance)
    return ma + (num_std * std), ma, ma - (num_std * std)

def estimate_holding_period(candles):
    closes = [c['trade_price'] for c in candles]
    ma20_series = [calc_ma(closes[:i+1], 20) for i in range(19, len(closes))]
    trend_lengths = []
    current_len = 1
    for i in range(1, len(ma20_series)):
        going_up_now = ma20_series[i] > ma20_series[i-1]
        going_up_prev = ma20_series[i-1] > ma20_series[i-2] if i > 1 else going_up_now
        if going_up_now == going_up_prev:
            current_len += 1
        else:
            trend_lengths.append(current_len)
            current_len = 1
    trend_lengths.append(current_len)
    avg_trend = sum(trend_lengths) / len(trend_lengths) if trend_lengths else 7
    return max(3, round(avg_trend))

# ===== 포트폴리오 파일 관리 =====
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"cash": TOTAL_BUDGET, "positions": []}

def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)

# ===== 전체 시장 스캔 =====
def scan_market(exclude_markets, top_n=1):
    markets = get_all_krw_markets()
    candidates = []
    for market in markets[:80]:
        if market in exclude_markets:
            continue
        try:
            candles = get_candles(market, count=30)
            closes = [c['trade_price'] for c in candles]
            volumes = [c['candle_acc_trade_volume'] for c in candles]
            if len(closes) < 20:
                continue
            rsi = calc_rsi(closes, 14)
            upper, mid, lower = calc_bollinger(closes, 20)
            current_price = closes[-1]
            avg_volume = sum(volumes[-5:]) / 5
            current_volume = volumes[-1]

            score = 0
            if 30 <= rsi <= 45:
                score += 2
            if current_price <= lower * 1.03:
                score += 2
            if current_volume > avg_volume * 1.3:
                score += 1

            if score >= 3:
                candidates.append({"market": market, "score": score, "rsi": rsi, "price": current_price})
        except Exception:
            continue
    candidates.sort(key=lambda x: -x["score"])
    return candidates[:top_n]

# ===== 메인 로직 =====
def run():
    portfolio = load_portfolio()
    today = datetime.now().strftime("%Y-%m-%d")
    report_lines = [f"📅 {today} 가상 포트폴리오 리포트", ""]

    # 1. 만기된 포지션 정리
    still_holding = []
    for pos in portfolio["positions"]:
        entry_date = datetime.strptime(pos["entry_date"], "%Y-%m-%d")
        days_held = (datetime.now() - entry_date).days
        if days_held >= pos["expected_days"]:
            current_price = get_current_price(pos["market"])
            return_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
            result_krw = pos["amount_krw"] * (1 + return_pct / 100)
            portfolio["cash"] += result_krw

            report_lines.append(f"✅ 청산: {pos['market']}")
            report_lines.append(f"  진입가 {pos['entry_price']:,.0f} → 현재가 {current_price:,.0f}")
            report_lines.append(f"  보유 {days_held}일 (예상 {pos['expected_days']}일) / 수익률 {return_pct:+.2f}%")
            report_lines.append("")
        else:
            current_price = get_current_price(pos["market"])
            return_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
            report_lines.append(f"📌 보유 중: {pos['market']} ({days_held}/{pos['expected_days']}일) 현재 {return_pct:+.2f}%")
            still_holding.append(pos)

    portfolio["positions"] = still_holding

    # 2. 빈 슬롯 있으면 신규 진입
    held_markets = [p["market"] for p in portfolio["positions"]]
    open_slots = MAX_POSITIONS - len(portfolio["positions"])

    if open_slots > 0 and portfolio["cash"] >= POSITION_SIZE:
        candidates = scan_market(exclude_markets=held_markets, top_n=open_slots)
        for c in candidates:
            candles = get_candles(c["market"], count=60)
            expected_days = estimate_holding_period(candles)
            amount = min(POSITION_SIZE, portfolio["cash"])

            portfolio["positions"].append({
                "market": c["market"],
                "entry_price": c["price"],
                "entry_date": today,
                "expected_days": expected_days,
                "amount_krw": amount
            })
            portfolio["cash"] -= amount

            report_lines.append(f"🆕 신규 진입: {c['market']}")
            report_lines.append(f"  진입가 {c['price']:,.0f} / RSI {c['rsi']:.0f} / 점수 {c['score']}")
            report_lines.append(f"  예상 보유기간: 약 {expected_days}일 / 투입금액 {amount:,.0f}원")
            report_lines.append("")

    report_lines.append(f"💰 현재 현금: {portfolio['cash']:,.0f}원")
    report_lines.append(f"📊 보유 종목 수: {len(portfolio['positions'])}/{MAX_POSITIONS}")

    save_portfolio(portfolio)
    return "\n".join(report_lines)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})

if __name__ == "__main__":
    result = run()
    print(result)
    send_telegram(result)
