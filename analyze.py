import requests
import math
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = "8978432332:AAH451qYm5sjhbVgYwYY3G4rfxeUowiIlNc"
TELEGRAM_CHAT_ID = "8964780804"
PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "trade_history.json"
TOTAL_BUDGET = 100000
MAX_POSITIONS = 2
MIN_CASH_RESERVE_RATIO = 0.2  # 최소 20%는 항상 현금 보유

# 스테이블코인/제외 목록 (RSI/볼린저가 무의미한 자산)
EXCLUDE_MARKETS = {
    "KRW-USDT", "KRW-USDC", "KRW-USDE", "KRW-USDS", "KRW-DAI"
}

# ===== 데이터 수집 =====
def get_candles(market, count=60, unit="days"):
    url = f"https://api.upbit.com/v1/candles/{unit}"
    params = {"market": market, "count": count}
    data = requests.get(url, params=params).json()
    data.reverse()
    return data

def get_all_krw_markets():
    url = "https://api.upbit.com/v1/market/all"
    data = requests.get(url).json()
    return [m['market'] for m in data if m['market'].startswith("KRW-") and m['market'] not in EXCLUDE_MARKETS]

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

def calc_atr(candles, period=14):
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]['high_price']
        low = candles[i]['low_price']
        prev_close = candles[i-1]['trade_price']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / period

def calc_daily_returns(prices):
    return [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]

def calc_correlation(returns_a, returns_b):
    n = min(len(returns_a), len(returns_b))
    a, b = returns_a[-n:], returns_b[-n:]
    mean_a, mean_b = sum(a)/n, sum(b)/n
    cov = sum((a[i]-mean_a)*(b[i]-mean_b) for i in range(n)) / n
    std_a = math.sqrt(sum((x-mean_a)**2 for x in a) / n)
    std_b = math.sqrt(sum((x-mean_b)**2 for x in b) / n)
    if std_a == 0 or std_b == 0:
        return 0
    return cov / (std_a * std_b)

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
    avg = sum(trend_lengths) / len(trend_lengths) if trend_lengths else 7
    std = math.sqrt(sum((x-avg)**2 for x in trend_lengths) / len(trend_lengths)) if len(trend_lengths) > 1 else avg * 0.4
    return max(3, round(avg)), round(std)

def weekly_trend_check(market):
    """주봉 기준 상승/하락 추세 확인"""
    weekly = get_candles(market, count=12, unit="weeks")
    closes = [c['trade_price'] for c in weekly]
    if len(closes) < 8:
        return "데이터 부족"
    ma4 = calc_ma(closes, 4)
    ma8 = calc_ma(closes, 8)
    return "상승" if ma4 > ma8 else "하락"

# ===== 파일 입출력 =====
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ===== 전체 시장 스캔 (지표별 상세 점수 포함) =====
def scan_market(exclude_markets, top_n=3):
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

            detail = {}
            score = 0
            if 30 <= rsi <= 45:
                score += 2; detail["RSI 과매도 회복권"] = f"{rsi:.0f} (+2)"
            else:
                detail["RSI"] = f"{rsi:.0f} (조건 미충족)"

            if current_price <= lower * 1.03:
                score += 2; detail["볼린저 하단 근접"] = "충족 (+2)"
            else:
                detail["볼린저 하단 근접"] = "미충족"

            if current_volume > avg_volume * 1.3:
                score += 1; detail["거래량 증가"] = f"{current_volume/avg_volume:.1f}배 (+1)"
            else:
                detail["거래량 증가"] = "미충족"

            weekly = weekly_trend_check(market)
            if weekly == "상승":
                score += 1; detail["주봉 추세"] = "상승 (+1)"
            else:
                detail["주봉 추세"] = weekly

            if score >= 3:
                candidates.append({
                    "market": market, "score": score, "rsi": rsi,
                    "price": current_price, "detail": detail,
                    "returns": calc_daily_returns(closes)
                })
        except Exception:
            continue
    candidates.sort(key=lambda x: -x["score"])
    return candidates[:top_n]

# ===== 메인 로직 =====
def run():
    portfolio = load_json(PORTFOLIO_FILE, {"cash": TOTAL_BUDGET, "positions": []})
    history = load_json(HISTORY_FILE, {"trades": []})
    today = datetime.now().strftime("%Y-%m-%d")
    report = [f"📅 {today} 가상 포트폴리오 리포트", ""]

    # 1. 만기 포지션 정리
    still_holding = []
    for pos in portfolio["positions"]:
        entry_date = datetime.strptime(pos["entry_date"], "%Y-%m-%d")
        days_held = (datetime.now() - entry_date).days
        current_price = get_current_price(pos["market"])
        return_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100

        if days_held >= pos["expected_days"]:
            result_krw = pos["amount_krw"] * (1 + return_pct / 100)
            portfolio["cash"] += result_krw
            history["trades"].append({
                "market": pos["market"], "entry_date": pos["entry_date"],
                "exit_date": today, "return_pct": return_pct
            })
            report.append(f"✅ 청산: {pos['market']} / 수익률 {return_pct:+.2f}% (보유 {days_held}일, 예상 {pos['expected_days']}±{pos.get('expected_std',2)}일)")
        else:
            report.append(f"📌 보유 중: {pos['market']} ({days_held}/{pos['expected_days']}일) 현재 {return_pct:+.2f}%")
            still_holding.append(pos)
    portfolio["positions"] = still_holding

    # 2. 과거 청산 성과 요약 (누적되면 점점 신뢰도 상승)
    closed_returns = [t["return_pct"] for t in history["trades"]]
    if closed_returns:
        avg_ret = sum(closed_returns) / len(closed_returns)
        win_rate = sum(1 for r in closed_returns if r > 0) / len(closed_returns) * 100
        std_ret = math.sqrt(sum((r-avg_ret)**2 for r in closed_returns)/len(closed_returns)) if len(closed_returns) > 1 else 0
        sharpe_like = avg_ret / std_ret if std_ret > 0 else 0
        report.append("")
        report.append(f"📈 누적 성과 (n={len(closed_returns)}): 평균수익 {avg_ret:+.2f}% / 승률 {win_rate:.0f}% / 변동성대비수익(유사샤프) {sharpe_like:.2f}")

    # 3. 신규 진입 (가중치 배분 + 상관관계 체크)
    held_markets = [p["market"] for p in portfolio["positions"]]
    open_slots = MAX_POSITIONS - len(portfolio["positions"])
    min_cash = TOTAL_BUDGET * MIN_CASH_RESERVE_RATIO

    if open_slots > 0 and portfolio["cash"] > min_cash:
        candidates = scan_market(exclude_markets=held_markets, top_n=open_slots + 2)

        # 상관관계 필터: 이미 보유 중인 자산과 너무 비슷하면 제외
        filtered = []
        for c in candidates:
            too_correlated = False
            for held in portfolio["positions"]:
                held_candles = get_candles(held["market"], count=30)
                held_returns = calc_daily_returns([x['trade_price'] for x in held_candles])
                corr = calc_correlation(c["returns"], held_returns)
                if corr > 0.85:
                    too_correlated = True
                    break
            if not too_correlated:
                filtered.append(c)
            if len(filtered) >= open_slots:
                break

        if filtered:
            available = portfolio["cash"] - min_cash
            total_score = sum(c["score"] for c in filtered)

            for c in filtered:
                weight = c["score"] / total_score
                amount = round(available * weight)
                candles = get_candles(c["market"], count=60)
                expected_days, expected_std = estimate_holding_period(candles)

                portfolio["positions"].append({
                    "market": c["market"], "entry_price": c["price"],
                    "entry_date": today, "expected_days": expected_days,
                    "expected_std": expected_std, "amount_krw": amount
                })
                portfolio["cash"] -= amount

                report.append("")
                report.append(f"🆕 신규 진입: {c['market']} (배분 {amount:,.0f}원, 비중 {weight*100:.0f}%)")
                for k, v in c["detail"].items():
                    report.append(f"   - {k}: {v}")
                report.append(f"   예상 보유기간: {expected_days}±{expected_std}일")

    report.append("")
    report.append(f"💰 현금: {portfolio['cash']:,.0f}원 (최소예비 {min_cash:,.0f}원)")
    report.append(f"📊 보유 종목: {len(portfolio['positions'])}/{MAX_POSITIONS}")

    save_json(PORTFOLIO_FILE, portfolio)
    save_json(HISTORY_FILE, history)
    return "\n".join(report)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})

if __name__ == "__main__":
    result = run()
    print(result)
    send_telegram(result)
