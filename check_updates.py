from datetime import datetime
from analyze_lib import *

PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "trade_history.json"
PENDING_FILE = "pending_actions.json"
OFFSET_FILE = "telegram_offset.json"
LAST_REPORT_FILE = "last_report.json"


def get_updates(offset):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 5}
    return requests.get(url, params=params, timeout=10).json()


def handle_approve(action_id, portfolio, history, pending):
    for action in pending["actions"]:
        if action["id"] == action_id and action["status"] == "waiting":
            if action["type"] == "sell":
                market = action["market"]
                pos = next((p for p in portfolio["positions"] if p["market"] == market), None)
                if pos:
                    price = get_current_price(pos.get("asset_class", "crypto"), market)
                    ret = (price - pos["entry_price"]) / pos["entry_price"] * 100
                    portfolio["cash"] += pos["amount_krw"] * (1 + ret / 100)
                    portfolio["positions"] = [p for p in portfolio["positions"] if p["market"] != market]
                    history["trades"].append({
                        "market": market, "asset_class": pos.get("asset_class", "crypto"),
                        "strategy_type": pos.get("strategy_type", "스윙"),
                        "entry_date": pos["entry_date"], "exit_date": datetime.now().strftime("%Y-%m-%d"),
                        "return_pct": ret
                    })
                    action["status"] = "approved"
                    send_telegram(f"✅ 승인 완료: {market} 매도 처리됨 ({ret:+.2f}%)")
            elif action["type"] == "buy":
                portfolio["positions"].append({
                    "market": action["market"], "asset_class": action["asset_class"],
                    "strategy_type": action["strategy_type"], "entry_price": action["entry_price"],
                    "entry_date": datetime.now().strftime("%Y-%m-%d"),
                    "expected_days": action["expected_days"], "amount_krw": action["amount_krw"]
                })
                portfolio["cash"] -= action["amount_krw"]
                action["status"] = "approved"
                send_telegram(f"✅ 승인 완료: {action['market']} 매수 처리됨 ({action['amount_krw']:,.0f}원)")
            return True
    return False



def handle_reject(action_id, pending):
    for action in pending["actions"]:
        if action["id"] == action_id and action["status"] == "waiting":
            action["status"] = "rejected"
            send_telegram(f"❌ 거절됨: {action['market']} 매도 취소, 계속 보유")
            return True
    return False


def handle_keep(market, portfolio):
    for pos in portfolio["positions"]:
        if pos["market"] == market:
            pos["conviction"] = True
            send_telegram(f"💎 {market} 확신 보유로 지정됨 (자동매매 대상에서 제외)")
            return True
    send_telegram(f"⚠️ {market} 종목을 보유 목록에서 찾을 수 없음")
    return False


def handle_unkeep(market, portfolio):
    for pos in portfolio["positions"]:
        if pos["market"] == market:
            pos["conviction"] = False
            send_telegram(f"🔓 {market} 확신 보유 해제됨 (자동매매 대상으로 복귀)")
            return True
    return False


def refresh_last_report(portfolio, pending):
    """승인/거절/keep 처리 후 웹 대시보드용 last_report.json도 최신 상태로 갱신"""
    last_report = load_json(LAST_REPORT_FILE, {})
    last_report["pending"] = [a for a in pending["actions"] if a["status"] == "waiting"]
    last_report["positions"] = []
    for p in portfolio["positions"]:
        try:
            price = get_current_price(p.get("asset_class", "crypto"), p["market"])
            ret = (price - p["entry_price"]) / p["entry_price"] * 100
        except Exception:
            ret = p.get("current_return", 0)
        last_report["positions"].append({
            "market": p["market"], "asset_class": p.get("asset_class", "crypto"),
            "strategy_type": p.get("strategy_type", "스윙"), "amount_krw": p["amount_krw"],
            "current_return": ret, "conviction": p.get("conviction", False)
        })
    last_report["cash"] = portfolio["cash"]
    save_json(LAST_REPORT_FILE, last_report)


def run():
    offset_data = load_json(OFFSET_FILE, {"last_update_id": 0})
    portfolio = load_json(PORTFOLIO_FILE, {"cash": 100000, "positions": []})
    history = load_json(HISTORY_FILE, {"trades": []})
    pending = load_json(PENDING_FILE, {"actions": []})

    updates = get_updates(offset_data["last_update_id"] + 1)
    if not updates.get("ok"):
        print("업데이트 조회 실패:", updates)
        save_json(OFFSET_FILE, offset_data)
        return

    changed = False
    for update in updates.get("result", []):
        offset_data["last_update_id"] = update["update_id"]
        message = update.get("message", {})
        text = message.get("text", "").strip()
        if not text:
            continue

        parts = text.split()
        cmd = parts[0].lower()

        if cmd == "/approve" and len(parts) > 1:
            if handle_approve(parts[1], portfolio, history, pending):
                changed = True
        elif cmd == "/reject" and len(parts) > 1:
            if handle_reject(parts[1], pending):
                changed = True
        elif cmd == "/keep" and len(parts) > 1:
            if handle_keep(parts[1], portfolio):
                changed = True
        elif cmd == "/unkeep" and len(parts) > 1:
            if handle_unkeep(parts[1], portfolio):
                changed = True
        elif cmd == "/status":
            lines = [f"- {p['market']}: {p.get('current_return',0):+.2f}% {'💎확신' if p.get('conviction') else ''}" for p in portfolio["positions"]]
            send_telegram("📊 현재 포지션\n" + "\n".join(lines) if lines else "보유 포지션 없음")

    if changed:
        save_json(PORTFOLIO_FILE, portfolio)
        save_json(HISTORY_FILE, history)
        save_json(PENDING_FILE, pending)
        refresh_last_report(portfolio, pending)

    save_json(OFFSET_FILE, offset_data)


if __name__ == "__main__":
    run()
