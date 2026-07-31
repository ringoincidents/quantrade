"""QuanTrade 백테스트 엔진 (Phase 1, 종합계획서 v3 §5) — 추세추종 재설계 버전.

메인 신호는 추세추종(20/60일 이동평균 골든크로스 + ADX 25 이상)으로,
RSI/볼린저는 "진입해도 되는가"가 아니라 "지금 들어가기 좋은 타이밍인가"만
판단하는 보조 필터로 격하했다. 사용자 검토 결과 기존 RSI+볼린저 단독 눌림목
매수가 검증구간에서 재현이 안 됐던 문제(2026-07-31 1차 백테스트)에 대한 대응.

주의: 이 신호는 아직 라이브 스캔(scan_crypto/scan_stocks, entry_score)에
반영되지 않았다 — 의도적으로 분리했다. "전략 검증이 아키텍처보다 먼저다"
원칙에 따라, 백테스트로 먼저 검증하고 사용자가 명시적으로 승인한 뒤에만
entry_score를 이 규칙으로 교체해야 한다.

한계: 실거래에서 보유/매도는 매번 Claude에게 물어 결정하지만, 과거 시점의
AI 판단을 재현할 방법이 없다(비용·비결정성 문제). 이 엔진은 매도 쪽을
규칙 기반(하드손절 / RSI 과열 / 타임스탑)으로 근사한다 — Phase 2의 AI 확신도
캘리브레이션이 도입되면 이 근사를 교체해야 한다.
"""
import argparse
import time
from datetime import datetime

from analyze_lib import (
    calc_rsi, calc_bollinger, calc_adx, is_golden_cross,
    estimate_holding_period, classify_strategy,
    HARD_STOP_LOSS, TRADING_COSTS, US_STOCKS,
    get_krw_candles, get_us_candles, get_krx_candles, get_all_krw_markets, save_json,
)

# 종합계획서 v3 §4.3 — 결과가 나온 뒤 기준을 짜맞추는 것을 막기 위해 미리 박아둔
# 성공 기준. 사후에 임의로 바꾸지 않는다(바꿔야 한다면 별도로 논의하고 명시적으로 기록).
SUCCESS_CRITERIA = {
    "min_trades": 30,
    "sharpe_meaningful": 1.0,
    "sharpe_review": 0.5,
    "mdd_limit_pct": -20,
}

# MDD는 Phase 2 Risk Engine(포지션 사이징)이 들어오기 전까지 참고용이다.
# 지금 계산은 모든 종목의 거래를 청산일 순으로 이어붙여 매번 자산 전액을
# 재투자한다고 가정하는 방식이라, 실제로 자금을 나눠 동시 보유하는 포트폴리오의
# 낙폭보다 훨씬 크게 나온다.
MDD_CAVEAT = "포지션 사이징 미반영 참고용 수치 - Phase 2 Risk Engine 도입 후 재계산 예정"

MA_SHORT = 20               # 골든크로스 단기 이동평균
MA_LONG = 60                # 골든크로스 장기 이동평균
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 25    # 이 미만이면 "추세 없음"으로 후보 제외
RSI_ENTRY_OVERBOUGHT = 75   # 추세 신호가 떴어도 이미 과열이면 진입 보류

REGIME_WINDOW = 60          # 국면 판정에 쓰는 추세 관찰 기간(일)
REGIME_THRESHOLD_PCT = 10   # 이 구간 수익률을 넘으면 상승장/하락장으로 분류
MAX_HOLD_MULTIPLIER = 2     # 예상 보유기간의 2배를 넘기면 타임스탑
TAKE_PROFIT_RSI = 70        # 보유 중 RSI 과열 구간 진입 시 익절(진입 게이트와는 별개)

DEFAULT_STOCK_TICKERS = US_STOCKS
CRYPTO_UNIVERSE_CAP = 80    # scan_crypto가 보는 것과 동일한 상한(get_all_krw_markets()[:80])
UPBIT_MARKET_SLEEP = 0.1    # 크립토 종목 사이 추가 유예(업비트 rate limit 배려)

# 코스피/코스닥 시가총액 상위권 스냅샷(정적 목록). 토스 API로 실시간 시총 랭킹을
# 가져올 수 있게 되면 동적 스캔으로 교체할 잠정 목록 — 상장폐지/합병 등으로 일부
# 종목이 조회 실패할 수 있으나, 기존 try/except가 그런 종목을 조용히 건너뛴다.
KRX_MARKET_CAP_TOP = [
    "005930", "000660", "373220", "207940", "005380", "005490", "006400", "051910",
    "035420", "000270", "105560", "055550", "012330", "035720", "068270", "028260",
    "066570", "096770", "032830", "003550", "015760", "034730", "086790", "010130",
    "009150", "042660", "196170", "000810", "316140", "024110",
    "247540", "086520", "328130", "240810", "041510", "112040", "039030", "068760",
]

WARMUP = MA_LONG + 5        # 골든크로스(60일선)+ADX 계산에 필요한 최소 선행 데이터 길이


def classify_regime(closes, i, window=REGIME_WINDOW):
    if i < window:
        return None
    past = closes[i - window]
    if past == 0:
        return None
    ret = (closes[i] - past) / past * 100
    if ret > REGIME_THRESHOLD_PCT:
        return "상승장"
    if ret < -REGIME_THRESHOLD_PCT:
        return "하락장"
    return "횡보장"


def apply_cost(price, asset_class, side):
    costs = TRADING_COSTS.get(asset_class, TRADING_COSTS["stock"])
    total_pct = (costs["fee_pct"] + costs["slippage_pct"]) / 100
    return price * (1 + total_pct) if side == "buy" else price * (1 - total_pct)


def load_candles(market, asset_class, count):
    if asset_class == "crypto":
        raw = get_krw_candles(market, count)
        return [
            {"date": c["candle_date_time_utc"][:10], "open": c["opening_price"],
             "high": c["high_price"], "low": c["low_price"], "close": c["trade_price"],
             "volume": c["candle_acc_trade_volume"]}
            for c in raw
        ]
    if asset_class == "krx":
        return get_krx_candles(market, count)
    return get_us_candles(market, count)


def simulate(market, asset_class, candles):
    """candles: 날짜 오름차순 OHLC dict 리스트({'open','high','low','close','date', ...})."""
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    dates = [c.get("date") for c in candles]

    trades = []
    position = None

    for i in range(WARMUP, len(closes)):
        window_closes = closes[:i + 1]
        window_highs = highs[:i + 1]
        window_lows = lows[:i + 1]
        price = closes[i]

        if position is None:
            # 메인 신호: 골든크로스 + 추세 강도(ADX)
            if not is_golden_cross(window_closes, MA_SHORT, MA_LONG):
                continue
            adx = calc_adx(window_highs, window_lows, window_closes, ADX_PERIOD)
            if adx < ADX_TREND_THRESHOLD:
                continue

            # 보조 필터: RSI/볼린저는 진입 타이밍만 확인(이미 과열이면 보류)
            rsi = calc_rsi(window_closes)
            upper, _, _ = calc_bollinger(window_closes)
            if rsi >= RSI_ENTRY_OVERBOUGHT or price > upper:
                continue

            expected_days = estimate_holding_period(window_closes)
            strategy_type = classify_strategy(expected_days)
            position = {
                "entry_index": i,
                "entry_price": apply_cost(price, asset_class, "buy"),
                "entry_date": dates[i],
                "strategy_type": strategy_type,
                "expected_days": expected_days,
                "regime": classify_regime(closes, i),
                "entry_adx": round(adx, 1),
            }
            continue

        days_held = i - position["entry_index"]
        current_return = (price - position["entry_price"]) / position["entry_price"] * 100
        stop_threshold = HARD_STOP_LOSS.get(position["strategy_type"], -10)
        rsi = calc_rsi(window_closes)

        exit_reason = None
        if current_return <= stop_threshold:
            exit_reason = "hard_stop"
        elif rsi >= TAKE_PROFIT_RSI:
            exit_reason = "rsi_overbought"
        elif days_held >= position["expected_days"] * MAX_HOLD_MULTIPLIER:
            exit_reason = "time_stop"

        is_last_day = i == len(closes) - 1
        if exit_reason or is_last_day:
            exit_price = apply_cost(price, asset_class, "sell")
            final_return = (exit_price - position["entry_price"]) / position["entry_price"] * 100
            trades.append({
                "market": market, "asset_class": asset_class,
                "strategy_type": position["strategy_type"], "regime": position["regime"],
                "entry_index": position["entry_index"], "entry_date": position["entry_date"],
                "entry_adx": position["entry_adx"],
                "exit_date": dates[i], "days_held": days_held,
                "return_pct": round(final_return, 3),
                "exit_reason": exit_reason or "end_of_data",
            })
            position = None

    return trades


def compute_metrics(trades):
    if not trades:
        return {"trade_count": 0, "win_rate_pct": None, "avg_return_pct": None,
                "sharpe_like": None, "mdd_pct": None}

    returns = [t["return_pct"] for t in trades]
    win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
    avg_return = sum(returns) / len(returns)
    variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
    std = variance ** 0.5
    sharpe_like = (avg_return / std) if std > 0 else 0.0

    equity, peak, mdd = 1.0, 1.0, 0.0
    for t in sorted(trades, key=lambda t: (t["exit_date"] or "", t["entry_index"])):
        equity *= (1 + t["return_pct"] / 100)
        peak = max(peak, equity)
        mdd = min(mdd, (equity - peak) / peak * 100)

    return {
        "trade_count": len(trades),
        "win_rate_pct": round(win_rate, 2),
        "avg_return_pct": round(avg_return, 2),
        "sharpe_like": round(sharpe_like, 3),
        "mdd_pct": round(mdd, 2),
    }


def evaluate_success(metrics):
    if metrics["trade_count"] < SUCCESS_CRITERIA["min_trades"]:
        return f"표본 부족 ({metrics['trade_count']}건 < 최소 {SUCCESS_CRITERIA['min_trades']}건) - 판단 보류"

    sharpe = metrics["sharpe_like"]
    if sharpe >= SUCCESS_CRITERIA["sharpe_meaningful"]:
        verdict = f"샤프 유사 지표 {sharpe} - 유의미"
    elif sharpe < SUCCESS_CRITERIA["sharpe_review"]:
        verdict = f"샤프 유사 지표 {sharpe} - 규칙 재검토 필요"
    else:
        verdict = f"샤프 유사 지표 {sharpe} - 애매(추가 관찰 필요)"

    return f"{verdict} / MDD {metrics['mdd_pct']}%({MDD_CAVEAT})"


def group_metrics(trades, key):
    groups = {}
    for t in trades:
        groups.setdefault(t.get(key) or "미분류", []).append(t)
    return {k: compute_metrics(v) for k, v in groups.items()}


def run_instrument(market, asset_class, count):
    candles = load_candles(market, asset_class, count)
    if len(candles) < WARMUP + 10:
        print(f"⚠️ {market}: 데이터 {len(candles)}건 - 백테스트하기엔 부족해 건너뜀")
        return None
    trades = simulate(market, asset_class, candles)
    split_index = int(len(candles) * 0.7)
    return {
        "candle_count": len(candles),
        "trades": trades,
        "train_trades": [t for t in trades if t["entry_index"] < split_index],
        "val_trades": [t for t in trades if t["entry_index"] >= split_index],
    }


def main():
    parser = argparse.ArgumentParser(description="QuanTrade 백테스트 엔진 (Phase 1, 추세추종)")
    parser.add_argument("--crypto", nargs="*", default=None,
                         help=f"생략하면 scan_crypto와 동일하게 업비트 KRW마켓 최대 {CRYPTO_UNIVERSE_CAP}개를 동적으로 사용")
    parser.add_argument("--stocks", nargs="*", default=DEFAULT_STOCK_TICKERS)
    parser.add_argument("--krx", nargs="*", default=None,
                         help="생략하면 코스피/코스닥 시가총액 상위 스냅샷(KRX_MARKET_CAP_TOP)을 사용. 예: --krx 005930 373220")
    parser.add_argument("--count", type=int, default=1500, help="KRX/미국주식 일봉 개수(기본 약 6년치)")
    parser.add_argument("--crypto-count", type=int, default=5000,
                         help="크립토 일봉 개수 - 상장 시점까지 최대한 확보하도록 넉넉히 잡고, 실제로는 페이지네이션이 상장일에서 자연히 멈춤")
    parser.add_argument("--out", default="backtest_report.json")
    args = parser.parse_args()

    crypto_markets = args.crypto if args.crypto is not None else get_all_krw_markets()[:CRYPTO_UNIVERSE_CAP]
    krx_tickers = args.krx if args.krx is not None else KRX_MARKET_CAP_TOP

    universe = (
        [(m, "crypto") for m in crypto_markets]
        + [(m, "stock") for m in args.stocks]
        + [(m, "krx") for m in krx_tickers]
    )
    print(f"유니버스: 크립토 {len(crypto_markets)} / 미국주식 {len(args.stocks)} / KRX {len(krx_tickers)}")

    all_trades, all_train, all_val, per_instrument = [], [], [], []

    for market, asset_class in universe:
        count = args.crypto_count if asset_class == "crypto" else args.count
        try:
            result = run_instrument(market, asset_class, count)
        except Exception as e:
            print(f"⚠️ {market} 데이터 조회/시뮬레이션 실패: {e}")
            continue
        finally:
            if asset_class == "crypto":
                time.sleep(UPBIT_MARKET_SLEEP)  # 업비트 rate limit 배려(80개 마켓 연속 조회)
        if not result:
            continue
        per_instrument.append({
            "market": market, "asset_class": asset_class,
            "candle_count": result["candle_count"], "trade_count": len(result["trades"]),
        })
        all_trades += result["trades"]
        all_train += result["train_trades"]
        all_val += result["val_trades"]

    overall = {
        "all": compute_metrics(all_trades),
        "train": compute_metrics(all_train),
        "validation": compute_metrics(all_val),
    }

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "strategy": {
            "main_signal": f"MA{MA_SHORT}/MA{MA_LONG} 골든크로스 + ADX>={ADX_TREND_THRESHOLD}",
            "timing_filter": f"RSI<{RSI_ENTRY_OVERBOUGHT} and price<=볼린저상단",
            "exit": "하드손절 / RSI과열({}) / 타임스탑(예상보유기간x{})".format(TAKE_PROFIT_RSI, MAX_HOLD_MULTIPLIER),
        },
        "universe": [f"{m}({a})" for m, a in universe],
        "success_criteria": SUCCESS_CRITERIA,
        "mdd_caveat": MDD_CAVEAT,
        "instruments": per_instrument,
        "overall": overall,
        "by_regime": group_metrics(all_trades, "regime"),
        "by_strategy_type": group_metrics(all_trades, "strategy_type"),
        "verdict": {
            "all": evaluate_success(overall["all"]),
            "train": evaluate_success(overall["train"]),
            "validation": evaluate_success(overall["validation"]),
        },
    }

    save_json(args.out, report)

    print(f"\n총 {len(all_trades)}건 거래 (훈련 {len(all_train)} / 검증 {len(all_val)})")
    print(f"훈련구간 지표: {overall['train']}")
    print(f"검증구간 지표: {overall['validation']}")
    print(f"훈련구간 판정: {report['verdict']['train']}")
    print(f"검증구간 판정: {report['verdict']['validation']}")
    print(f"리포트 저장 완료: {args.out}")


if __name__ == "__main__":
    main()
