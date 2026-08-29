"""[Alpha Lab — 격리됨, v4.0 §15] 보조지표 실질 우위 검증 (방향성 세션 지시, 2026-08-08).

목적: "거래량 동반 상승/하락", "추세선 이탈" 등 차트보조지표 기반 신호 7개가
118티커 유니버스(backtest.py와 동일 — 크립토 80 + 미국주식 5 + KRX 33)에서
실질적 통계적 우위를 갖는지 검증한다. UI/대시보드 착수 전 선행 조사이며,
백테스트(backtest.py)와는 독립적인 스크립트다 — entry_score/골든크로스 전략을
건드리지 않는다.

방법론(지시서 §2 그대로):
- backtest.py와 동일 유니버스, 동일 데이터 소스(load_candles), 동일 70/30
  훈련/검증 분리(인덱스 기준 split_index = int(len(candles) * 0.7)).
- 신호별로 "신호 발생 후 N일 수익률 vs 그 신호가 발생하지 않은 모든 날의
  N일 수익률"을 비교한다. N=5(거래일)로 고정했다 — 지시서가 N을 명시하지
  않아 이 저장소의 다른 이벤트 기반 검증(Phase 2 뉴스 캘리브레이션의 D+5)과
  맞춘 것이며, 후보 7번(캔들 패턴)의 지시문 표현 "다음날 수익률과의 상관"도
  방법론 일관성을 위해 같은 N=5로 통일했다 — 이 편차를 report의 note에
  명시한다.
- 상승/하락 방향이 갈리는 복합 신호(이동평균 배열, 볼린저 터치, RSI
  다이버전스, 캔들 패턴)는 신호가 예측하는 방향으로 부호를 맞춘
  "정합 수익률"(aligned_return = direction * forward_return)로 변환해
  단일 검정을 수행한다 — 그래야 상승 예측/하락 예측이 서로 상쇄돼 평균이
  0으로 씻겨나가는 것을 막을 수 있다.
- 다중비교 보정: 본페로니(7개 후보) — p_corrected = min(1, p_raw * 7).
- 훈련구간에서 보정 후 유의(p<0.05)했던 신호만 검증구간에 재적용하고,
  검증구간에서도 보정 후 유의 + 같은 방향(정합 수익률 평균 부호 동일)이어야
  "채택". 그 외 전부 "우위 없음"으로 폐기 — 숨기지 않고 표에 전부 남긴다.
- 거래비용(TRADING_COSTS, analyze_lib.py, backtest.py의 apply_cost() 그대로
  재사용)을 신호일/기준일 양쪽 forward return에 동일하게 반영한다. 양쪽에
  똑같이 적용되는 상수 성격의 차감이라 두 그룹 "차이"의 유의성 자체에는
  영향이 없지만, 지시대로 반영한다.

통계 검정: scipy를 새 의존성으로 들이지 않는다(CLAUDE.md "의존성 최소화,
requests 외 금지" 원칙) — 대신 Welch's t-test를 표준정규분포 근사(erf 기반
normal CDF, math.erf는 표준 라이브러리)로 직접 구현했다. 각 신호의 표본수(n)가
작으면(n<10) 근사 신뢰도가 낮으므로 p값을 계산하지 않고 "표본부족"으로
표시한다 — 이 저장소의 "빈 칸이 틀린 숫자보다 낫다" 원칙(rule_trigger_report.py
등에 이미 적용)을 따른다.

이 스크립트는 이 세션(Claude Code 샌드박스)에서 직접 실행할 수 없다 —
Upbit/Yahoo/stooq/Naver 네 소스 모두 이 환경의 egress 정책에서 403으로
차단된다(backtest.py도 마찬가지 제약을 갖고 있어 GitHub Actions에서만
실행됨, backtest.yml 참고). 그래서 이 스크립트도 동일하게 workflow_dispatch
전용 워크플로(indicator_significance_test.yml)로 GitHub Actions 러너에서
실행하도록 만들었다.

검증(2026-08-09, 실데이터 없이 합성 데이터로만 가능했던 것): 118종목 규모를
흉내낸 합성 driftless 랜덤워크(신호 없음, 진짜 우위가 존재하지 않는 데이터)를
돌려 훈련구간에서 "유의(p<0.05)" 판정이 나오는 비율이 기대치(~5%)에 가까운지
확인했다. 첫 시도에서 이동평균/RSI/캔들패턴 등 대부분 신호가 100%에 가깝게
"유의"로 잘못 나오는 심각한 버그를 발견했다 — direction(±1)을
`net_forward_return()`(비용까지 반영된 수익률)에 곱하다 보니 direction=-1인
표본 절반가량에서 거래비용의 부호까지 같이 뒤집혀 "비용이 오히려 수익에
도움되는" 것처럼 계산되고 있었다. cost_drag_pct()로 분리해 direction 적용
이후 방향과 무관하게 상수로 차감하도록 고친 뒤 재검증하니 유의 비율이
0~10%로 돌아왔다(`evaluate()`가 채택 여부를 가르는 α=0.05 기준과 합치).
같은 합성 데이터에 인위적으로 진짜 방향성 우위를 주입한 별도 테스트에서는
해당 신호가 정확한 부호로 강하게 유의하게 나오는 것도 확인해, 검정 자체가
진짜 신호는 잡아내고 노이즈는 걸러내는 것을 함께 확인했다. 이 재현/디버깅
과정은 스크래치패드에서 수행했고 이 파일에는 최종 수정된 코드만 남아있다 —
과정 자체는 CLAUDE.md의 이번 작업 기록(indicator_significance_test 관련
커밋 메시지)에 남겨둔다.

[Alpha Lab 격리] Core(v3.2 활성 기능 — analyze.py/analyze_lib.py/news_event_cards.py 등)와
연결 없음. 재개 절차(v4.0 §15) 완료 전 통합 금지. 물리적 파일 이동 없이 이 태그로만
격리를 표시한다(옵션 B — 상세는 CLAUDE.md "Alpha Lab 격리" 절 참고).
"""
import argparse
import math
import time

from analyze_lib import (
    FORBIDDEN_FIELDS_BASE, FORBIDDEN_PHRASES_BASE, US_STOCKS, TRADING_COSTS,
    get_all_krw_markets, save_json,
)
from backtest import (
    KRX_MARKET_CAP_TOP, CRYPTO_UNIVERSE_CAP, UPBIT_MARKET_SLEEP,
    load_candles,
)

# 2026-08-10 "자유텍스트 금지문구 전수 점검"으로 추가 — 이 파일은 지금까지
# 금지 필드/문구 검사가 전혀 없었다(0/0). 실제로는 CANDIDATES가 고정 문자열
# 목록이고 Claude API를 부르지 않아 위험도는 낮지만(market_indicators.py와
# 같은 "사람이 직접 쓴 템플릿" 위험만 있음), 점검 지시가 "안 걸려있는 곳
# 있으면 추가"이므로 다른 모듈과 같은 방어선을 둔다.
#
# "signal"은 base에서 뺀다 — evaluate()의 결과행이 쓰는 "signal" 필드는
# 매매 신호가 아니라 CANDIDATES의 지표 이름("거래량 동반 가격변동" 등)이다.
# index.html의 renderLearningRow가 이미 이 필드를 "indicator"로 바꿔치기해서
# 렌더링하는 것도 같은 이유(대시보드 쪽 주석 참고) — 여기서도 실제로 self-test를
# 돌려보니 그대로 걸렸다. portfolio_report.py의 "rank"(계급) 예외와 같은 종류.
FORBIDDEN_FIELDS = tuple(f for f in FORBIDDEN_FIELDS_BASE if f != "signal")
FORBIDDEN_PHRASES = FORBIDDEN_PHRASES_BASE

N_FORWARD = 5           # 신호 발생 후 며칠 뒤 수익률을 볼지 (지시서에 N 미지정 - 문서화된 선택)
ALPHA = 0.05
N_CANDIDATES = 7        # 본페로니 분모
WARMUP = 65             # MA60 + 여유
MIN_SAMPLE = 10         # 이보다 표본이 적으면 p값 계산하지 않음

CANDIDATES = [
    "거래량 동반 가격변동",
    "추세선 이탈",
    "이동평균선 배열(정배열/역배열)",
    "볼린저밴드 상/하단 터치+밴드폭",
    "RSI 다이버전스",
    "피보나치 되돌림 레벨 근접도",
    "캔들 패턴(장대양봉/음봉,긴꼬리도지)",
]


# ── 롤링 지표 (O(n), numpy/scipy 없이 순수 파이썬 — analyze_lib의 O(n) 재계산형
#    함수를 매일 슬라이스로 다시 부르면 118종목×수천봉에서 O(n^2)라 여기선 별도로
#    O(n) 누적합/윌더평활 버전을 쓴다) ──────────────────────────────────────────

def rolling_sma(values, window):
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        if i >= window - 1:
            out[i] = s / window
    return out


def rolling_std(values, window, means):
    out = [None] * len(values)
    s2 = 0.0
    for i, v in enumerate(values):
        s2 += v * v
        if i >= window:
            s2 -= values[i - window] ** 2
        if i >= window - 1 and means[i] is not None:
            var = s2 / window - means[i] ** 2
            out[i] = math.sqrt(max(var, 0))
    return out


def rolling_rsi(closes, period=14):
    n = len(closes)
    out = [None] * n
    if n < period + 1:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0)
        losses += abs(min(ch, 0))
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, n):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0), abs(min(ch, 0))
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def rolling_atr(highs, lows, closes, period=20):
    n = len(closes)
    tr = [0.0] * n
    for i in range(n):
        if i == 0:
            tr[i] = highs[i] - lows[i]
        else:
            tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    return rolling_sma(tr, period)


def swing_flags(values, k, mode):
    """values[i]가 [i-k, i+k] 구간의 최댓값/최솟값이면 True. k일 지연 확정."""
    n = len(values)
    out = [False] * n
    for i in range(k, n - k):
        window = values[i - k:i + k + 1]
        out[i] = (values[i] == max(window)) if mode == "high" else (values[i] == min(window))
    return out


SWING_K = 5  # 추세선/피보나치용 스윙포인트 확정 지연(일)


def compute_signals(candles):
    """신호명 -> [(index, direction)] (direction: +1 상승예측 / -1 하락예측)."""
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    opens = [c["open"] for c in candles]
    vols = [c.get("volume", 0) or 0 for c in candles]
    n = len(closes)

    ma5, ma20, ma60 = rolling_sma(closes, 5), rolling_sma(closes, 20), rolling_sma(closes, 60)
    vol_ma20 = rolling_sma(vols, 20)
    rsi14 = rolling_rsi(closes, 14)
    boll_std = rolling_std(closes, 20, ma20)
    atr20 = rolling_atr(highs, lows, closes, 20)
    swing_high_flag = swing_flags(highs, SWING_K, "high")
    swing_low_flag = swing_flags(lows, SWING_K, "low")

    signals = {name: [] for name in CANDIDATES}
    swing_highs_seen, swing_lows_seen = [], []
    prev_align = None
    prev_trend_side = None  # 추세선 대비 현재가 위/아래 상태(전일)
    bandwidth_hist = []

    for i in range(WARMUP, n):
        confirm_i = i - SWING_K
        if confirm_i >= 0:
            if swing_high_flag[confirm_i]:
                swing_highs_seen.append((confirm_i, highs[confirm_i]))
            if swing_low_flag[confirm_i]:
                swing_lows_seen.append((confirm_i, lows[confirm_i]))

        # 1. 거래량 동반 가격변동: 20일 평균 대비 거래량 2배 이상 + 당일 |수익률| 2%p 이상
        if vol_ma20[i] and vol_ma20[i] > 0 and closes[i - 1]:
            vol_ratio = vols[i] / vol_ma20[i]
            ret_today = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
            if vol_ratio >= 2.0 and abs(ret_today) >= 2.0:
                signals["거래량 동반 가격변동"].append((i, 1 if ret_today > 0 else -1))

        # 3. 이동평균선 배열: 정배열/역배열 진입 첫날만 신호(계속 유지되는 날은 제외)
        if ma5[i] and ma20[i] and ma60[i]:
            if ma5[i] > ma20[i] > ma60[i]:
                align = "bull"
            elif ma5[i] < ma20[i] < ma60[i]:
                align = "bear"
            else:
                align = None
            if align and align != prev_align:
                signals["이동평균선 배열(정배열/역배열)"].append((i, 1 if align == "bull" else -1))
            prev_align = align

        # 4. 볼린저밴드 터치 + 밴드폭 스퀴즈(직전 120일 밴드폭 하위 30%일 때만)
        if ma20[i] and boll_std[i] is not None and ma20[i] != 0:
            upper, lower = ma20[i] + 2 * boll_std[i], ma20[i] - 2 * boll_std[i]
            bw = (upper - lower) / ma20[i] * 100
            bandwidth_hist.append(bw)
            hist = [x for x in bandwidth_hist[-120:] if x is not None]
            if len(hist) >= 20:
                pct_rank = sum(1 for x in hist if x <= bw) / len(hist)
                if pct_rank <= 0.3:
                    if closes[i] >= upper:
                        signals["볼린저밴드 상/하단 터치+밴드폭"].append((i, 1))
                    elif closes[i] <= lower:
                        signals["볼린저밴드 상/하단 터치+밴드폭"].append((i, -1))

        # 5. RSI 다이버전스: 20일 신고가인데 RSI는 직전 고점보다 낮음(약세) / 그 반대(강세)
        if rsi14[i] is not None and i >= 20:
            wc, wr = closes[i - 20:i], rsi14[i - 20:i]
            prior = [(c, r) for c, r in zip(wc, wr) if r is not None]
            if prior:
                if closes[i] >= max(c for c, _ in prior):
                    prior_r_at_high = max(prior, key=lambda cr: cr[0])[1]
                    if rsi14[i] < prior_r_at_high:
                        signals["RSI 다이버전스"].append((i, -1))
                if closes[i] <= min(c for c, _ in prior):
                    prior_r_at_low = min(prior, key=lambda cr: cr[0])[1]
                    if rsi14[i] > prior_r_at_low:
                        signals["RSI 다이버전스"].append((i, 1))

        # 7. 캔들 패턴: 장대양봉/음봉(몸통 >= 1.5*ATR20) / 긴꼬리 도지(몸통 <= 10%range, 꼬리 >= 60%range)
        if atr20[i]:
            body = abs(closes[i] - opens[i])
            rng = highs[i] - lows[i]
            if rng > 0:
                if body >= 1.5 * atr20[i]:
                    signals["캔들 패턴(장대양봉/음봉,긴꼬리도지)"].append((i, 1 if closes[i] > opens[i] else -1))
                elif body <= 0.1 * rng:
                    lower_wick = min(opens[i], closes[i]) - lows[i]
                    upper_wick = highs[i] - max(opens[i], closes[i])
                    if lower_wick >= 0.6 * rng:
                        signals["캔들 패턴(장대양봉/음봉,긴꼬리도지)"].append((i, 1))
                    elif upper_wick >= 0.6 * rng:
                        signals["캔들 패턴(장대양봉/음봉,긴꼬리도지)"].append((i, -1))

        # 2. 추세선 이탈: 최근 스윙저점 2개를 잇는 상승 지지선 하향이탈(하락신호) /
        #    최근 스윙고점 2개를 잇는 하락 저항선 상향이탈(상승신호)
        trend_side = None
        if len(swing_lows_seen) >= 2:
            (i1, p1), (i2, p2) = swing_lows_seen[-2], swing_lows_seen[-1]
            if i2 > i1 and p2 >= p1:  # 상승 지지선일 때만 의미 있음
                proj = p2 + (p2 - p1) / (i2 - i1) * (i - i2)
                if closes[i] < proj:
                    trend_side = "below_support"
        if len(swing_highs_seen) >= 2:
            (i1, p1), (i2, p2) = swing_highs_seen[-2], swing_highs_seen[-1]
            if i2 > i1 and p2 <= p1:  # 하락 저항선일 때만 의미 있음
                proj = p2 + (p2 - p1) / (i2 - i1) * (i - i2)
                if closes[i] > proj:
                    trend_side = "above_resistance" if trend_side is None else trend_side
        if trend_side and trend_side != prev_trend_side:
            signals["추세선 이탈"].append((i, -1 if trend_side == "below_support" else 1))
        prev_trend_side = trend_side

        # 6. 피보나치 되돌림: 가장 최근 스윙고점/저점 사이 되돌림 38.2/50/61.8% 근접(1% 이내)
        if swing_highs_seen and swing_lows_seen:
            hi_i, hi_p = swing_highs_seen[-1]
            lo_i, lo_p = swing_lows_seen[-1]
            if hi_p > lo_p:
                uptrend = hi_i < lo_i  # 저점이 더 최근 = 고점에서 저점으로 내려온 되돌림 구간 진행중... (아래 분기로 방향 결정)
                span = hi_p - lo_p
                levels = [lo_p + span * f for f in (0.382, 0.5, 0.618)]
                near = any(abs(closes[i] - lv) / lv <= 0.01 for lv in levels if lv)
                if near:
                    # 저점이 더 최근이면 고점->저점 하락 되돌림 중 지지 기대(반등, +1)
                    # 고점이 더 최근이면 저점->고점 상승 되돌림 중 저항 기대(반락, -1)
                    signals["피보나치 되돌림 레벨 근접도"].append((i, 1 if lo_i > hi_i else -1))

    return signals


def cost_drag_pct(asset_class):
    """왕복(매수+매도) 거래비용(%), 항상 양수 — 방향과 무관하게 항상 차감된다.

    2026-08-08 발견/수정: 처음엔 backtest.py의 apply_cost()를 그대로 재사용해
    entry/exit 가격에 적용한 뒤 direction을 곱했는데(`direction * net_forward_return`),
    이러면 direction=-1인 절반 가까운 표본에서 비용 항의 부호까지 같이 뒤집혀
    "거래비용이 오히려 수익에 도움되는" 것처럼 계산됐다 — 118종목 합성
    무편향(드리프트 0) 랜덤워크로 훈련구간 유의(p<0.05) 비율을 재본 결과
    거의 모든 신호에서 100%에 가깝게 나와(기대치 5%) 이 버그를 발견,
    거래비용을 direction 곱셈 **이전에** raw 수익률에서 분리해 계산하고,
    direction 적용 후 방향과 무관하게 상수로 빼는 방식으로 고쳤다. 고친 뒤
    같은 합성 테스트에서 유의 비율이 기대치 근처(약 5%)로 돌아옴을 확인."""
    costs = TRADING_COSTS.get(asset_class, TRADING_COSTS["stock"])
    buy_pct = costs["fee_pct"] + costs["slippage_pct"]
    sell_pct = costs["fee_pct"] + costs["slippage_pct"] + costs.get("sell_tax_pct", 0)
    return buy_pct + sell_pct


def raw_forward_return(closes, i):
    """비용 반영 전, N_FORWARD일 뒤 순수 가격변동률(%)."""
    if i + N_FORWARD >= len(closes):
        return None
    return (closes[i + N_FORWARD] - closes[i]) / closes[i] * 100


def normal_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def one_sample_p_value(diffs):
    """종목별 (신호일 평균 정합수익률 - 기준일 평균수익률) 차이값들에 대한
    양측 단일표본 z근사 검정. 표본(=신호가 1건 이상 발생한 종목 수)이
    MIN_SAMPLE 미만이면 (None, n) 반환.

    day-level(봉 단위) 데이터를 그대로 풀링해 검정하면 forward return
    윈도우(N_FORWARD=5일)가 겹치는 인접 신호일들끼리 강한 자기상관을 가져
    표준오차가 과소추정되고 순수 노이즈에서도 유의한 것처럼 나온다 —
    118개 종목 유니버스로 합성 랜덤워크(신호 없음)를 돌려 실제로 재현
    확인함(p<0.01이 기대치 1%가 아니라 40%가량 나옴). 그래서 day-level이
    아니라 "종목 하나당 값 하나"(신호일 평균 - 기준일 평균, paired)로
    집계해 종목 간에만 검정한다 — 종목 내 자기상관 문제를 원천적으로
    피하고, 종목별 기저 수익률 차이도 대응비교로 통제된다."""
    n = len(diffs)
    if n < MIN_SAMPLE:
        return None, n
    mean_d = sum(diffs) / n
    var_d = sum((x - mean_d) ** 2 for x in diffs) / (n - 1)
    se = math.sqrt(var_d / n)
    if se == 0:
        return (0.0 if mean_d != 0 else 1.0), n
    z = mean_d / se
    p = 2 * (1 - normal_cdf(abs(z)))
    return p, n


def run_instrument_signals(market, asset_class, count):
    """종목 하나당, 신호별 {"train": diff_or_None, "val": diff_or_None} 반환.
    diff = (이 종목 이 구간에서의 신호일 평균 정합수익률) - (이 종목 이 구간
    비신호일 평균수익률). 신호가 그 구간에 한 번도 안 뜬 종목은 그 구간에서
    None(집계 제외) — one_sample_p_value()가 종목별 diff 하나씩을 모아
    종목 간에만 검정하므로, 봉 단위로 풀링할 때 생기는 자기상관 문제를
    피한다(one_sample_p_value 문서 참고)."""
    candles = load_candles(market, asset_class, count)
    if len(candles) < WARMUP + N_FORWARD + 30:
        return None
    closes = [c["close"] for c in candles]
    split_index = int(len(candles) * 0.7)
    signals = compute_signals(candles)

    drag = cost_drag_pct(asset_class)
    result = {}
    for name, pts in signals.items():
        fired = set(i for i, _ in pts)
        buckets = {
            "train": {"treat": [], "base": []},
            "val": {"treat": [], "base": []},
        }
        for i, direction in pts:
            raw = raw_forward_return(closes, i)
            if raw is None:
                continue
            bucket = "train" if i < split_index else "val"
            # direction을 raw 수익률에만 곱하고, 비용은 방향과 무관하게 항상 차감한다
            # (direction*raw - drag) — direction*(raw-drag)로 쓰면 direction=-1일 때
            # 비용 부호까지 뒤집히는 버그가 재발한다(cost_drag_pct 문서 참고).
            buckets[bucket]["treat"].append(direction * raw - drag)
        for i in range(WARMUP, len(closes) - N_FORWARD):
            if i in fired:
                continue
            raw = raw_forward_return(closes, i)
            if raw is None:
                continue
            bucket = "train" if i < split_index else "val"
            buckets[bucket]["base"].append(raw - drag)

        entry = {}
        for bucket in ("train", "val"):
            treat, base = buckets[bucket]["treat"], buckets[bucket]["base"]
            if treat and base:
                entry[bucket] = (sum(treat) / len(treat)) - (sum(base) / len(base))
            else:
                entry[bucket] = None
        result[name] = entry
    return result


def merge_into(acc, per_signal):
    for name in CANDIDATES:
        for bucket in ("train", "val"):
            diff = per_signal[name][bucket]
            if diff is not None:
                acc[name][bucket].append(diff)


def evaluate(acc):
    rows = []
    for name in CANDIDATES:
        train_diffs = acc[name]["train"]
        train_p, train_n = one_sample_p_value(train_diffs)
        train_mean = (sum(train_diffs) / len(train_diffs)) if train_diffs else None
        train_p_corr = None if train_p is None else min(1.0, train_p * N_CANDIDATES)

        val_p = val_n = val_p_corr = val_mean = None
        # 훈련구간에서 유의했던 신호만 검증구간에 재적용(지시서 §2)
        if train_p_corr is not None and train_p_corr < ALPHA:
            val_diffs = acc[name]["val"]
            val_p, val_n = one_sample_p_value(val_diffs)
            val_mean = (sum(val_diffs) / len(val_diffs)) if val_diffs else None
            val_p_corr = None if val_p is None else min(1.0, val_p * N_CANDIDATES)

        same_direction = (train_mean is not None and val_mean is not None
                           and (train_mean > 0) == (val_mean > 0))
        adopted = bool(val_p_corr is not None and val_p_corr < ALPHA and same_direction)

        rows.append({
            "signal": name,
            "train_n_instruments": train_n,
            "train_p_raw": None if train_p is None else round(train_p, 5),
            "train_p_corrected": None if train_p_corr is None else round(train_p_corr, 5),
            "train_mean_diff_pct": None if train_mean is None else round(train_mean, 4),
            "val_n_instruments": val_n,
            "val_p_raw": None if val_p is None else round(val_p, 5),
            "val_p_corrected": None if val_p_corr is None else round(val_p_corr, 5),
            "val_mean_diff_pct": None if val_mean is None else round(val_mean, 4),
            "verdict": "채택" if adopted else "우위 없음(폐기)",
        })
    return rows


def format_p(p):
    if p is None:
        return "표본부족"
    return f"{p:.4f}"


def print_report_table(rows):
    print("\n[신호명] / [훈련 p,보정후] / [검증 p,보정후] / [채택·폐기]")
    for r in rows:
        train_str = format_p(r["train_p_corrected"])
        val_str = format_p(r["val_p_corrected"]) if r["train_p_corrected"] is not None and r["train_p_corrected"] < ALPHA else "검증 미실시(훈련 미통과)"
        print(f"{r['signal']} / {train_str} / {val_str} / {r['verdict']}")


def audit(obj, path="report"):
    """금지 필드/문구가 섞였는지 재귀 검사(market_indicators.py/post_trade_review.py와
    같은 패턴). 2026-08-10 "자유텍스트 금지문구 전수 점검"으로 신설."""
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in FORBIDDEN_FIELDS:
                bad.append(f"{path}.{k} (금지 필드)")
            bad += audit(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += audit(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        for ph in FORBIDDEN_PHRASES:
            if ph in obj:
                bad.append(f"{path}: 금지 문구 '{ph}'")
    return bad


def main():
    parser = argparse.ArgumentParser(description="보조지표 실질 우위 검증 — 118티커, 훈련/검증 분리, 본페로니 보정")
    parser.add_argument("--crypto", nargs="*", default=None)
    parser.add_argument("--stocks", nargs="*", default=US_STOCKS)
    parser.add_argument("--krx", nargs="*", default=None)
    parser.add_argument("--count", type=int, default=1500)
    parser.add_argument("--crypto-count", type=int, default=5000)
    parser.add_argument("--out", default="indicator_significance_report.json")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
        return

    crypto_markets = args.crypto if args.crypto is not None else get_all_krw_markets()[:CRYPTO_UNIVERSE_CAP]
    krx_tickers = args.krx if args.krx is not None else KRX_MARKET_CAP_TOP
    universe = ([(m, "crypto") for m in crypto_markets]
                + [(m, "stock") for m in args.stocks]
                + [(m, "krx") for m in krx_tickers])
    print(f"유니버스: 크립토 {len(crypto_markets)} / 미국주식 {len(args.stocks)} / KRX {len(krx_tickers)}")

    acc = {name: {"train": [], "val": []} for name in CANDIDATES}
    instruments_used = 0
    for market, asset_class in universe:
        count = args.crypto_count if asset_class == "crypto" else args.count
        try:
            per_signal = run_instrument_signals(market, asset_class, count)
        except Exception as e:
            print(f"⚠️ {market} 실패: {e}")
            continue
        finally:
            if asset_class == "crypto":
                time.sleep(UPBIT_MARKET_SLEEP)
        if per_signal is None:
            continue
        instruments_used += 1
        merge_into(acc, per_signal)

    rows = evaluate(acc)
    print_report_table(rows)

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "instruments_used": instruments_used,
        "n_forward_days": N_FORWARD,
        "alpha": ALPHA,
        "bonferroni_n": N_CANDIDATES,
        "methodology_note": (
            "신호일 vs 비신호일 N일 순수익률(거래비용 반영) 비교, Welch's t-test "
            "정규근사(erf 기반, scipy 미사용). 방향 혼재 신호는 direction*forward_return "
            "정합수익률로 단일검정. 훈련구간 보정후 유의(p<0.05)한 신호만 검증구간 "
            "재적용, 같은 방향+검증구간도 유의해야 '채택'. n<10인 구간은 표본부족으로 "
            "p값 미계산. 후보7번(캔들패턴)의 '다음날 수익률'은 방법론 통일을 위해 "
            "N=5로 일반화 — 지시서 표현과의 편차."
        ),
        "results": rows,
    }

    violations = audit(report)
    if violations:
        print("❌ 감사 위반 발견 - 저장 거부:")
        for v in violations:
            print(f"   - {v}")
        raise SystemExit(1)

    save_json(args.out, report)
    print(f"\n리포트 저장: {args.out}")


def run_self_test():
    """네트워크 미사용 — 이 파일 나머지는 전부 실데이터 조회가 필요해 이
    세션에서 돌릴 수 없지만(모듈 docstring 참고), audit()는 합성 데이터로
    독립 검증할 수 있다."""
    print("=== indicator_significance_test.py 자체 검증 (네트워크 미사용) ===\n")

    # 1) 정상 evaluate() 결과가 감사를 통과하는지 — CANDIDATES 고정 문자열,
    #    "채택"/"우위 없음(폐기)" 고정 라벨만 쓰므로 위반이 없어야 한다.
    acc = {name: {"train": [1.0, -0.5, 2.0, -1.0, 1.5, 0.8, -0.3, 1.2, 0.4, -0.6],
                  "val": [0.5, -0.2, 1.0, -0.3, 0.6]} for name in CANDIDATES}
    rows = evaluate(acc)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "instruments_used": 10,
        "n_forward_days": N_FORWARD,
        "alpha": ALPHA,
        "bonferroni_n": N_CANDIDATES,
        "methodology_note": "테스트용 고정 문구",
        "results": rows,
    }
    violations = audit(report)
    print(f"[1] 정상 evaluate() 결과 감사 -> 위반 {violations or '없음'}")
    assert violations == [], f"고정 라벨만 쓰는 정상 리포트인데 위반이 잡힘: {violations}"

    # 2) 오염된 리포트는 실제로 잡히는지
    dirty = {"results": [{"signal": "테스트", "verdict": "채택", "action": "매수",
                          "note": "지금이 기회입니다"}]}
    bad = audit(dirty)
    print(f"[2] 오염된 리포트 -> 위반 {bad}")
    assert any("action" in v for v in bad)
    assert any("지금이 기회" in v for v in bad)

    # 3) main()의 저장 거부 경로 — 오염된 report면 save_json 호출 전에 SystemExit
    violations2 = audit(dirty)
    assert violations2, "테스트 픽스처 자체가 깨끗하면 3번 검증이 무의미함"
    try:
        if violations2:
            raise SystemExit(1)
        raised = False
    except SystemExit:
        raised = True
    print(f"[3] 오염된 리포트 저장 시도 -> SystemExit={raised} (main()과 동일한 분기)")
    assert raised

    print("\n모든 자체 검증 통과(네트워크 필요한 부분은 GitHub Actions에서만 실행 가능).")


if __name__ == "__main__":
    main()
