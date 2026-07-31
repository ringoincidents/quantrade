from datetime import datetime
from analyze_lib import *

PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "trade_history.json"
PENDING_FILE = "pending_actions.json"
TOTAL_BUDGET = 100000
MIN_CASH_RESERVE_RATIO = 0.2


def run():
    portfolio = load_json(PORTFOLIO_FILE, {"cash": TOTAL_BUDGET, "positions": []})
    history = load_json(HISTORY_FILE, {"trades": []})
    pending = load_json(PENDING_FILE, {"actions": []})
    today = datetime.now().strftime("%Y-%m-%d")
    report = [f"📅 {today} 통합 포트폴리오 리포트", ""]

    for pos in portfolio["positions"]:
        try:
            asset_class = pos.get("asset_class", "crypto")
            price = get_current_price(asset_class, pos["market"])
            pos["current_price"] = price
            pos["current_return"] = (price - pos["entry_price"]) / pos["entry_price"] * 100
        except Exception as e:
            pos["current_price"] = pos.get("entry_price", 0)
            pos["current_return"] = 0
            report.append(f"⚠️ {pos['market']} 가격 조회 실패: {e}")

    held_all = [p["market"] for p in portfolio["positions"]]
    crypto_cands = scan_crypto(exclude=held_all, top_n=3)
    stock_cands = scan_stocks(exclude=held_all, top_n=2)
    all_cands = crypto_cands + stock_cands

    news_by_market = {}
    for c in all_cands:
        c["expected_days"] = estimate_holding_period(c["raw_closes"])
        c["strategy_type"] = classify_strategy(c["expected_days"])
        news_by_market[c["market"]] = get_news_sentiment(c["market"].replace("KRW-", ""))

    ai_result = ask_claude_decision(portfolio["positions"], all_cands, news_by_market)
    report.append("🤖 AI 시장 요약")
    report.append(ai_result.get("market_summary", "요약 없음"))
    report.append("")

    decisions = ai_result.get("decisions", [])
    decision_map = {d["market"]: d for d in decisions}

    still_holding = []
    for pos in portfolio["positions"]:
        market = pos["market"]

        if pos.get("conviction"):
            report.append(f"💎 확신 보유: {market} {pos['current_return']:+.2f}% (자동매매 대상 아님)")
            still_holding.append(pos)
            continue

        strat = pos.get("strategy_type", "스윙")
        threshold = HARD_STOP_LOSS.get(strat, -10)

        if pos["current_return"] <= threshold:
            ret = pos["current_return"]
            portfolio["cash"] += pos["amount_krw"] * (1 + ret / 100)
            history["trades"].append({
                "market": market, "asset_class": pos.get("asset_class", "crypto"),
                "strategy_type": strat, "entry_date": pos["entry_date"],
                "exit_date": today, "return_pct": ret
            })
            report.append(f"🛑 하드손절 자동실행: {market} ({ret:+.2f}%, {strat} 기준 {threshold}% 이하)")
            continue

        decision = decision_map.get(market)
        days_held = (datetime.now() - datetime.strptime(pos["entry_date"], "%Y-%m-%d")).days

        if decision and decision.get("action") == "매도":
            action_id = f"{market}_{today}"
            already_pending = any(a["id"] == action_id for a in pending["actions
