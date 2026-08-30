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
            # [v3.2] 예측 경로가 비활성이면 그 산물인 매수/매도 승인도 집행하지 않는다.
            # analyze.py가 신규 pending을 더 만들지 않더라도 **이전에 쌓인 대기 건이
            # 남아 있어서**, 이 가드가 없으면 기각된 신호가 뒤늦게 체결될 수 있다.
            # /reject는 그대로 동작한다 — 제안을 치우는 건 언제나 안전하다.
            if not PREDICTION_ENABLED:
                send_telegram(
                    f"🔬 {action_id} — 예측 경로가 중단되어(v3.2, §2.1 게이트 미통과) "
                    "승인 집행이 비활성입니다. 이 건은 종료된 연구의 잔여 제안입니다. "
                    "정리하려면 /reject 를 쓰세요."
                )
                return True
            if action.get("target_account") == "real":
                # 실계좌는 조회 전용 — 주문 API 자체가 없다. 게이트가 꺼져 있으면(기본값)
                # 승인해도 아무것도 실행되지 않는다는 걸 명시적으로 알리기만 하고,
                # status는 "waiting"으로 유지해 반복 승인 시도도 안전하게 no-op이 되게 한다.
                label = "매도" if action.get("action_type") == "sell" else "비중조정"
                name = action.get("name", action.get("market"))
                if action.get("dry_run", True):
                    send_telegram(f"🔒 [모의] {name} {label} — dry-run 상태, 실행되지 않음 (AI_SUGGESTION_DRY_RUN=true)")
                else:
                    send_telegram(f"⚠️ {name} {label} — 실계좌 주문 실행은 아직 구현되어 있지 않습니다 (조회 전용)")
                return True
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
            if action.get("target_account") == "real":
                label = "매도" if action.get("action_type") == "sell" else "비중조정"
                name = action.get("name", action.get("market"))
                send_telegram(f"❌ 거절됨: {name} 실계좌 {label} 제안 취소")
            else:
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


# ── 매매 사후 점검 리포트 (Layer 3, 2026-08-10) ─────────────────────────────
# 온디맨드 트리거 — 배치(post_trade_review.yml, 변동 있을 때만)와 같은
# build_report()를 쓰지만, 여기는 변동 여부와 무관하게 항상 생성한다. 응답
# 메시지는 사람이 요청한 것에 대한 답장이지 자동 푸시가 아니다(지시서 §2).

def handle_review():
    import post_trade_review
    report = post_trade_review.run_ondemand()
    send_telegram(post_trade_review.render_telegram(report))
    return True


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


# ── 규칙 기반 자동실행 킬스위치 (2026-08-04) ────────────────────────────────
# 자동실행을 즉시 멈추는 수단. autoexec.py는 실행 직전에 매번 이 상태를 확인하며,
# 한 번 걸리면 /autoexec_start로 명시적으로 풀기 전까지 유지된다 — 재실행이나
# 워크플로 재시작으로 저절로 풀리지 않는다.

def handle_autoexec_stop():
    import autoexec
    st = autoexec.load_state()
    already = autoexec.kill_switch_engaged(st)
    st = autoexec.engage_kill_switch(st)
    autoexec.save_json(autoexec.STATE_FILE, st)
    send_telegram(
        ("🛑 자동실행 킬스위치 작동 (이미 작동 중이었음)" if already else "🛑 자동실행 킬스위치 작동")
        + f"\n중단 시각: {st['stopped_at']}"
        "\n이후 어떤 규칙도 실행되지 않습니다. 판정과 로깅은 계속됩니다."
        "\n해제하려면 /autoexec_start 를 보내세요."
    )
    return True


def handle_autoexec_start():
    import autoexec
    st = autoexec.load_state()
    if not autoexec.kill_switch_engaged(st):
        send_telegram("ℹ️ 킬스위치는 이미 해제 상태입니다.")
        return False
    st = autoexec.release_kill_switch(st)
    autoexec.save_json(autoexec.STATE_FILE, st)
    send_telegram("▶️ 자동실행 킬스위치 해제. 규칙 실행이 다시 허용됩니다.\n"
                  "(RULE_BASED_AUTOEXEC_ENABLED가 false면 여전히 판정만 수행합니다.)")
    return True


def handle_autoexec_status():
    import autoexec
    from analyze_lib import RULE_BASED_AUTOEXEC_ENABLED
    st = autoexec.load_state()
    log = load_json(autoexec.LOG_FILE, {"decisions": []})
    today = autoexec.today_kst()
    todays = [d for d in log["decisions"] if d.get("date") == today]
    lines = [
        "🤖 자동실행 상태",
        f"· 킬스위치: {'🛑 작동 중' if autoexec.kill_switch_engaged(st) else '해제됨'}",
        f"· 활성 플래그: {'true' if RULE_BASED_AUTOEXEC_ENABLED else 'false (판정만)'}",
        f"· 유예기간: {'적용 중 (규칙별 1일 1회)' if autoexec.in_grace_period(st) else '해제됨'}",
        f"· 최초 활성화: {st.get('first_enabled_at') or '없음'}",
        f"· 오늘 판정 로그: {len(todays)}건 (누적 {len(log['decisions'])}건)",
    ]
    send_telegram("\n".join(lines))
    return True


# ── 사전 승인 흐름 (2026-08-04) ─────────────────────────────────────────────
# 규칙이 발동해도 바로 실행하지 않는다. 심층분석 리포트를 보고 사용자가 승인해야
# 실행 단계로 넘어간다.

def handle_autoexec_report(approval_id):
    """발동 건의 심층분석 리포트를 다시 보낸다."""
    import autoexec, rule_trigger_report
    reports = load_json(autoexec.REPORTS_FILE, {"reports": {}})
    rep = reports["reports"].get(approval_id)
    if not rep:
        send_telegram(f"❓ {approval_id} 리포트를 찾을 수 없습니다.")
        return False
    send_telegram(rule_trigger_report.render_text(rep))
    return True


def handle_autoexec_approve(approval_id):
    import autoexec
    st = autoexec.load_state()
    ap = autoexec.find_approval(st, approval_id)
    if not ap:
        send_telegram(f"❓ {approval_id} 승인 대기 건을 찾을 수 없습니다.")
        return False
    if ap["status"] != "waiting":
        send_telegram(f"ℹ️ {approval_id}는 이미 '{ap['status']}' 상태입니다.")
        return False
    if autoexec.kill_switch_engaged(st):
        send_telegram("🛑 킬스위치가 작동 중이라 승인해도 실행되지 않습니다. "
                      "해제하려면 /autoexec_start 를 보내세요.")
        return False

    try:
        autoexec.execute({"action": "sell", "symbol": ap["symbol"],
                          "quantity": ap["quantity"]})
        ap["status"] = "executed"
        msg = f"✅ 승인 실행: {ap['name']} {ap['quantity']}주 매도"
    except autoexec.OrderLayerUnavailable as e:
        ap["status"] = "approved_not_executed"
        msg = (f"⏸️ {ap['name']} {ap['quantity']}주 — 승인은 기록됐으나 실행되지 "
               f"않았습니다.\n{e}")
    except Exception as e:
        ap["status"] = "error"
        msg = f"❌ {ap['name']} 실행 오류: {e}"
    autoexec.save_json(autoexec.STATE_FILE, st)
    send_telegram(msg)
    return True


def handle_autoexec_reject(approval_id):
    import autoexec
    st = autoexec.load_state()
    ap = autoexec.find_approval(st, approval_id)
    if not ap:
        send_telegram(f"❓ {approval_id} 승인 대기 건을 찾을 수 없습니다.")
        return False
    if ap["status"] != "waiting":
        send_telegram(f"ℹ️ {approval_id}는 이미 '{ap['status']}' 상태입니다.")
        return False
    ap["status"] = "rejected"
    autoexec.save_json(autoexec.STATE_FILE, st)
    send_telegram(f"🚫 {ap['name']} {ap['quantity']}주 매도 제안을 취소했습니다.")
    return True


# ── 정책 이탈 예외 승인 (A6, 2026-08-30) ────────────────────────────────────
# portfolio_report.py의 role_gap(역할 배분 목표 초과 사실)을 사람이 보고
# "지금은 예외로 둔다"고 승인한 것만 기록한다. 새 매매 판단이나 자동 조치가
# 아니다 — policy_exception.py의 불변 저널에 사실을 남기고 끝난다.

def handle_approve_exception(role, reason, telegram_from):
    import portfolio_report, policy_exception
    report = load_json(portfolio_report.REPORT_FILE, None)
    if not report or not report.get("role_gap"):
        send_telegram("❓ 역할 배분 정보가 없습니다 (portfolio_report.py가 먼저 실행돼야 합니다).")
        return
    rows = report["role_gap"]["rows"]
    row = next((r for r in rows if r["role"] == role), None)
    if not row:
        valid = ", ".join(r["role"] for r in rows)
        send_telegram(f"❓ '{role}' 역할을 찾을 수 없습니다. 사용 가능: {valid}")
        return
    if row.get("gap_pct") is None or row["gap_pct"] >= 0:
        send_telegram(f"ℹ️ {row.get('label', role)}는 현재 목표 초과 상태가 아닙니다 — 예외 승인 대상이 아닙니다.")
        return
    if not reason:
        send_telegram("❓ 예외 사유를 함께 적어주세요: /approve_exception <역할> <사유>")
        return

    ident = telegram_from.get("username") or telegram_from.get("first_name") or "알수없음"
    approved_by = f"{ident} (id:{telegram_from.get('id', '알수없음')})"
    try:
        record = policy_exception.append_and_save(
            policy_exception.build_record(row, reason, approved_by))
    except policy_exception.AuditViolation as e:
        send_telegram(f"❌ 예외 사유에 금지된 표현이 포함되어 저장하지 않았습니다: {'; '.join(e.violations)}")
        return
    send_telegram(f"✅ 예외 승인 기록됨: {record['label']} 역할 배분 초과 "
                  f"(목표 {row['target_pct']:.1f}% / 실제 {row['actual_pct']:.1f}%)\n"
                  f"사유: {reason}\nID: {record['id']}")


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
        elif cmd == "/autoexec_stop":
            handle_autoexec_stop()
        elif cmd == "/autoexec_start":
            handle_autoexec_start()
        elif cmd == "/autoexec_status":
            handle_autoexec_status()
        elif cmd == "/autoexec_report" and len(parts) > 1:
            handle_autoexec_report(parts[1])
        elif cmd == "/autoexec_approve" and len(parts) > 1:
            handle_autoexec_approve(parts[1])
        elif cmd == "/autoexec_reject" and len(parts) > 1:
            handle_autoexec_reject(parts[1])
        elif cmd == "/approve_exception" and len(parts) > 1:
            handle_approve_exception(parts[1], " ".join(parts[2:]), message.get("from", {}))
        elif cmd == "/review":
            handle_review()
        elif cmd == "/status":
            # 2026-08-09 방향성 세션 지시: 폐기된 코인 모의투자 포지션은 /status
            # 출력에서 제외한다 — 시뮬레이션 자체는 손대지 않고 출력만 뺀다.
            lines = [f"- {p['market']}: {p.get('current_return',0):+.2f}% {'💎확신' if p.get('conviction') else ''}"
                     for p in portfolio["positions"] if p.get("asset_class", "crypto") != "crypto"]
            send_telegram("📊 현재 포지션\n" + "\n".join(lines) if lines else "보유 포지션 없음")

    if changed:
        save_json(PORTFOLIO_FILE, portfolio)
        save_json(HISTORY_FILE, history)
        save_json(PENDING_FILE, pending)
        refresh_last_report(portfolio, pending)

    save_json(OFFSET_FILE, offset_data)


if __name__ == "__main__":
    run()
