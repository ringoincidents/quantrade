import requests
import math

TELEGRAM_TOKEN = "8978432332:AAH451qYm5sjhbVgYwYY3G4rfxeUowiIlNc"
TELEGRAM_CHAT_ID = "8964780804"
MAIN_MARKET = "KRW-BTC"

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

# ===== 지표 계산 =====
def calc_ma(prices, window):
    return sum(prices[-window:]) / window

def calc_ema_series(prices, period):
    ema = [prices[0]]
    k = 2 / (period + 1)
    for p in prices[1:]:
        ema.append(p * k + ema[-1] * (1 - k))
    return ema

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

def calc_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = calc_ema_series(prices, fast)
    ema_slow = calc_ema_series(prices, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = calc_ema_series(macd_line, signal)
    hist = macd_line[-1] - signal_line[-1]
    prev_hist = macd_line[-2] - signal_line[-2]
    return macd_line[-1], signal_line[-1], hist, prev_hist

def calc_atr(candles, period=14):
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]['high_price']
        low = candles[i]['low_price']
        prev_close = candles[i-1]['trade_price']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / period

# ===== 지표 해설 (쉬운 말로) =====
def explain_rsi(rsi):
    if rsi > 70:
        return f"RSI {rsi:.0f} → 최근 많이 올라서 '과열' 상태예요. 단기 조정 가능성 있음"
    elif rsi < 30:
        return f"RSI {rsi:.0f} → 많이 떨어져서 '과매도' 상태예요. 반등 가능성 있으나 더 떨어질 수도"
    else:
        return f"RSI {rsi:.0f} → 특별히 과열/과매도 아닌 중립 구간"

def explain_macd(hist, prev_hist):
    if hist > 0 and prev_hist <= 0:
        return "MACD 골든크로스 → 상승 모멘텀 시작 신호"
    elif hist < 0 and prev_hist >= 0:
        return "MACD 데드크로스 → 하락 모멘텀 시작 신호"
    elif hist > 0:
        return "MACD 양전환 유지 → 상승 흐름 지속 중"
    else:
        return "MACD 음전환 유지 → 하락 흐름 지속 중"

# ===== 예상 보유기간 (참고용 통계, 확정 아님) =====
def estimate_holding_period(candles):
    closes = [c['trade_price'] for c in candles]
    ma20_series = [calc_ma(closes[:i+1], 20) for i in range(19, len(closes))]
    # 추세 방향이 바뀌기까지 걸린 평균 일수 계산 (단순화된 근사치)
    trend_lengths = []
    current_len = 1
    for i in range(1, len(ma20_series)):
        if (ma20_series[i] > ma20_series[i-1]) == (ma20_series[i-1] > ma20_series[i-2] if i > 1 else True):
            current_len += 1
        else:
            trend_lengths.append(current_len)
            current_len = 1
    trend_lengths.append(current_len)
    avg_trend = sum(trend_lengths) / len(trend_lengths) if trend_lengths else 7
    return round(avg_trend)

# ===== 단일 종목 상세 분석 =====
def analyze_single(market):
    candles = get_candles(market, count=60)
    closes = [c['trade_price'] for c in candles]
    volumes = [c['candle_acc_trade_volume'] for c in candles]

    current_price = closes[-1]
    ma5, ma20, ma60 = calc_ma(closes, 5), calc_ma(closes, 20), calc_ma(closes, 60)
    rsi = calc_rsi(closes, 14)
    upper, mid, lower = calc_bollinger(closes, 20)
    macd, signal, hist, prev_hist = calc_macd(closes)
    atr = calc_atr(candles)
    avg_volume = sum(volumes[-5:]) / 5
    current_volume = volumes[-1]
    holding_days = estimate_holding_period(candles)

    lines = [f"📊 {market} 상세 분석", f"현재가: {current_price:,.0f}"]
    lines.append(f"이평선(5/20/60): {ma5:,.0f} / {ma20:,.0f} / {ma60:,.0f}")
    lines.append(f"변동성(ATR): 일평균 ±{atr:,.0f} 변동")
    lines.append("")
    lines.append("📖 지표 해설")
    lines.append(explain_rsi(rsi))
    lines.append(explain_macd(hist, prev_hist))

    if current_price >= upper:
        lines.append("볼린저 상단 돌파 → 단기 과열 구간")
    elif current_price <= lower:
        lines.append("볼린저 하단 돌파 → 단기 낙폭 과대 구간")

    if current_volume > avg_volume * 1.5:
        lines.append("거래량 급증 → 신호 신뢰도 상승")

    lines.append("")
    lines.append(f"⏱ 참고용 예상 흐름 지속기간: 약 {holding_days}일")
    lines.append("(과거 추세 지속 패턴 기반 통계 추정치, 확정 예측 아님)")

    return "\n".join(lines)

# ===== 전체 시장 스캔 (저평가/반등 후보 발굴) =====
def scan_market(top_n=5):
    markets = get_all_krw_markets()
    candidates = []

    for market in markets[:80]:  # 과도한 API 호출 방지로 상위 80개만
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
                candidates.append((market, score, rsi, current_price))
        except Exception:
            continue

    candidates.sort(key=lambda x: -x[1])
    top = candidates[:top_n]

    lines = ["🔎 낙폭과대/반등 후보 스캔 결과", ""]
    if not top:
        lines.append("현재 조건에 맞는 후보가 없어요.")
    else:
        for market, score, rsi, price in top:
            lines.append(f"- {market}: 현재가 {price:,.0f} / RSI {rsi:.0f} / 점수 {score}")
    return "\n".join(lines)

# ===== 공포탐욕지수 =====
def get_fear_greed_index():
    try:
        data = requests.get("https://api.alternative.me/fng/", timeout=5).json()
        value = int(data['data'][0]['value'])
        classification = data['data'][0]['value_classification']
        return value, classification
    except Exception:
        return None, None

# ===== 텔레그램 전송 =====
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})

if __name__ == "__main__":
    detail = analyze_single(MAIN_MARKET)
    fng_value, fng_class = get_fear_greed_index()
    if fng_value:
        detail += f"\n\n🌐 시장 전체 공포탐욕지수: {fng_value} ({fng_class})"
        if fng_value <= 25:
            detail += "\n→ 시장 전체가 공포 상태 (역발상 관심 구간)"
        elif fng_value >= 75:
            detail += "\n→ 시장 전체가 탐욕 상태 (조정 위험 구간)"

    scan_result = scan_market(top_n=5)

    full_message = detail + "\n\n" + ("="*20) + "\n\n" + scan_result
    print(full_message)
    send_telegram(full_message)
