import requests
import math

# ===== 설정 (본인 값으로 채우기) =====
TELEGRAM_TOKEN = "8978432332:AAH451qYm5sjhbVgYwYY3G4rfxeUowiIlNc"
TELEGRAM_CHAT_ID = "8964780804"
MARKET = "KRW-BTC"

# ===== 데이터 수집 =====
def get_upbit_data(market, count=60):
    url = "https://api.upbit.com/v1/candles/days"
    params = {"market": market, "count": count}
    response = requests.get(url, params=params)
    data = response.json()
    data.reverse()
    return data

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

# ===== 공포탐욕지수 (코인 시장 전체 심리) =====
def get_fear_greed_index():
    try:
        url = "https://api.alternative.me/fng/"
        response = requests.get(url, timeout=5)
        data = response.json()
        value = int(data['data'][0]['value'])
        classification = data['data'][0]['value_classification']
        return value, classification
    except Exception:
        return None, None

# ===== 분석 및 메시지 생성 =====
def analyze(market):
    data = get_upbit_data(market, count=60)
    closes = [c['trade_price'] for c in data]
    volumes = [c['candle_acc_trade_volume'] for c in data]

    current_price = closes[-1]
    ma5 = calc_ma(closes, 5)
    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60)
    rsi = calc_rsi(closes, 14)
    upper, mid, lower = calc_bollinger(closes, 20)
    macd, signal, hist, prev_hist = calc_macd(closes)
    avg_volume = sum(volumes[-5:]) / 5
    current_volume = volumes[-1]
    fng_value, fng_class = get_fear_greed_index()

    lines = []
    lines.append(f"📊 {market} 분석 결과")
    lines.append(f"현재가: {current_price:,.0f}")
    lines.append(f"이평선(5/20/60): {ma5:,.0f} / {ma20:,.0f} / {ma60:,.0f}")
    lines.append(f"RSI(14): {rsi:.1f}")
    lines.append(f"볼린저(상/중/하): {upper:,.0f} / {mid:,.0f} / {lower:,.0f}")
    lines.append(f"MACD 히스토그램: {hist:,.0f}")
    if fng_value:
        lines.append(f"공포탐욕지수: {fng_value} ({fng_class})")
    lines.append("")
    lines.append("🔍 판단 힌트:")

    if ma5 > ma20 > ma60:
        lines.append("- 추세: 뚜렷한 상승 정배열")
    elif ma5 < ma20 < ma60:
        lines.append("- 추세: 뚜렷한 하락 역배열")
    elif ma5 > ma20:
        lines.append("- 추세: 단기 반등 시도")
    else:
        lines.append("- 추세: 단기 조정")

    if rsi > 70:
        lines.append("- ⚠️ RSI 과매수 구간")
    elif rsi < 30:
        lines.append("- 💡 RSI 과매도 구간")
    else:
        lines.append(f"- RSI 중립 ({rsi:.0f})")

    if current_price >= upper:
        lines.append("- ⚠️ 볼린저 상단 돌파 (단기 과열)")
    elif current_price <= lower:
        lines.append("- 💡 볼린저 하단 돌파 (낙폭 과대)")

    if hist > 0 and prev_hist <= 0:
        lines.append("- MACD 골든크로스 발생")
    elif hist < 0 and prev_hist >= 0:
        lines.append("- MACD 데드크로스 발생")
    elif hist > 0:
        lines.append("- MACD 양전환 유지 중")
    else:
        lines.append("- MACD 음전환 유지 중")

    if current_volume > avg_volume * 1.5:
        lines.append("- 📢 거래량 급증")

    if fng_value:
        if fng_value <= 25:
            lines.append("- 💡 시장 극도의 공포 (역발상 매수 관심 구간)")
        elif fng_value >= 75:
            lines.append("- ⚠️ 시장 극도의 탐욕 (조정 위험 구간)")

    return "\n".join(lines)

# ===== 텔레그램 전송 =====
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=payload)

if __name__ == "__main__":
    result = analyze(MARKET)
    print(result)
    send_telegram(result)
