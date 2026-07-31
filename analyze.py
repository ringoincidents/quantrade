from datetime import datetime
from analyze_lib import *

PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "trade_history.json"
PENDING_FILE = "pending_actions.json"
TOTAL_BUDGET = 100000
MIN_CASH_RESERVE_RATIO = 0.2
LARGE_POSITION_THRESHOLD = 0.25  # 전체 자산의 25% 이상이면 승인 필요


def needs_approval(pos, total_assets):
    if pos.get("strategy_type") == "장기":
        return True
    if pos.get("asset_class") in ("stock", "krx"):
        return True
    if total_assets > 0 and (pos["amount_krw"] / total_assets) >= LARGE_POSITION_THRESHOLD:
        return True
    return False


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

    total_assets = portfolio["cash"] + sum(p["amount_krw"] for p in portfolio["positions"])

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

        # 하드 손절은 조건 무관 항상 즉시 자동 실행
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
            if needs_approval(pos, total_assets):
                # 장기/주식/대형 비중 → 승인 대기
                action_id = f"{market}_{today}"
                already_pending = any(a["id"] == action_id for a in pending["actions"])
                if not already_pending:
                    pending["actions"].append({
                        "id": action_id, "type": "sell", "market": market,
                        "reasoning": decision.get("reasoning", "-"), "status": "waiting"
                    })
                    reason_tag = "장기전략" if strat == "장기" else ("주식" if pos.get("asset_class") in ("stock", "krx") else "대형비중")
                    report.append(f"⏳ 매도 승인 대기 [{reason_tag}]: {market} ({pos['current_return']:+.2f}%)")
                    report.append(f"   AI 이유: {decision.get('reasoning','-')}")
                    report.append(f"   👉 승인 /approve {action_id} / 거절 /reject {action_id}")
                still_holding.append(pos)
            else:
                # 단타/스윙(소형 비중, 코인) → 즉시 자동 매도
                ret = pos["current_return"]
                portfolio["cash"] += pos["amount_krw"] * (1 + ret / 100)
                history["trades"].append({
                    "market": market, "asset_class": pos.get("asset_class", "crypto"),
                    "strategy_type": strat, "entry_date": pos["entry_date"],
                    "exit_date": today, "return_pct": ret
                })
                report.append(f"✅ 자동 매도 [{strat}]: {market} ({ret:+.2f}%)")
                report.append(f"   이유: {decision.get('reasoning','-')}")
        else:
            report.append(f"📌 보유 유지: {market} ({days_held}일) {pos['current_return']:+.2f}%")
            if decision:
                report.append(f"   AI 코멘트: {decision.get('reasoning','-')}")
            still_holding.append(pos)

    portfolio["positions"] = still_holding

    min_cash = TOTAL_BUDGET * MIN_CASH_RESERVE_RATIO
    available = portfolio["cash"] - min_cash

    for c in all_cands:
        decision = decision_map.get(c["market"])
        if decision and decision.get("action") in ("매수", "비중조정") and available > 0:
            weight_pct = decision.get("target_weight_pct") or 20
            amount = round(available * (weight_pct / 100))
            amount = min(amount, available)
            if amount <= 0:
                continue

            # 매수도 대형 비중이거나 주식이면 승인 필요
            temp_pos = {"asset_class": c["asset_class"], "strategy_type": c["strategy_type"], "amount_krw": amount}
            if needs_approval(temp_pos, total_assets):
                action_id = f"BUY_{c['market']}_{today}"
                already_pending = any(a["id"] == action_id for a in pending["actions"])
                if not already_pending:
                    pending["actions"].append({
                        "id": action_id, "type": "buy", "market": c["market"],
                        "amount_krw": amount, "entry_price": c["price"],
                        "strategy_type": c["strategy_type"], "asset_class": c["asset_class"],
                        "expected_days": c["expected_days"],
                        "reasoning": decision.get("reasoning", "-"), "status": "waiting"
                    })
                    reason_tag = "장기전략" if c["strategy_type"] == "장기" else ("주식" if c["asset_class"] in ("stock", "krx") else "대형비중")
                    report.append("")
                    report.append(f"⏳ 매수 승인 대기 [{reason_tag}]: {c['market']} (비중 {weight_pct}%, {amount:,.0f}원)")
                    report.append(f"   AI 이유: {decision.get('reasoning','-')}")
                    report.append(f"   👉 승인 /approve {action_id} / 거절 /reject {action_id}")
            else:
                portfolio["positions"].append({
                    "market": c["market"], "asset_class": c["asset_class"],
                    "strategy_type": c["strategy_type"], "entry_price": c["price"],
                    "entry_date": today, "expected_days": c["expected_days"], "amount_krw": amount
                })
                portfolio["cash"] -= amount
                available -= amount
                report.append("")
                report.append(f"🆕 자동 매수 [{c['strategy_type']}]: {c['market']} (비중 {weight_pct}%, {amount:,.0f}원)")
                report.append(f"   이유: {decision.get('reasoning','-')}")

    report.append("")
    report.append(f"💰 현금: {portfolio['cash']:,.0f}원 / 보유 {len(portfolio['positions'])}개")
    waiting_count = len([a for a in pending["actions"] if a["status"] == "waiting"])
    if waiting_count:
        report.append(f"⏳ 승인 대기 중 {waiting_count}건")

    last_report = {
        "date": today,
        "market_summary": ai_result.get("market_summary", ""),
        "positions": [
            {
                "market": p["market"], "asset_class": p.get("asset_class", "crypto"),
                "strategy_type": p.get("strategy_type", "스윙"), "amount_krw": p["amount_krw"],
                "current_return": p.get("current_return", 0), "conviction": p.get("conviction", False)
            } for p in portfolio["positions"]
        ],
        "pending": [a for a in pending["actions"] if a["status"] == "waiting"],
        "cash": portfolio["cash"]
    }
    save_json("last_report.json", last_report)

    save_json(PORTFOLIO_FILE, portfolio)
    save_json(HISTORY_FILE, history)
    save_json(PENDING_FILE, pending)
    return "\n".join(report)


if __name__ == "__main__":
    try:
        result = run()
        print(result)
        send_telegram(result)
    except Exception as e:
        send_telegram(f"❌ 실행 오류: {e}")
