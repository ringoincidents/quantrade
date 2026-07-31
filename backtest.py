"""QuanTrade 백테스트 엔진 (Phase 1, 종합계획서 v3 §5).

라이브 스캔(scan_crypto/scan_stocks)이 쓰는 진입 규칙(entry_score)과 하드손절
규칙(HARD_STOP_LOSS)을 과거 시세에 그대로 재현해 검증한다.

한계: 실거래에서 보유/매도는 매번 Claude에게 물어 결정하지만, 과거 시점의
AI 판단을 재현할 방법이 없다(비용·비결정성 문제). 이 엔진은 매도 쪽을
규칙 기반(하드손절 / RSI 과열 / 타임스탑)으로 근사한다 — Phase 2의 AI 확신도
캘리브레이션이 도입되면 이 근사를 교체해야 한다.
"""
import argparse
from datetime import datetime

from analyze_lib import (
    calc_rsi, entry_score, estimate_holding_period, classify_strategy,
    HARD_STOP_LOSS, TRADING_COSTS, US_STOCKS,
    get_krw_candles, get_us_closes, get_krx_candles, save_json,
)

# 종합계획서 v3 §4.3 — 결과가 나온 뒤 기준을 짜맞추는 것을 막기 위해 미리 박아둔
# 성공 기준. 사후에 임의로 바꾸지 않는다(바꿔야 한다면 별도로 논의하고 명시적으로 기록).
SUCCESS_CRITERIA = {
    "min_trades": 30,
    "sharpe_meaningful": 1.0,
    "sharpe_review": 0.5,
    "mdd_limit_pct": -20,
}

REGIME_WINDOW = 60          # 국면 판정에 쓰는 추세 관찰 기간(일)
REGIME_THRESHOLD_PCT = 10   # 이 구간 수익률을 넘으면 상승장/하락장으로 분류
MAX_HOLD_MULTIPLIER = 2     # 예상 보유기간의 2배를 넘기면 타임스탑
TAKE_PROFIT_RSI = 70        # RSI 과열 구간 진입 시 익절

DEFAULT_CRYPTO_MARKETS = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
DEFAULT_STOCK_TICKERS = US_STOCKS
WARMUP = 30                 # 지표 계산에 필요한 최소 선행 데이터 길이


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
            {"date": c["candle_date_time_utc"][:10], "close": c["trade_price"],
             "volume": c["candle_acc_trade_volume"]}
            for c in raw
        ]
    if asset_class == "krx":
        return get_krx_candles(market, count)
    return [{"date": None, "close": c} for c in get_us_closes(market, count)]


def simulate(market, asset_class, candles):
    """candles: 날짜 오름차순 dict 리스트({'close': ..., 'volume': ...(선택), 'date': ...})."""
    closes = [c["close"] for c in candles]
    has_volume = all("volume" in c for c in candles)
    volumes = [c["volume"] for c in candles] if has_volume else None
    dates = [c.get("date") for c in candles]

    trades = []
    position = None

    for i in range(WARMUP, len(closes)):
        window_closes = closes[:i + 1]
        window_volumes = volumes[:i + 1] if volumes else None
        price = closes[i]

        if position is None:
            score, _ = entry_score(window_closes, window_volumes)
            threshold = 3 if has_volume else 2
            if score >= threshold:
                expected_days = estimate_holding_period(window_closes)
                strategy_type = classify_strategy(expected_days)
                position = {
                    "entry_index": i,
                    "entry_price": apply_cost(price, asset_class, "buy"),
                    "entry_date": dates[i],
                    "strategy_type": strategy_type,
                    "expected_days": expected_days,
                    "regime": classify_regime(closes, i),
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

    verdicts = []
    sharpe = metrics["sharpe_like"]
    if sharpe >= SUCCESS_CRITERIA["sharpe_meaningful"]:
        verdicts.append(f"샤프 유사 지표 {sharpe} - 유의미")
    elif sharpe < SUCCESS_CRITERIA["sharpe_review"]:
        verdicts.append(f"샤프 유사 지표 {sharpe} - 규칙 재검토 필요")
    else:
        verdicts.append(f"샤프 유사 지표 {sharpe} - 애매(추가 관찰 필요)")

    mdd = metrics["mdd_pct"]
    if mdd < SUCCESS_CRITERIA["mdd_limit_pct"]:
        verdicts.append(f"MDD {mdd}% - 리스크 규칙 재점검 필요")
    else:
        verdicts.append(f"MDD {mdd}% - 한도 이내")

    return " / ".join(verdicts)


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
    parser = argparse.ArgumentParser(description="QuanTrade 백테스트 엔진 (Phase 1)")
    parser.add_argument("--crypto", nargs="*", default=DEFAULT_CRYPTO_MARKETS)
    parser.add_argument("--stocks", nargs="*", default=DEFAULT_STOCK_TICKERS)
    parser.add_argument("--krx", nargs="*", default=[], help="예: --krx 005930 373220")
    parser.add_argument("--count", type=int, default=750, help="일봉 개수(기본 약 3년치, 계획서 §4.2)")
    parser.add_argument("--out", default="backtest_report.json")
    args = parser.parse_args()

    universe = (
        [(m, "crypto") for m in args.crypto]
        + [(m, "stock") for m in args.stocks]
        + [(m, "krx") for m in args.krx]
    )

    all_trades, all_train, all_val, per_instrument = [], [], [], []

    for market, asset_class in universe:
        try:
            result = run_instrument(market, asset_class, args.count)
        except Exception as e:
            print(f"⚠️ {market} 데이터 조회/시뮬레이션 실패: {e}")
            continue
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
        "universe": [f"{m}({a})" for m, a in universe],
        "success_criteria": SUCCESS_CRITERIA,
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
    print(f"전체 지표: {overall['all']}")
    print(f"훈련구간 판정: {report['verdict']['train']}")
    print(f"검증구간 판정: {report['verdict']['validation']}")
    print(f"리포트 저장 완료: {args.out}")


if __name__ == "__main__":
    main()
