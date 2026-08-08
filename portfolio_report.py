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

def validate_allocation(income):
    """배분표 정합성 검사. 여기서 조용히 넘어가면 합이 90%인 표로 로드맵을 내고도
    아무도 모른다 — 리포트가 자신 있게 틀리는 걸 막는 게 목적이다."""
    alloc = income.get("allocation", {})
    classes = alloc.get("asset_classes", [])
    tiers = alloc.get("tiers", [])
    ranks = [r["rank"] for r in income.get("ranks", [])]
    problems = []

    for t in tiers:
        total = sum(float(t.get(c, 0)) for c in classes)
        if abs(total - 100.0) > 0.01:
            problems.append(f"{t.get('rank')} 배분 합계 {total:g}% (100%가 아님)")
        unknown = [k for k in t if k != "rank" and k not in classes]
        if unknown:
            problems.append(f"{t.get('rank')}에 정의되지 않은 자산군 {unknown}")

    tier_ranks = [t.get("rank") for t in tiers]
    for r in ranks:
        if r not in tier_ranks:
            problems.append(f"'{r}' 계급의 배분표가 없음")
    for r in tier_ranks:
        if r not in ranks:
            problems.append(f"배분표의 '{r}'가 수입 스케줄에 없음")
    return problems


def compute_roadmap(income):
    """수입 스케줄 → 계급별 투자가능액 → 계급 구간별 목표 배분.

    **배분 규칙을 코드에 내장하지 않는다.** income_schedule.json의
    allocation.tiers를 해석만 한다 — 표가 바뀌면 JSON만 고치면 되고, 코드가 표를
    '기억'하고 있어서 문서와 어긋나는 일이 생기지 않는다."""
    if income.get("placeholder"):
        return {"status": "미입력",
                "reason": "income_schedule.json이 placeholder 상태 - 계급별 기간/월수입 실제 값 필요"}

    ranks = income.get("ranks", [])
    missing = [r.get("rank") for r in ranks
               if not r.get("months") or r.get("monthly_krw") is None]
    if missing:
        return {"status": "미입력", "reason": f"수입 정보가 비어 있는 계급: {missing}"}

    problems = validate_allocation(income)
    if problems:
        return {"status": "배분표 오류", "reason": " / ".join(problems)}

    # 용돈 처리: monthly_krw가 이미 용돈을 뺀 값인지, 총액이라 빼야 하는지.
    # 15개월 x 30만 = 450만 차이라 총액의 4분의 1이 걸린 가정이므로 결과에 명시한다.
    allowance = float(income.get("excluded", {}).get("allowance_krw", 0) or 0)
    already_excluded = income.get("allowance_already_excluded", True)
    deduction = 0.0 if already_excluded else allowance

    tier_by_rank = {t["rank"]: t for t in income["allocation"]["tiers"]}
    classes = income["allocation"]["asset_classes"]

    dated, discrepancies = derive_months_from_dates(income)
    basis = income.get("month_basis", "declared")

    phases, cumulative, elapsed = [], 0.0, 0
    for r in ranks:
        monthly = float(r["monthly_krw"]) - deduction
        # 개월수 출처를 명시적으로 고른다. 두 값이 어긋나면 어느 쪽을 골랐든
        # discrepancies에 남아 리포트에 표시된다 — 조용히 한쪽을 쓰지 않는다.
        n = int(dated.get(r["rank"], {}).get("months", r["months"])) \
            if basis == "dates" else int(r["months"])
        subtotal = monthly * n
        cumulative += subtotal
        t = tier_by_rank[r["rank"]]
        if r.get("start"):
            s = datetime.strptime(r["start"], "%Y-%m")
            e = s.month - 1 + n - 1
            period = (f"{r['start']} ~ {s.year + e // 12}-{e % 12 + 1:02d}")
        else:
            period = f"{elapsed + 1}~{elapsed + n}개월차"
        phases.append({
            "rank": r["rank"],
            "period": period,
            "months": n,
            "monthly_investable_krw": round(monthly),
            "subtotal_krw": round(subtotal),
            "cumulative_krw": round(cumulative),
            "target_allocation_pct": {c: t.get(c, 0) for c in classes},
            "target_allocation_krw": {c: round(cumulative * t.get(c, 0) / 100) for c in classes},
        })
        elapsed += n

    has_dates = all(r.get("start") for r in ranks)
    return {
        "status": "계산됨",
        "total_months": elapsed,
        "total_investable_krw": round(cumulative),
        "allowance_krw": round(allowance),
        "allowance_already_excluded": already_excluded,
        "allowance_note": ("monthly_krw를 투자가능액으로 간주해 용돈을 추가 차감하지 않았음"
                           if already_excluded else
                           f"monthly_krw에서 용돈 {allowance:,.0f}원을 매달 차감함"),
        "date_basis": "절대 날짜" if has_dates else "상대(복무 개월차) - 계급별 start 미입력",
        "month_basis": basis,
        "month_basis_note": ("ranks[].months 선언값 사용" if basis == "declared"
                             else "진급 시점에서 역산한 개월수 사용"),
        "month_discrepancies": discrepancies,
        "schedule_warnings": validate_schedule(income),
        "schedule_anchor": income.get("schedule_anchor", {}),
        "service": income.get("service", {}),
        "asset_class_labels": income["allocation"].get("labels", {}),
        "phases": phases,
    }


def validate_schedule(income):
    """앵커 체이닝 결과가 복무 사실과 맞는지 본다.

    start를 months에서 산출하므로 둘은 어긋날 수 없지만, **체인 종료월이
    전역월을 넘어서는 경우**는 여전히 생긴다(선언 개월수 합이 남은 복무기간보다
    길 때). 조용히 넘어가면 전역 이후까지 수입이 잡힌 로드맵이 나온다."""
    problems = []
    ranks = income.get("ranks", [])
    svc = income.get("service", {})
    if not ranks or not all(r.get("start") for r in ranks):
        return problems

    def m(s):
        d = datetime.strptime(s, "%Y-%m")
        return d.year * 12 + d.month - 1

    # 구간이 연속인지 (앵커 체이닝이면 항상 참이어야 한다)
    for i in range(len(ranks) - 1):
        end = m(ranks[i]["start"]) + int(ranks[i]["months"])
        if end != m(ranks[i + 1]["start"]):
            nxt = ranks[i + 1]
            problems.append(
                f"{ranks[i]['rank']} 구간 종료 다음 달과 {nxt['rank']} 시작({nxt['start']})이 "
                f"이어지지 않음 — 빈 구간 또는 겹침")

    last = ranks[-1]
    chain_end = m(last["start"]) + int(last["months"]) - 1
    discharge = svc.get("discharge")
    if discharge:
        over = chain_end - m(discharge)
        if over > 0:
            problems.append(
                f"체인 종료 {chain_end//12}-{chain_end%12+1:02d}가 전역 가정 "
                f"{discharge}을 {over}개월 초과 — 전역 이후 구간까지 수입이 잡혀 있음 "
                f"(전역월 가정이 틀렸거나 선언 개월수가 실제와 다름)")
    enlisted = svc.get("enlisted")
    if enlisted and ranks:
        served_at_anchor = m(ranks[0]["start"]) - m(enlisted) + 1
        if served_at_anchor < 1:
            problems.append(f"첫 구간 시작({ranks[0]['start']})이 입대월({enlisted})보다 이름")
    return problems


def derive_months_from_dates(income):
    """계급별 start와 전역일에서 개월수를 역산한다. 마지막 계급은 전역일까지.

    선언된 months와 어긋나면 그 사실을 그대로 반환한다 — 둘 중 하나를 조용히
    이기게 두면 총 투자가능액이 소리 없이 달라진다(실제로 60만원 차이가 났다)."""
    ranks = income.get("ranks", [])
    discharge = income.get("service", {}).get("discharge")
    if not all(r.get("start") for r in ranks) or not discharge:
        return {}, []

    def m(s):
        d = datetime.strptime(s, "%Y-%m")
        return d.year * 12 + d.month

    # 앵커 체이닝을 쓰면 마지막 구간의 "역산"은 진급 시점 비교가 아니라 전역월
    # 가정과의 비교가 된다. 그건 validate_schedule()의 체인 종료 검사가 더
    # 정확하게 다루므로 여기서 중복 보고하지 않는다.
    anchored = bool(income.get("schedule_anchor", {}).get("anchor_month"))

    out, disc = {}, []
    for i, r in enumerate(ranks):
        is_last = i + 1 == len(ranks)
        if is_last and anchored:
            continue
        end = ranks[i + 1]["start"] if not is_last else discharge
        # 마지막 계급은 전역월 포함, 그 외는 다음 진급 직전까지
        n = m(end) - m(r["start"]) + (1 if is_last else 0)
        out[r["rank"]] = {"months": n, "start": r["start"], "end_exclusive": end}
        if int(r.get("months", n)) != n:
            disc.append({
                "rank": r["rank"],
                "declared_months": int(r["months"]),
                "derived_months": n,
                "note": (f"{r['rank']}: 선언 {r['months']}개월 vs "
                         f"진급시점 역산 {n}개월 ({r['start']} ~ {end})"),
            })
    return out, disc


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
    lines.append("")
    if rm.get("status") != "계산됨":
        lines.append(f"🗺️ 배분 로드맵: {rm['status']} — {rm['reason']}")
    else:
        labels = rm.get("asset_class_labels", {})
        lines.append(f"🗺️ 배분 로드맵 ({rm['total_months']}개월, 총 "
                     f"{rm['total_investable_krw']:,.0f}원 · {rm['date_basis']})")
        for ph in rm["phases"]:
            top = sorted(ph["target_allocation_pct"].items(), key=lambda kv: -kv[1])[:3]
            top_s = " ".join(f"{labels.get(k, k)} {v}%" for k, v in top)
            lines.append(f"   · {ph['rank']} ({ph['period']}) 누적 "
                         f"{ph['cumulative_krw']:,.0f}원 → {top_s} …")
        lines.append(f"   ※ 용돈 처리: {rm['allowance_note']}")
        anc = rm.get("schedule_anchor") or {}
        if anc.get("anchor_month"):
            lines.append(f"   ※ 기준: {anc['anchor_month']}부터 순차 배정 "
                         f"(고정값, 매달 밀리지 않음)")
        for w in rm.get("schedule_warnings", []):
            lines.append(f"   ⚠️ {w}")
        if rm.get("month_discrepancies"):
            lines.append(f"   ⚠️ 개월수 불일치 ({rm['month_basis_note']} 기준으로 계산됨)")
            for d in rm["month_discrepancies"]:
                lines.append(f"      · {d['note']}")
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

    # 7-b) 실제 배분표로 계산이 맞는지 (산술 검산)
    income = {
        "placeholder": False, "allowance_already_excluded": True,
        "ranks": [{"rank": "일병", "months": 5, "monthly_krw": 850000},
                  {"rank": "상병", "months": 6, "monthly_krw": 1150000},
                  {"rank": "병장", "months": 4, "monthly_krw": 1450000}],
        "excluded": {"allowance_krw": 300000},
        "allocation": {
            "asset_classes": ["bond", "developed_exUS", "emerging", "healthcare", "reit", "cash"],
            "tiers": [
                {"rank": "일병", "bond": 10, "developed_exUS": 20, "emerging": 15,
                 "healthcare": 25, "reit": 15, "cash": 15},
                {"rank": "상병", "bond": 20, "developed_exUS": 20, "emerging": 10,
                 "healthcare": 20, "reit": 10, "cash": 20},
                {"rank": "병장", "bond": 40, "developed_exUS": 10, "emerging": 5,
                 "healthcare": 10, "reit": 10, "cash": 25}]}}
    rm = compute_roadmap(income)
    print(f"[7b] 총 {rm['total_months']}개월 / 누적 {rm['total_investable_krw']:,}원")
    for ph in rm["phases"]:
        print(f"     {ph['rank']}: {ph['months']}개월 x {ph['monthly_investable_krw']:,} "
              f"= {ph['subtotal_krw']:,} (누적 {ph['cumulative_krw']:,})")
    assert rm["status"] == "계산됨"
    assert rm["total_months"] == 15
    assert rm["total_investable_krw"] == 5 * 850000 + 6 * 1150000 + 4 * 1450000 == 16950000
    assert rm["phases"][2]["target_allocation_krw"]["bond"] == round(16950000 * 0.40)

    # 7-c) 용돈을 차감하는 설정이면 실제로 줄어드는지
    rm2 = compute_roadmap(dict(income, allowance_already_excluded=False))
    print(f"[7c] 용돈 차감 시 누적 {rm2['total_investable_krw']:,}원 "
          f"(차이 {rm['total_investable_krw'] - rm2['total_investable_krw']:,})")
    assert rm["total_investable_krw"] - rm2["total_investable_krw"] == 300000 * 15

    # 7-d) 배분표가 100%가 아니면 계산을 거부하는지 (조용히 틀리지 않게)
    broken = json.loads(json.dumps(income))
    broken["allocation"]["tiers"][0]["bond"] = 5   # 합계 95%
    rm3 = compute_roadmap(broken)
    print(f"[7d] 합계 95% 표 -> {rm3['status']}: {rm3['reason']}")
    assert rm3["status"] == "배분표 오류" and "95" in rm3["reason"]

    # 7-e) 계급과 배분표가 어긋나면 잡아내는지
    mismatch = json.loads(json.dumps(income))
    mismatch["ranks"].append({"rank": "이병", "months": 2, "monthly_krw": 600000})
    rm4 = compute_roadmap(mismatch)
    print(f"[7e] 배분표 없는 계급 추가 -> {rm4['status']}: {rm4['reason']}")
    assert rm4["status"] == "배분표 오류" and "이병" in rm4["reason"]

    # 7-f) 진급 날짜와 선언 개월수가 어긋나면 조용히 넘어가지 않는지
    dated = json.loads(json.dumps(income))
    dated["service"] = {"enlisted": "2026-04", "discharge": "2027-09"}
    for r, st in zip(dated["ranks"], ["2026-07", "2027-01", "2027-07"]):
        r["start"] = st
    rm5 = compute_roadmap(dated)
    print(f"[7f] 불일치 {len(rm5['month_discrepancies'])}건, 기준={rm5['month_basis']}")
    for d in rm5["month_discrepancies"]:
        print(f"     {d['note']}")
    assert len(rm5["month_discrepancies"]) == 2, "일병/병장 불일치가 잡혀야 함"
    assert rm5["total_investable_krw"] == 16950000, "declared 기준이면 총액 불변이어야 함"

    # 기준을 dates로 바꾸면 총액이 실제로 달라지는지 (조용히 같으면 분기가 죽은 것)
    rm6 = compute_roadmap(dict(dated, month_basis="dates"))
    print(f"[7f] month_basis=dates -> 총 {rm6['total_investable_krw']:,}원 "
          f"(declared 대비 {rm6['total_investable_krw'] - rm5['total_investable_krw']:+,})")
    assert rm6["total_investable_krw"] == 6 * 850000 + 6 * 1150000 + 3 * 1450000 == 16350000
    assert rm6["month_discrepancies"], "dates 기준이어도 불일치 사실은 계속 표시돼야 함"

    # 7-g) 앵커 체이닝: 구간이 연속이고, 전역월 초과가 잡히는지
    anchored = json.loads(json.dumps(income))
    anchored["schedule_anchor"] = {"anchor_month": "2026-08"}
    anchored["service"] = {"enlisted": "2026-04", "discharge": "2027-09"}
    for r, st in zip(anchored["ranks"], ["2026-08", "2027-01", "2027-07"]):
        r["start"] = st
    rm7 = compute_roadmap(anchored)
    periods = [(p["rank"], p["period"]) for p in rm7["phases"]]
    print(f"[7g] 구간: {periods}")
    assert rm7["phases"][0]["period"] == "2026-08 ~ 2026-12"
    assert rm7["phases"][1]["period"] == "2027-01 ~ 2027-06"
    assert rm7["phases"][2]["period"] == "2027-07 ~ 2027-10"
    # 구간이 연속이므로 연속성 경고는 없어야 하고, 전역 초과만 잡혀야 한다
    warns = rm7["schedule_warnings"]
    print(f"     경고 {len(warns)}건: {warns}")
    assert len(warns) == 1 and "전역 가정" in warns[0] and "1개월 초과" in warns[0]
    # 앵커 모드에서는 마지막 구간 역산 불일치를 중복 보고하지 않는다
    assert not rm7["month_discrepancies"], f"중복 경고: {rm7['month_discrepancies']}"

    # 구간이 끊기면 잡아내는지 (일병만 한 달 앞당김 -> 빈 달 발생)
    broken_chain = json.loads(json.dumps(anchored))
    broken_chain["ranks"][0]["start"] = "2026-07"
    w2 = validate_schedule(broken_chain)
    print(f"[7g] 구간 끊김 주입 -> {len(w2)}건: {w2[0][:52]}...")
    assert any("이어지지 않음" in x for x in w2), "구간 불연속이 안 잡힘"

    # 8) 실계좌 파일을 쓰지 않는지
    src = open("portfolio_report.py", encoding="utf-8").read()
    for w in [f'save_json("{REAL_PORTFOLIO_FILE}', f"save_json('{REAL_PORTFOLIO_FILE}"]:
        assert w not in src, "real_portfolio.json에 쓰면 안 됨(읽기 전용)"
    print("[8] real_portfolio.json 쓰기 코드 없음 확인")

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    main()
