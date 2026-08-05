"""규칙 기반 포지션 관리 자동실행 (2026-08-04, 방향성 세션 정식 승인).

**매도/리밸런싱 전용이다. 매수 경로는 코드 구조상 존재하지 않는다** — 실행기가
`sell` 이외의 action을 받으면 예외를 던지며, 신규 매수 후보를 만드는 함수 자체가
이 파일에 없다(요구사항 3).

**세 규칙** (전부 결정론적 산술. AI 판단이 개입하지 않는다):
  1. 집중도 리밸런싱 — 종목 비중 > 30%면 초과분 매도, 1회 최대 해당 종목
     평가액의 30%.
  2. 손실 지속 손절 — 평가손익이 기준선 이하로 N일 지속되면 매도.
  3. 목표가 부분익절 — `target_prices.json`의 **사람이 수기 입력한** 목표가에
     도달하면 지정 비율만큼 부분 매도.

**목표가는 절대 AI가 계산·제안하지 않는다**(요구사항 2). 이 파일에는 Claude API
호출이 없고, self-test가 그 사실을 검사한다. 목표가는 사람이 JSON에 직접 적는
값이며, 코드는 읽어서 비교만 한다.

**승인 흐름 (2026-08-04 방향성 세션 수정)**: 원래 "즉시 실행 + 사후 통보"였으나
**"발동 시 심층분석 리포트 + 사전 승인"**으로 바뀌었다. 규칙이 발동하면 대상
종목의 리포트(`rule_trigger_report.generate()`)를 만들어 승인 대기로 올리고,
사용자가 `/autoexec_approve <id>`를 보낸 뒤에만 실행한다. 승인 없이
APPROVAL_TTL_DAYS가 지나면 만료된다 — 며칠 지난 판정으로 지금 체결하는 건
근거가 이미 낡았기 때문이다.

**안전장치**:
  - 킬스위치: `/autoexec_stop` 이후에는 어떤 규칙도 실행되지 않는다. 실행 직전에
    매번 확인하며, 해제는 `/autoexec_start`로만 가능하다(사고로 풀리지 않게).
  - 전량 로깅: 발동/미발동을 가리지 않고 모든 트리거 판정을 남긴다.
  - 사전 승인: 위 승인 흐름. 리포트를 보고 사람이 결정한다.
  - 초기 유예: 첫 GRACE_PERIOD_DAYS 동안 규칙별 1일 1회로 제한.

**주문 실행 계층은 아직 없다.** `place_sell_order()`는 토스 주문 API 스펙이
저장소에 없어 구현되지 않았고, 호출되면 실행하지 않고 "실행 불가"로 로깅한다 —
추측으로 엔드포인트/스키마를 지어내는 건 실계좌 주문에서 할 수 있는 일이 아니다.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone

from analyze_lib import load_json, save_json, send_telegram

REAL_PORTFOLIO_FILE = "real_portfolio.json"
TARGET_PRICES_FILE = "target_prices.json"
STATE_FILE = "autoexec_state.json"
LOG_FILE = "autoexec_log.json"
REPORTS_FILE = "autoexec_reports.json"
REPORT_STATE_FILE = "portfolio_report_state.json"   # 손실 지속일수 추적(리포트와 공유)

# 규칙 파라미터. 방향성 세션 확정 대상이며 결과를 보고 바꾸지 않는다.
CONCENTRATION_PCT = 30.0        # 이 비중을 넘으면 리밸런싱 대상
CONCENTRATION_MAX_SELL_PCT = 30.0  # 1회 매도 상한 = 해당 종목 평가액의 이 비율
LOSS_PCT = -50.0                # 손절 기준선
LOSS_SUSTAINED_DAYS = 60        # 기준선 이하 지속 일수
GRACE_PERIOD_DAYS = 7           # 초기 유예: 규칙별 1일 1회 제한
KST = timezone(timedelta(hours=9))

RULES = ("집중도리밸런싱", "손실지속손절", "목표가부분익절")

# [2026-08-04 방향성 세션 수정] 발동 시 즉시 실행하지 않고, 심층분석 리포트를
# 만들어 사용자 승인을 먼저 받는다. 이 값을 False로 되돌리면 예전의
# "즉시 실행 + 사후 통보"로 돌아가므로, 승인 절차를 우회하려는 변경인지
# 확인하지 않고 건드리지 말 것.
REQUIRE_APPROVAL = True
APPROVAL_TTL_DAYS = 2   # 승인 없이 이 기간이 지나면 만료 - 오래된 판정이 뒤늦게 체결되지 않게


def today_kst():
    return datetime.now(KST).strftime("%Y-%m-%d")


# ── 킬스위치 / 상태 ─────────────────────────────────────────────────────────

def load_state():
    st = load_json(STATE_FILE, {})
    st.setdefault("stopped", False)
    st.setdefault("stopped_at", None)
    st.setdefault("first_enabled_at", None)
    st.setdefault("last_fired", {})       # rule -> "YYYY-MM-DD"
    return st


def kill_switch_engaged(state):
    """실행 직전에 매번 호출한다. True면 어떤 규칙도 실행하지 않는다."""
    return bool(state.get("stopped"))


def engage_kill_switch(state, at=None):
    state["stopped"] = True
    state["stopped_at"] = at or datetime.now(KST).isoformat()
    return state


def release_kill_switch(state):
    """해제는 명시적 명령으로만. 실행 실패나 재시작으로 저절로 풀리지 않는다."""
    state["stopped"] = False
    state["stopped_at"] = None
    return state


def in_grace_period(state, today=None):
    """첫 활성화로부터 GRACE_PERIOD_DAYS 이내인지."""
    first = state.get("first_enabled_at")
    if not first:
        return True   # 아직 한 번도 활성화된 적 없으면 가장 보수적으로 취급
    today = today or today_kst()
    d = (datetime.strptime(today, "%Y-%m-%d")
         - datetime.strptime(first[:10], "%Y-%m-%d")).days
    return d < GRACE_PERIOD_DAYS


def rate_limited(state, rule, today=None):
    """유예 기간 동안 규칙별 1일 1회 제한. 기간이 지나면 제한 해제."""
    if not in_grace_period(state, today):
        return False
    return state.get("last_fired", {}).get(rule) == (today or today_kst())


# ── 로깅: 발동/미발동 전량 ──────────────────────────────────────────────────

def log_decision(log, today, rule, symbol, fired, reason, detail=None):
    log.setdefault("decisions", []).append({
        "at": datetime.now(KST).isoformat(),
        "date": today,
        "rule": rule,
        "symbol": symbol,
        "fired": fired,          # 발동 여부를 명시적으로 남긴다
        "reason": reason,        # 발동/미발동 사유
        "detail": detail or {},
    })
    return log


# ── 규칙 판정 (결정론적 산술) ───────────────────────────────────────────────

def _num(v, default=0.0):
    """토스 API는 quantity/current_price를 **문자열**로 준다('1', '347500').
    픽스처에 정수를 쓰면 self-test는 통과하는데 실계좌 데이터에서 터진다 —
    실제로 그렇게 터졌다. 수량 계산에 들어가는 값은 전부 이 함수를 통과시킨다."""
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _sell_qty(amount_krw, price_krw, held_qty):
    """매도 수량. 소수 주식은 다루지 않으므로 내림하고, 보유 수량을 넘지 않는다."""
    price = _num(price_krw)
    held = _num(held_qty)
    if price <= 0 or held <= 0:
        return 0
    return max(0, min(int(_num(amount_krw) // price), int(held)))


def eval_concentration(positions, total_assets):
    """비중 > CONCENTRATION_PCT인 종목의 초과분을 매도하되, 1회 매도액은
    해당 종목 평가액의 CONCENTRATION_MAX_SELL_PCT를 넘지 않는다."""
    out = []
    for p in positions:
        ev = _num(p.get("eval_amount_krw"))
        weight = ev / total_assets * 100 if total_assets else 0
        if weight <= CONCENTRATION_PCT:
            out.append({"symbol": p["symbol"], "fired": False,
                        "reason": f"비중 {weight:.2f}% ≤ 기준 {CONCENTRATION_PCT:.0f}%"})
            continue
        excess = ev - total_assets * (CONCENTRATION_PCT / 100)
        cap = ev * (CONCENTRATION_MAX_SELL_PCT / 100)
        amount = min(excess, cap)
        price = _num(p.get("current_price"))
        qty = _sell_qty(amount, price, p.get("quantity") or 0)
        if qty <= 0:
            out.append({"symbol": p["symbol"], "fired": False,
                        "reason": f"매도 수량 계산 결과 0주 (매도액 {amount:,.0f}원 / 현재가 {price:,.0f}원)"})
            continue
        out.append({
            "symbol": p["symbol"], "name": p.get("name", p["symbol"]), "fired": True,
            "action": "sell", "quantity": qty,
            "reason": (f"비중 {weight:.2f}%가 기준 {CONCENTRATION_PCT:.0f}% 초과 — "
                       f"초과분 {excess:,.0f}원, 1회 상한 {cap:,.0f}원 적용해 {amount:,.0f}원 매도"),
            "detail": {"weight_pct": round(weight, 2), "excess_krw": round(excess),
                       "cap_krw": round(cap), "sell_krw": round(amount)},
        })
    return out


def eval_loss_cut(positions, loss_since, today=None):
    """기준선 이하가 LOSS_SUSTAINED_DAYS 이상 지속되면 전량 매도.
    지속일수는 portfolio_report.py가 관리하는 loss_since 기록을 그대로 쓴다."""
    today = today or today_kst()
    today_dt = datetime.strptime(today, "%Y-%m-%d")
    out = []
    for p in positions:
        ret = _num(p.get("return_pct"))
        sym = p["symbol"]
        if ret > LOSS_PCT:
            out.append({"symbol": sym, "fired": False,
                        "reason": f"손익 {ret:.2f}% > 기준선 {LOSS_PCT:.0f}%"})
            continue
        since = loss_since.get(sym)
        if not since:
            out.append({"symbol": sym, "fired": False,
                        "reason": f"손익 {ret:.2f}%는 기준선 이하이나 지속 추적 시작일 기록 없음"})
            continue
        days = (today_dt - datetime.strptime(since, "%Y-%m-%d")).days
        if days < LOSS_SUSTAINED_DAYS:
            out.append({"symbol": sym, "fired": False,
                        "reason": f"손익 {ret:.2f}% 지속 {days}일 < 기준 {LOSS_SUSTAINED_DAYS}일"})
            continue
        qty = int(_num(p.get("quantity")))
        if qty <= 0:
            out.append({"symbol": sym, "fired": False, "reason": "보유 수량 0"})
            continue
        out.append({
            "symbol": sym, "name": p.get("name", sym), "fired": True,
            "action": "sell", "quantity": qty,
            "reason": (f"손익 {ret:.2f}%가 기준선 {LOSS_PCT:.0f}% 이하로 "
                       f"{since}부터 {days}일 지속 — 전량 매도"),
            # 세금손실 활용 문구(요구사항 2). 사실 안내이며 세무 자문이 아니다.
            "tax_note": ("실현 손실은 같은 과세연도의 양도소득과 통산됩니다. "
                         "해외주식은 연간 250만원 기본공제가 있어 이익 종목과 함께 실현하면 "
                         "과세표준을 낮출 수 있습니다. 구체적 적용은 세무 전문가 확인이 필요합니다."),
            "detail": {"return_pct": ret, "since": since, "days": days},
        })
    return out


def eval_target_price(positions, targets):
    """사람이 수기 입력한 목표가에 도달하면 지정 비율만큼 부분 매도.

    **목표가를 코드가 계산하거나 제안하지 않는다.** targets에 없는 종목은 판정
    대상이 아니며, 값이 비어 있으면 건너뛴다 — 기본값을 지어내지 않는다."""
    out = []
    for p in positions:
        sym = p["symbol"]
        t = targets.get(sym)
        if not t or t.get("target_price") in (None, ""):
            out.append({"symbol": sym, "fired": False, "reason": "사용자 입력 목표가 없음"})
            continue
        target = _num(t["target_price"])
        price = _num(p.get("current_price"))
        if price < target:
            out.append({"symbol": sym, "fired": False,
                        "reason": f"현재가 {price:,.0f} < 목표가 {target:,.0f}"})
            continue
        ratio = _num(t.get("sell_ratio_pct"))
        if ratio <= 0:
            out.append({"symbol": sym, "fired": False,
                        "reason": "목표가 도달했으나 sell_ratio_pct 미입력"})
            continue
        held = int(_num(p.get("quantity")))
        qty = max(0, min(int(held * ratio / 100), held))
        if qty <= 0:
            out.append({"symbol": sym, "fired": False,
                        "reason": f"부분매도 비율 {ratio:.0f}% 적용 시 0주 (보유 {held}주)"})
            continue
        out.append({
            "symbol": sym, "name": p.get("name", sym), "fired": True,
            "action": "sell", "quantity": qty,
            "reason": (f"현재가 {price:,.0f}가 사용자 입력 목표가 {target:,.0f} 도달 — "
                       f"보유 {held}주의 {ratio:.0f}%인 {qty}주 부분 매도"),
            "detail": {"target_price": target, "current_price": price,
                       "sell_ratio_pct": ratio, "held_qty": held,
                       "target_entered_at": t.get("entered_at"),
                       "target_source": "user_manual_input"},
        })
    return out


# ── 승인 대기열 (사전 승인 흐름) ────────────────────────────────────────────

def queue_for_approval(state, rule, decision, today=None):
    """발동 건을 승인 대기로 올린다. 같은 날 같은 규칙·종목 건은 재등록하지
    않는다 — 매일 도는 워크플로가 같은 제안을 쌓지 않게."""
    today = today or today_kst()
    q = state.setdefault("pending_approvals", [])
    aid = f"{rule}_{decision['symbol']}_{today}"
    for p in q:
        if p["id"] == aid and p["status"] == "waiting":
            return p
    entry = {
        "id": aid, "rule": rule, "symbol": decision["symbol"],
        "name": decision.get("name", decision["symbol"]),
        "quantity": int(_num(decision.get("quantity"))),
        "reason": decision.get("reason", ""),
        "detail": decision.get("detail", {}),
        "tax_note": decision.get("tax_note"),
        "created_at": today, "status": "waiting",
    }
    q.append(entry)
    return entry


def expire_stale_approvals(state, today=None):
    """오래된 승인 대기를 만료시킨다. 며칠 지난 판정으로 지금 체결하는 건
    근거가 이미 낡은 것이라 위험하다."""
    today = today or today_kst()
    t = datetime.strptime(today, "%Y-%m-%d")
    expired = []
    for p in state.get("pending_approvals", []):
        if p["status"] != "waiting":
            continue
        age = (t - datetime.strptime(p["created_at"], "%Y-%m-%d")).days
        if age >= APPROVAL_TTL_DAYS:
            p["status"] = "expired"
            expired.append(p)
    return expired


def find_approval(state, approval_id):
    for p in state.get("pending_approvals", []):
        if p["id"] == approval_id:
            return p
    return None


# ── 주문 실행 계층 (미구현 seam) ────────────────────────────────────────────

class OrderLayerUnavailable(Exception):
    pass


def place_sell_order(symbol, quantity):
    """**미구현.** 토스 주문 API 스펙이 저장소에 없다 — 현재 연동된 엔드포인트는
    /accounts, /holdings, /buying-power, /exchange-rate, /oauth2/token 뿐이고
    주문 엔드포인트·요청 스키마·주문유형 enum·멱등키 처리 방식 중 무엇도 알려져
    있지 않다. 실계좌 주문에서 이것들을 추측으로 채우는 건 허용될 수 없어
    구현하지 않고 명시적으로 실패시킨다.

    매수는 이 함수에도, 이 파일 어디에도 없다(요구사항 3)."""
    raise OrderLayerUnavailable(
        f"주문 실행 계층 미구현 - 토스 주문 API 스펙 필요 (요청: {symbol} {quantity}주 매도)")


def execute(decision):
    """매도만 허용한다. 다른 action은 구조적으로 거부 — 매수 경로를 만들지 않기
    위한 방어선이다(요구사항 3)."""
    if decision.get("action") != "sell":
        raise ValueError(f"매도 외 action은 허용되지 않음: {decision.get('action')!r}")
    if int(_num(decision.get("quantity"))) <= 0:
        raise ValueError("매도 수량이 0 이하")
    return place_sell_order(decision["symbol"], int(decision["quantity"]))


# ── 실행 루프 ───────────────────────────────────────────────────────────────

def run_rules(portfolio, targets, state, log, loss_since, today=None, enabled=False):
    """규칙을 판정하고, 발동 건에 대해 안전장치를 순서대로 통과시킨 뒤 실행한다.
    반환: (실행 결과 목록, state, log)"""
    today = today or today_kst()
    positions = portfolio.get("positions", [])
    total = sum(_num(p.get("eval_amount_krw")) for p in positions) + _num(portfolio.get("cash"))

    batches = [
        ("집중도리밸런싱", eval_concentration(positions, total)),
        ("손실지속손절", eval_loss_cut(positions, loss_since, today)),
        ("목표가부분익절", eval_target_price(positions, targets)),
    ]

    results = []
    for rule, decisions in batches:
        for d in decisions:
            if not d["fired"]:
                log_decision(log, today, rule, d["symbol"], False, d["reason"])
                continue

            # 안전장치 순서: 킬스위치 → 활성 플래그 → 유예기간 레이트리밋
            if kill_switch_engaged(state):
                log_decision(log, today, rule, d["symbol"], False,
                             "킬스위치 작동 중 - 실행 차단", d.get("detail"))
                continue
            if not enabled:
                log_decision(log, today, rule, d["symbol"], False,
                             "RULE_BASED_AUTOEXEC_ENABLED=false - 판정만 수행", d.get("detail"))
                results.append({**d, "rule": rule, "executed": False,
                                "status": "비활성(판정만)"})
                continue
            if rate_limited(state, rule, today):
                log_decision(log, today, rule, d["symbol"], False,
                             f"유예기간 중 {rule} 당일 1회 제한 초과", d.get("detail"))
                continue

            # [2026-08-04 방향성 세션 수정] "즉시 실행 + 사후 통보" -> "분석 리포트 +
            # 사전 승인". 발동해도 바로 실행하지 않고, 심층분석 리포트를 만들어
            # 승인 대기로 올린다. 실제 실행은 사용자가 /autoexec_approve 한 뒤에만.
            if REQUIRE_APPROVAL:
                pend = queue_for_approval(state, rule, d, today)
                log_decision(log, today, rule, d["symbol"], False,
                             f"승인 대기 등록 (id={pend['id']}) - 사전 승인 필요", d.get("detail"))
                results.append({**d, "rule": rule, "executed": False,
                                "status": "승인 대기", "approval_id": pend["id"]})
                continue

            try:
                execute(d)
                state.setdefault("last_fired", {})[rule] = today
                log_decision(log, today, rule, d["symbol"], True, d["reason"], d.get("detail"))
                results.append({**d, "rule": rule, "executed": True, "status": "실행됨"})
            except OrderLayerUnavailable as e:
                log_decision(log, today, rule, d["symbol"], False,
                             f"실행 불가: {e}", d.get("detail"))
                results.append({**d, "rule": rule, "executed": False,
                                "status": "실행 불가(주문계층 미구현)"})
            except Exception as e:
                log_decision(log, today, rule, d["symbol"], False,
                             f"실행 오류: {e}", d.get("detail"))
                results.append({**d, "rule": rule, "executed": False,
                                "status": f"오류: {e}"})
    return results, state, log


def fetch_market_context(symbol, position):
    """리포트에 넣을 시세/뉴스를 조회한다. 조회 실패는 리포트 생성을 막지 않고
    해당 섹션만 '데이터 부족'으로 남는다 — 승인 자료가 아예 안 나오는 것보다
    일부라도 나오는 편이 낫고, 무엇이 빠졌는지는 리포트에 드러난다."""
    closes = highs = lows = None
    headlines = None
    try:
        if position.get("market_country") == "KR":
            from analyze_lib import get_krx_candles
            candles = get_krx_candles(symbol, count=140)
            closes = [c["close"] for c in candles]
            highs = [c["high"] for c in candles]
            lows = [c["low"] for c in candles]
        else:
            from analyze_lib import get_us_closes
            closes = get_us_closes(symbol, count=140)
    except Exception as e:
        print(f"⚠️ {symbol} 시세 조회 실패 - 차트 섹션 생략 ({e})")
    try:
        from analyze_lib import get_news_headlines
        headlines = get_news_headlines(symbol)
    except Exception as e:
        print(f"⚠️ {symbol} 뉴스 조회 실패 - 시장 섹션 생략 ({e})")
    return {"closes": closes, "highs": highs, "lows": lows, "headlines": headlines}


def build_trigger_report(approval, position, context=None):
    """발동 건에 대한 심층분석 리포트를 만든다.

    **리포트 형식/금지어 규율은 rule_trigger_report.generate()가 단독으로
    책임진다** — 자동실행 플로우와 프록시 세션이 같은 함수를 부르게 해서 두
    경로의 결과물이 갈라지지 않게 한다(요구사항 4)."""
    import rule_trigger_report as rtr
    ctx = context or fetch_market_context(approval["symbol"], position)
    return rtr.generate(
        approval["symbol"], position,
        {"rule": approval["rule"], "quantity": approval["quantity"],
         "reason": approval["reason"], "detail": approval["detail"]},
        closes=ctx.get("closes"), highs=ctx.get("highs"), lows=ctx.get("lows"),
        event_card=ctx.get("event_card"), headlines=ctx.get("headlines"),
    )


def notify(results, state):
    """판정 결과 통보. 2026-08-04 수정으로 발동 건은 승인 대기로 가므로,
    이 메시지는 사후 통보가 아니라 승인 요청이다."""
    fired = [r for r in results if r.get("executed")]
    blocked = [r for r in results if not r.get("executed")]
    if not fired and not blocked:
        return None
    lines = ["🤖 규칙 기반 자동실행 판정 결과 (실행 전 승인 필요)"]
    if kill_switch_engaged(state):
        lines.append("🛑 킬스위치 작동 중 — 실행이 차단되었습니다.")
    for r in fired:
        lines.append(f"✅ [{r['rule']}] {r.get('name', r['symbol'])} {r['quantity']}주 매도")
        lines.append(f"   {r['reason']}")
        if r.get("tax_note"):
            lines.append(f"   💡 {r['tax_note']}")
    for r in blocked:
        lines.append(f"⏸️ [{r['rule']}] {r.get('name', r['symbol'])} {r['quantity']}주 — {r['status']}")
        lines.append(f"   {r['reason']}")
        if r.get("approval_id"):
            lines.append(f"   👉 분석 리포트 확인 후 /autoexec_approve {r['approval_id']}")
            lines.append(f"      취소하려면 /autoexec_reject {r['approval_id']}")
    lines.append("")
    lines.append("중단하려면 /autoexec_stop 을 보내세요.")
    return "\n".join(lines)


def run(args):
    from analyze_lib import RULE_BASED_AUTOEXEC_ENABLED
    portfolio = load_json(REAL_PORTFOLIO_FILE, None)
    if not portfolio:
        print(f"⚠️ {REAL_PORTFOLIO_FILE} 없음")
        return
    targets = load_json(TARGET_PRICES_FILE, {}).get("targets", {})
    state = load_state()
    log = load_json(LOG_FILE, {"decisions": []})
    loss_since = load_json(REPORT_STATE_FILE, {}).get("loss_since", {})

    enabled = RULE_BASED_AUTOEXEC_ENABLED and not args.evaluate_only
    if enabled and not state.get("first_enabled_at"):
        state["first_enabled_at"] = datetime.now(KST).isoformat()

    expired = expire_stale_approvals(state)
    for e in expired:
        print(f"⌛ 승인 대기 만료: {e['id']} ({APPROVAL_TTL_DAYS}일 경과)")

    results, state, log = run_rules(portfolio, targets, state, log, loss_since,
                                    enabled=enabled)

    # 승인 대기로 올라간 건에 대해 심층분석 리포트를 만들어 저장한다.
    pos_by_sym = {p["symbol"]: p for p in portfolio.get("positions", [])}
    reports = load_json(REPORTS_FILE, {"reports": {}})
    for r in results:
        aid = r.get("approval_id")
        if not aid or aid in reports["reports"]:
            continue
        ap = find_approval(state, aid)
        pos = pos_by_sym.get(r["symbol"], {})
        try:
            rep = build_trigger_report(ap, pos)
            reports["reports"][aid] = rep
            print("\n" + __import__("rule_trigger_report").render_text(rep))
        except Exception as e:
            print(f"⚠️ {aid} 리포트 생성 실패: {e}")
    save_json(REPORTS_FILE, reports)

    save_json(STATE_FILE, state)
    save_json(LOG_FILE, log)

    msg = notify(results, state)
    print(msg or "발동한 규칙 없음")
    print(f"\n판정 로그 누적 {len(log['decisions'])}건 → {LOG_FILE}")
    if msg and args.telegram:
        send_telegram(msg)


def main():
    p = argparse.ArgumentParser(description="규칙 기반 포지션 관리 자동실행 (매도 전용)")
    p.add_argument("--telegram", action="store_true")
    p.add_argument("--evaluate-only", action="store_true",
                   help="플래그와 무관하게 판정만 수행(실행 안 함)")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        run_self_test()
        return
    run(a)


# ── 자체 검증 ───────────────────────────────────────────────────────────────

def _fixture():
    portfolio = {"cash": 0.0, "positions": [
        {"symbol": "BIG", "name": "집중종목", "quantity": 100,
         "current_price": 10000, "eval_amount_krw": 1000000.0, "return_pct": 5.0},
        {"symbol": "LOSS", "name": "손실종목", "quantity": 50,
         "current_price": 2000, "eval_amount_krw": 100000.0, "return_pct": -60.0},
        {"symbol": "TGT", "name": "목표가종목", "quantity": 40,
         "current_price": 15000, "eval_amount_krw": 600000.0, "return_pct": 20.0},
    ]}
    targets = {"TGT": {"target_price": 14000, "sell_ratio_pct": 25,
                       "entered_at": "2026-08-01"}}
    return portfolio, targets


def run_self_test():
    print("=== autoexec.py 자체 검증 (네트워크/실계좌 미사용) ===\n")
    portfolio, targets = _fixture()
    total = sum(p["eval_amount_krw"] for p in portfolio["positions"])

    # 1) 킬스위치: 걸리면 실행 차단, 해제는 명시 명령으로만
    st = load_state()
    st = engage_kill_switch(st, "2026-08-04T00:00:00+09:00")
    print(f"[1] 킬스위치 engage -> stopped={st['stopped']}")
    assert kill_switch_engaged(st) is True
    log = {"decisions": []}
    res, st, log = run_rules(portfolio, targets, st, log, {"LOSS": "2026-01-01"},
                             "2026-08-04", enabled=True)
    executed = [r for r in res if r.get("executed")]
    print(f"    킬스위치 ON 상태 실행건수={len(executed)} (0이어야 함)")
    assert executed == [], "킬스위치가 걸렸는데 실행됨"
    blocked = [d for d in log["decisions"] if "킬스위치" in d["reason"]]
    print(f"    킬스위치 차단 로그 {len(blocked)}건")
    assert blocked, "킬스위치 차단이 로깅되지 않음"
    st = release_kill_switch(st)
    assert kill_switch_engaged(st) is False
    print("    release 후 stopped=False 확인")

    # 2) 규칙 산술: 집중도
    conc = [d for d in eval_concentration(portfolio["positions"], total) if d["fired"]]
    by_sym = {d["symbol"]: d for d in conc}
    print(f"[2] 집중도 발동 {len(conc)}건: {sorted(by_sym)}")
    for d in conc:
        print(f"    {d['symbol']}: {d['reason']}")
    # 총자산 170만. BIG 100만(58.8%)과 TGT 60만(35.3%) 둘 다 30% 초과 —
    # 규칙이 종목별로 독립 적용되는지까지 같이 확인한다.
    assert set(by_sym) == {"BIG", "TGT"}, f"발동 종목이 예상과 다름: {sorted(by_sym)}"
    # BIG: 초과분 = 100만 - 51만 = 49만, 1회 상한 = 100만*30% = 30만 -> 30만, 현재가 1만 -> 30주
    assert by_sym["BIG"]["quantity"] == 30, f"BIG 매도 수량 오류: {by_sym['BIG']['quantity']}"
    assert by_sym["BIG"]["detail"]["sell_krw"] == 300000
    # TGT: 초과분 = 60만 - 51만 = 9만 < 상한 18만 -> 9만, 현재가 1.5만 -> 6주 (상한이 아니라 초과분이 묶임)
    assert by_sym["TGT"]["detail"]["sell_krw"] == 90000, "초과분이 상한보다 작으면 초과분만 매도해야 함"
    assert by_sym["TGT"]["quantity"] == 6, f"TGT 매도 수량 오류: {by_sym['TGT']['quantity']}"

    # 3) 손실 지속: 60일 미만이면 미발동, 이상이면 전량
    short = eval_loss_cut(portfolio["positions"], {"LOSS": "2026-07-01"}, "2026-08-04")
    assert not [d for d in short if d["fired"]], "34일인데 발동됨"
    long_ = [d for d in eval_loss_cut(portfolio["positions"], {"LOSS": "2026-01-01"},
                                      "2026-08-04") if d["fired"]]
    print(f"[3] 손실지속 발동 {len(long_)}건, 수량={long_[0]['quantity']} (전량 50주)")
    assert long_[0]["quantity"] == 50
    assert "양도소득" in long_[0]["tax_note"], "세금손실 활용 문구 누락"

    # 4) 목표가: 사람이 넣은 값만 쓰고, 없으면 발동하지 않는다
    tg = [d for d in eval_target_price(portfolio["positions"], targets) if d["fired"]]
    print(f"[4] 목표가 발동 {len(tg)}건, 수량={tg[0]['quantity']} (40주의 25%)")
    assert len(tg) == 1 and tg[0]["symbol"] == "TGT" and tg[0]["quantity"] == 10
    assert tg[0]["detail"]["target_source"] == "user_manual_input"
    none_t = [d for d in eval_target_price(portfolio["positions"], {}) if d["fired"]]
    assert none_t == [], "목표가 미입력인데 발동됨 - 기본값을 지어내면 안 됨"
    print("    목표가 미입력 시 발동 0건 확인 (기본값 생성 안 함)")

    # 5) 매수 경로 부재: sell 외 action은 구조적으로 거부
    try:
        execute({"action": "buy", "symbol": "X", "quantity": 1})
        raise AssertionError("매수가 거부되지 않음")
    except ValueError as e:
        print(f"[5] 매수 시도 거부됨: {e}")
    # 소스 문자열을 훑는 검사는 테스트 자신의 코드에 걸려 오탐이 난다(이번 세션에서
    # 반복해서 겪음). 모듈 네임스페이스와 실제 동작으로 판정한다.
    import sys
    mod = sys.modules[__name__]
    buyish = [n for n in dir(mod)
              if any(k in n.lower() for k in ("buy", "purchase", "매수"))
              and callable(getattr(mod, n))]
    print(f"    매수 관련 호출 가능 심볼: {buyish or '없음'}")
    assert not buyish, f"매수 경로로 쓰일 수 있는 함수가 존재함: {buyish}"
    for bad_action in ("buy", "매수", "BUY", None, "", "rebalance"):
        try:
            execute({"action": bad_action, "symbol": "X", "quantity": 1})
            raise AssertionError(f"action={bad_action!r}가 거부되지 않음")
        except ValueError:
            pass
    print("    sell 외 action 6종 전부 거부 확인")

    # 6) 목표가를 AI가 계산하지 않는지 - 이 모듈이 Claude API를 임포트조차 안 해야 한다
    import inspect
    ai_syms = [n for n in dir(mod)
               if any(k in n.upper() for k in ("CLAUDE", "ANTHROPIC", "ASK_"))]
    fn_src = inspect.getsource(eval_target_price)
    print(f"[6] AI 관련 심볼: {ai_syms or '없음'}")
    assert not ai_syms, f"AI 호출 관련 심볼 발견: {ai_syms}"
    for banned in ("requests.post", "anthropic", "CLAUDE_API_KEY"):
        assert banned not in fn_src, f"목표가 판정부에 AI 호출 흔적: {banned}"
    print("    목표가 판정부는 targets 딕셔너리 비교만 수행 (사람 입력 전용)")

    # 7) 전량 로깅: 미발동도 남는가
    log2 = {"decisions": []}
    st2 = load_state()
    _, _, log2 = run_rules(portfolio, targets, st2, log2, {"LOSS": "2026-07-01"},
                           "2026-08-04", enabled=False)
    fired_logs = [d for d in log2["decisions"] if d["fired"]]
    not_fired = [d for d in log2["decisions"] if not d["fired"]]
    print(f"[7] 로그 총 {len(log2['decisions'])}건 (발동 {len(fired_logs)} / 미발동 {len(not_fired)})")
    assert len(log2["decisions"]) == 9, "3규칙 x 3종목 = 9건이 전량 로깅돼야 함"
    assert all("reason" in d for d in log2["decisions"]), "사유 없는 로그 존재"

    # 8) 유예기간 레이트리밋: 같은 날 두 번째는 차단
    st3 = load_state()
    st3["first_enabled_at"] = "2026-08-04T00:00:00+09:00"
    assert in_grace_period(st3, "2026-08-06") is True
    assert rate_limited(st3, "집중도리밸런싱", "2026-08-06") is False
    st3["last_fired"]["집중도리밸런싱"] = "2026-08-06"
    assert rate_limited(st3, "집중도리밸런싱", "2026-08-06") is True
    print("[8] 유예기간 중 당일 재발동 차단 확인")
    assert in_grace_period(st3, "2026-08-20") is False
    assert rate_limited(st3, "집중도리밸런싱", "2026-08-20") is False
    print("    유예기간(7일) 경과 후 제한 해제 확인")

    # 8-b) 실계좌와 동일한 **문자열** 타입 입력에서도 동작하는지 (회귀 방지).
    #      토스 API는 quantity/current_price를 문자열로 준다. 정수 픽스처만으로
    #      테스트했다가 실계좌 데이터에서 TypeError로 터진 적이 있다.
    str_pf = {"cash": "0", "positions": [
        {"symbol": "STR", "name": "문자열종목", "quantity": "100",
         "current_price": "10000", "eval_amount_krw": 1000000.0, "return_pct": "-60.0"},
    ]}
    c = [d for d in eval_concentration(str_pf["positions"], 1000000.0) if d["fired"]]
    l = [d for d in eval_loss_cut(str_pf["positions"], {"STR": "2026-01-01"}, "2026-08-04") if d["fired"]]
    t = [d for d in eval_target_price(str_pf["positions"],
                                      {"STR": {"target_price": "9000", "sell_ratio_pct": "50"}}) if d["fired"]]
    print(f"[8b] 문자열 입력: 집중도 {c[0]['quantity'] if c else 0}주 / "
          f"손절 {l[0]['quantity'] if l else 0}주 / 목표가 {t[0]['quantity'] if t else 0}주")
    assert c and c[0]["quantity"] == 30, "문자열 입력에서 집중도 수량 계산 실패"
    assert l and l[0]["quantity"] == 100, "문자열 입력에서 손절 수량 계산 실패"
    assert t and t[0]["quantity"] == 50, "문자열 입력에서 목표가 수량 계산 실패"

    # 8-c) 사전 승인 흐름: 발동해도 바로 실행되지 않고 승인 대기로 가는지
    st4 = load_state()
    log4 = {"decisions": []}
    res4, st4, log4 = run_rules(portfolio, targets, st4, log4,
                                {"LOSS": "2026-01-01"}, "2026-08-04", enabled=True)
    fired4 = [r for r in res4 if r.get("approval_id")]
    executed4 = [r for r in res4 if r.get("executed")]
    print(f"[8c] 발동 {len(fired4)}건 전부 승인대기 / 즉시 실행 {len(executed4)}건")
    assert fired4, "발동 건이 승인 대기로 올라가지 않음"
    assert executed4 == [], "사전 승인 없이 실행됨"
    assert all(r["status"] == "승인 대기" for r in fired4)
    q = st4.get("pending_approvals", [])
    assert len(q) == len(fired4) and all(p["status"] == "waiting" for p in q)

    # 같은 날 재실행해도 중복 등록되지 않는지
    res5, st4, _ = run_rules(portfolio, targets, st4, {"decisions": []},
                             {"LOSS": "2026-01-01"}, "2026-08-04", enabled=True)
    assert len(st4["pending_approvals"]) == len(q), "같은 건이 중복 등록됨"
    print(f"     같은 날 재실행 후에도 대기열 {len(st4['pending_approvals'])}건 (중복 없음)")

    # 승인 없이 TTL 경과하면 만료되는지
    later = datetime.strptime("2026-08-04", "%Y-%m-%d").toordinal() + APPROVAL_TTL_DAYS
    exp = expire_stale_approvals(st4, datetime.fromordinal(later).strftime("%Y-%m-%d"))
    print(f"     {APPROVAL_TTL_DAYS}일 경과 -> 만료 {len(exp)}건")
    assert len(exp) == len(q), "TTL 경과분이 만료되지 않음"

    # 8-d) 리포트 생성기가 공유되는지 + 금지 내용이 없는지
    import rule_trigger_report as rtr
    ap = {"id": "t", "rule": "집중도리밸런싱", "symbol": "BIG", "name": "집중종목",
          "quantity": 30, "reason": "테스트", "detail": {"weight_pct": 58.8,
          "excess_krw": 490000, "cap_krw": 300000, "sell_krw": 300000}}
    rep = build_trigger_report(ap, portfolio["positions"][0],
                               context={"closes": [100 + i for i in range(140)]})
    viol = rtr.audit(rep)
    print(f"[8d] 리포트 생성기={rtr.generate.__module__} / 감사 위반 {viol or '없음'}")
    assert not viol, f"리포트에 금지 내용: {viol}"
    assert rep["trigger"]["facts"], "발동 사실이 비어 있음"

    # 9) 주문 계층 미구현이 조용히 성공하지 않는지
    try:
        place_sell_order("X", 1)
        raise AssertionError("미구현 주문이 성공한 것처럼 반환됨")
    except OrderLayerUnavailable as e:
        print(f"[9] 주문 계층: {str(e)[:60]}...")

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    main()
