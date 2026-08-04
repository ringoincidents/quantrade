"""[v3.2 활성 기능] 정기 포트폴리오 리포트 생성기 (2026-08-04).

**예측이 아니다.** 하는 일은 두 가지뿐이다:
  (1) 현재 상태를 산술로 계산한다 — 종목별 비중, 평가손익, 자산군 구성.
  (2) 사전에 정해진 규칙에 해당하는지 판정한다 — 집중도, 손실 지속.

출력 스키마에 `direction`/`confidence`/`action` 같은 필드가 **아예 없다**.
"이런 상황이다" + "이런 규칙에 해당한다"까지만 적고, 그래서 무엇을 사거나 팔라는
문장은 담지 않는다(CLAUDE.md v3.2 (b) 원칙, `news_event_cards.py`와 같은 규율).

**읽기 전용이다.** `real_portfolio.json`을 읽기만 하고 쓰지 않으며, 주문·승인
경로와 어떤 식으로도 연결되지 않는다. 실계좌 데이터를 *사람이 보도록 표시*하는
용도는 CLAUDE.md에서 이미 승인된 범주이고, 이 스크립트는 그 범주 안에 있다 —
AI에게 넘겨 판단을 받는 경로(ask_claude_decision)와는 무관하다.

**임계값은 초안이다.** 방향성 세션에서 사전 확정하기 전까지 `THRESHOLDS`의
`provisional: true`가 유지되고, 리포트에도 초안임이 표시된다. 결과를 보고
숫자를 맞추는 걸 막기 위해, 확정 시에는 이 파일이 아니라 별도 기록에 남긴다
(backtest.py SUCCESS_CRITERIA와 같은 원칙).
"""
import argparse
import json
from datetime import datetime, timezone

from analyze_lib import load_json, save_json, send_telegram

REAL_PORTFOLIO_FILE = "real_portfolio.json"
INCOME_SCHEDULE_FILE = "income_schedule.json"
REPORT_FILE = "portfolio_report.json"
STATE_FILE = "portfolio_report_state.json"

# 사전 확정 대기 중인 초안 임계값.
# concentration_pct / loss_pct는 지시받은 값이고, loss_sustained_days는
# "N일"이 미정이라 초안으로 둔 값이다. 셋 다 방향성 세션 확정 대상.
THRESHOLDS = {
    "provisional": True,
    "concentration_pct": 30.0,      # 단일 종목 비중이 이 이상이면 플래그
    "loss_pct": -50.0,              # 평가손익률이 이 이하이고
    "loss_sustained_days": 60,      # 그 상태가 이 일수 이상 지속되면 플래그 (초안)
}

# 리포트 어디에도 들어가면 안 되는 필드. self-test와 대시보드가 함께 검사한다.
FORBIDDEN_FIELDS = ("direction", "confidence", "action", "recommendation",
                    "target_weight_pct", "signal", "buy", "sell", "score")


# ── (1) 순수 계산 ────────────────────────────────────────────────────────────

def compute_positions(real):
    """종목별 비중/손익. 산술만 한다 — 어떤 판단도 붙이지 않는다."""
    positions = real.get("positions", [])
    total_eval = sum(float(p.get("eval_amount_krw") or 0) for p in positions)
    cash = float(real.get("cash") or 0)
    total_assets = total_eval + cash

    rows = []
    for p in positions:
        ev = float(p.get("eval_amount_krw") or 0)
        rows.append({
            "symbol": p.get("symbol"),
            "name": p.get("name", p.get("symbol")),
            "market_country": p.get("market_country"),
            "eval_amount_krw": round(ev, 0),
            "weight_pct": round(ev / total_assets * 100, 2) if total_assets else 0.0,
            "return_pct": float(p.get("return_pct") or 0),
        })
    rows.sort(key=lambda r: -r["eval_amount_krw"])

    by_country = {}
    for r in rows:
        c = r["market_country"] or "미분류"
        by_country[c] = round(by_country.get(c, 0) + r["weight_pct"], 2)

    return {
        "synced_at": real.get("synced_at"),
        "total_assets_krw": round(total_assets, 0),
        "cash_krw": round(cash, 0),
        "cash_pct": round(cash / total_assets * 100, 2) if total_assets else 0.0,
        "position_count": len(rows),
        "positions": rows,
        "weight_by_country_pct": by_country,
    }


# ── (2) 규칙 판정 ────────────────────────────────────────────────────────────

def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def update_loss_streaks(rows, state, today=None):
    """손실 지속일수 추적. real_portfolio.json은 스냅샷이라 '며칠째인지'를 알 수
    없어서, 임계값 이하로 처음 떨어진 날짜를 이 상태파일에 남겨 누적한다.
    임계값 위로 회복하면 기록을 지운다 — 회복 후 재하락은 다시 0일부터."""
    today = today or _today()
    streaks = state.setdefault("loss_since", {})
    for r in rows:
        sym = r["symbol"]
        if r["return_pct"] <= THRESHOLDS["loss_pct"]:
            streaks.setdefault(sym, today)
        else:
            streaks.pop(sym, None)
    # 더 이상 보유하지 않는 종목은 정리
    held = {r["symbol"] for r in rows}
    for sym in [s for s in streaks if s not in held]:
        streaks.pop(sym)
    return streaks


def evaluate_rules(rows, streaks, today=None):
    """규칙 해당 여부만 판정한다. 반환 항목은 '무엇이 어떤 규칙에 해당하는가'라는
    사실이며, 어떻게 하라는 제안 필드는 스키마에 없다."""
    today = today or _today()
    today_dt = datetime.strptime(today, "%Y-%m-%d")
    matches = []

    for r in rows:
        if r["weight_pct"] >= THRESHOLDS["concentration_pct"]:
            matches.append({
                "rule": "집중도",
                "symbol": r["symbol"],
                "name": r["name"],
                "threshold": f"단일 종목 비중 {THRESHOLDS['concentration_pct']:.0f}% 이상",
                "observed": f"{r['weight_pct']:.2f}%",
                "fact": (f"{r['name']}({r['symbol']}) 비중이 총자산의 "
                         f"{r['weight_pct']:.2f}%로 기준 {THRESHOLDS['concentration_pct']:.0f}% 이상"),
            })

    for r in rows:
        since = streaks.get(r["symbol"])
        if not since:
            continue
        days = (today_dt - datetime.strptime(since, "%Y-%m-%d")).days
        if r["return_pct"] <= THRESHOLDS["loss_pct"] and days >= THRESHOLDS["loss_sustained_days"]:
            matches.append({
                "rule": "손실 지속",
                "symbol": r["symbol"],
                "name": r["name"],
                "threshold": (f"평가손익 {THRESHOLDS['loss_pct']:.0f}% 이하가 "
                              f"{THRESHOLDS['loss_sustained_days']}일 이상 지속"),
                "observed": f"{r['return_pct']:.2f}% / {days}일째",
                "fact": (f"{r['name']}({r['symbol']}) 평가손익 {r['return_pct']:.2f}%가 "
                         f"{since}부터 {days}일째 기준선 이하"),
            })
    return matches


# ── (3) 수입 스케줄 기반 배분 로드맵 ────────────────────────────────────────

def compute_roadmap(income):
    """수입 스케줄 → 누적 투자가능액 → 구간별 목표 배분.

    **배분 규칙을 코드에 내장하지 않는다.** income_schedule.json의
    allocation_roadmap.tiers를 해석만 한다 — 표가 바뀌면 JSON만 고치면 되고,
    코드가 표를 '기억'하고 있어서 문서와 어긋나는 일이 생기지 않는다."""
    if income.get("placeholder"):
        return {"status": "미입력",
                "reason": "income_schedule.json이 placeholder 상태 - 계급별 기간/월급/적금 실제 값 필요"}

    schedule = income.get("schedule", [])
    missing = [s.get("rank") for s in schedule
               if not s.get("start") or s.get("monthly_pay") is None or s.get("monthly_savings") is None]
    if missing:
        return {"status": "미입력", "reason": f"수입 정보가 비어 있는 계급: {missing}"}

    months, cumulative = [], 0
    for s in schedule:
        start = datetime.strptime(s["start"], "%Y-%m")
        end = datetime.strptime(s["end"], "%Y-%m")
        n = (end.year - start.year) * 12 + (end.month - start.month) + 1
        monthly = float(s["monthly_pay"]) + float(s["monthly_savings"])
        for i in range(n):
            m = start.month - 1 + i
            cumulative += monthly
            months.append({
                "month": f"{start.year + m // 12}-{m % 12 + 1:02d}",
                "rank": s["rank"],
                "monthly_investable": monthly,
                "cumulative_investable": cumulative,
            })

    tiers = income.get("allocation_roadmap", {}).get("tiers", [])
    if not tiers:
        return {"status": "구간표 미입력",
                "reason": "allocation_roadmap.tiers가 비어 있음 - 방향성 세션에서 정리한 배분표를 옮겨야 함",
                "months": months, "total_investable": cumulative}

    for m in months:
        m["target_allocation"] = next(
            (t.get("allocation") for t in tiers
             if m["cumulative_investable"] >= t.get("min_cumulative", 0)
             and (t.get("max_cumulative") is None or m["cumulative_investable"] < t["max_cumulative"])),
            None)
    return {"status": "계산됨", "months": months, "total_investable": cumulative}


# ── 리포트 조립 ─────────────────────────────────────────────────────────────

def build_report(real, income, state, today=None):
    today = today or _today()
    snapshot = compute_positions(real)
    streaks = update_loss_streaks(snapshot["positions"], state, today)
    matches = evaluate_rules(snapshot["positions"], streaks, today)
    report = {
        "generated_at": today,
        "schema": "portfolio_report_v3.2",
        "note": ("현황 계산 + 사전 정의 규칙 해당 여부만 담는다. 매매 판단/방향 예측/"
                 "확신도 필드는 스키마에 없다 - 누락이 아니라 설계."),
        "thresholds": dict(THRESHOLDS),
        "snapshot": snapshot,
        "rule_matches": matches,
        "roadmap": compute_roadmap(income),
    }
    return report, state


def format_telegram(report):
    s = report["snapshot"]
    lines = [f"📋 포트폴리오 리포트 ({report['generated_at']})", ""]
    lines.append(f"총자산 {s['total_assets_krw']:,.0f}원 · 현금 {s['cash_pct']:.1f}% · 보유 {s['position_count']}종목")
    if s["weight_by_country_pct"]:
        lines.append("자산군: " + " / ".join(f"{k} {v:.1f}%" for k, v in s["weight_by_country_pct"].items()))
    lines.append("")
    top = s["positions"][:5]
    for p in top:
        lines.append(f"· {p['name']} {p['weight_pct']:.1f}% ({p['return_pct']:+.2f}%)")
    lines.append("")
    if report["rule_matches"]:
        tag = " [초안 기준]" if report["thresholds"]["provisional"] else ""
        lines.append(f"📐 규칙 해당 {len(report['rule_matches'])}건{tag}")
        for m in report["rule_matches"]:
            lines.append(f"   · [{m['rule']}] {m['fact']}")
    else:
        lines.append("📐 해당하는 규칙 없음")
    rm = report["roadmap"]
    if rm.get("status") != "계산됨":
        lines.append("")
        lines.append(f"🗺️ 배분 로드맵: {rm['status']} — {rm['reason']}")
    lines.append("")
    lines.append("※ 현황과 규칙 해당 여부만 알립니다. 매매 판단은 포함하지 않습니다.")
    return "\n".join(lines)


def run(args):
    real = load_json(REAL_PORTFOLIO_FILE, None)
    if not real:
        print(f"⚠️ {REAL_PORTFOLIO_FILE} 없음 - sync_real.yml 실행 후 다시 시도")
        return
    income = load_json(INCOME_SCHEDULE_FILE, {"placeholder": True})
    state = load_json(STATE_FILE, {"loss_since": {}})

    report, state = build_report(real, income, state)
    save_json(REPORT_FILE, report)
    save_json(STATE_FILE, state)

    text = format_telegram(report)
    print(text)
    if args.telegram:
        send_telegram(text)


def main():
    p = argparse.ArgumentParser(description="정기 포트폴리오 리포트 (읽기 전용, 예측 없음)")
    p.add_argument("--telegram", action="store_true", help="텔레그램으로도 전송")
    p.add_argument("--self-test", action="store_true", help="네트워크/실제 파일 없이 로직 검증")
    a = p.parse_args()
    if a.self_test:
        run_self_test()
        return
    run(a)


def run_self_test():
    print("=== portfolio_report.py 자체 검증 (네트워크/실제 파일 미사용) ===\n")

    real = {"synced_at": "2026-08-04T00:00:00+00:00", "cash": 100000.0, "positions": [
        {"symbol": "A", "name": "집중종목", "market_country": "KR",
         "eval_amount_krw": 600000.0, "return_pct": -5.0},
        {"symbol": "B", "name": "손실종목", "market_country": "US",
         "eval_amount_krw": 200000.0, "return_pct": -60.0},
        {"symbol": "C", "name": "보통종목", "market_country": "US",
         "eval_amount_krw": 100000.0, "return_pct": 3.0},
    ]}

    # 1) 비중 계산 (총자산 = 90만 + 현금 10만 = 100만)
    snap = compute_positions(real)
    print(f"[1] 총자산={snap['total_assets_krw']:,.0f} / A 비중={snap['positions'][0]['weight_pct']}% "
          f"/ 현금={snap['cash_pct']}% / 국가별={snap['weight_by_country_pct']}")
    assert snap["total_assets_krw"] == 1000000
    assert snap["positions"][0]["weight_pct"] == 60.0
    assert snap["cash_pct"] == 10.0
    assert abs(sum(snap["weight_by_country_pct"].values()) + snap["cash_pct"] - 100.0) < 0.01, \
        "종목 비중 합 + 현금 비중은 100%여야 함"

    # 2) 집중도 규칙: 60% >= 30% -> 해당
    state = {"loss_since": {}}
    streaks = update_loss_streaks(snap["positions"], state, "2026-08-04")
    m = evaluate_rules(snap["positions"], streaks, "2026-08-04")
    conc = [x for x in m if x["rule"] == "집중도"]
    print(f"[2] 집중도 해당 {len(conc)}건: {conc[0]['fact'] if conc else '-'}")
    assert len(conc) == 1 and conc[0]["symbol"] == "A"

    # 3) 손실 지속: 첫날은 0일째라 미해당, 임계일수 경과 후 해당
    print(f"[3] 손실 추적 시작일 기록: {streaks}")
    assert streaks["B"] == "2026-08-04" and "C" not in streaks
    assert not [x for x in m if x["rule"] == "손실 지속"], "첫날부터 지속 판정이 나오면 안 됨"
    later = (datetime.strptime("2026-08-04", "%Y-%m-%d").toordinal()
             + THRESHOLDS["loss_sustained_days"])
    later_s = datetime.fromordinal(later).strftime("%Y-%m-%d")
    m2 = evaluate_rules(snap["positions"], streaks, later_s)
    loss = [x for x in m2 if x["rule"] == "손실 지속"]
    print(f"[3] {THRESHOLDS['loss_sustained_days']}일 경과({later_s}) -> 해당 {len(loss)}건: "
          f"{loss[0]['fact'] if loss else '-'}")
    assert len(loss) == 1 and loss[0]["symbol"] == "B"

    # 4) 회복하면 추적 초기화 (회복 후 재하락은 다시 0일부터)
    recovered = [dict(r, return_pct=-10.0) if r["symbol"] == "B" else r for r in snap["positions"]]
    s2 = update_loss_streaks(recovered, {"loss_since": dict(streaks)}, later_s)
    print(f"[4] B 회복(-10%) 후 추적: {s2}")
    assert "B" not in s2, "임계값 위로 회복하면 지속 기록이 지워져야 함"

    # 5) 예측성 필드가 리포트 어디에도 없는지 (재귀 검사)
    report, _ = build_report(real, {"placeholder": True}, {"loss_since": {}}, "2026-08-04")
    def scan(o, path="report"):
        bad = []
        if isinstance(o, dict):
            for k, v in o.items():
                if k in FORBIDDEN_FIELDS:
                    bad.append(f"{path}.{k}")
                bad += scan(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                bad += scan(v, f"{path}[{i}]")
        return bad
    found = scan(report)
    print(f"[5] 리포트 내 예측성 필드: {found or '없음'}")
    assert not found, f"예측성 필드가 리포트에 있음: {found}"

    # 6) 매매 지시성 표현이 텍스트에 없는지
    text = format_telegram(report)
    for banned in ("매수", "매도", "파세요", "사세요", "추천", "권장", "정리하세요"):
        assert banned not in text, f"리포트 텍스트에 매매 지시 표현 '{banned}'이 있음"
    print("[6] 텔레그램 텍스트: 매매 지시 표현 없음 확인")

    # 7) 로드맵은 placeholder면 계산하지 않는다 (틀린 숫자 방지)
    print(f"[7] 로드맵 상태: {report['roadmap']['status']} - {report['roadmap']['reason']}")
    assert report["roadmap"]["status"] == "미입력"

    # 8) 실계좌 파일을 쓰지 않는지
    src = open("portfolio_report.py", encoding="utf-8").read()
    for w in [f'save_json("{REAL_PORTFOLIO_FILE}', f"save_json('{REAL_PORTFOLIO_FILE}"]:
        assert w not in src, "real_portfolio.json에 쓰면 안 됨(읽기 전용)"
    print("[8] real_portfolio.json 쓰기 코드 없음 확인")

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    main()
