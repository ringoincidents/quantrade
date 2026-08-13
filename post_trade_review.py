"""[v3.2 활성 기능] 매매 사후 점검 리포트 — Layer 3 (2026-08-10, 방향성 세션 지시).

**예측이 아니다. 새 AI/LLM 호출이 없다.** v3.0 원칙2("AI는 뭘 살지 관여, 얼마나
살지는 Risk Engine이 결정")의 반대편 — 이미 일어난 매매를 사후에 점검한다.
다섯 항목(노출 변화/배분 괴리/상관관계 사각지대/행동 패턴/최근 뉴스 연결)
전부 이미 계산된 값(`real_portfolio.json`, `portfolio_report.py`의 순수 함수,
`news_event_cards.json`)을 재사용한 산술/사실 연결이며, 어디에서도 Claude API를
부르지 않는다 — 그래서 CLAUDE.md v3.2 (a) 리스크 가드레일과 같은 성격(결정론적,
판단 없음)이지 새로운 세 번째 AI 역할이 아니라고 이 모듈은 스스로를 설계했다
(다만 그 판정 자체는 방향성 세션 몫이라 여기 사실만 적는다 — "State facts,
don't render verdicts").

**불변 기록이다.** `post_trade_review_log.json`은 append-only 저널이다 — 한 번
쓰인 리포트는 이후 절대 수정하지 않는다. `audit()`가 금지 필드/문구를 하나라도
찾으면 저장 자체를 거부한다(`market_indicators.py`와 같은 "위반 시 전체 반려" —
불변 기록이라는 특성상 사후 정정이 불가능하므로 여기서 더 엄격하게 막는다).

**두 트리거, 같은 로직**:
- 배치(`run_batch`): `real_portfolio.json`이 직전 확인 시점(상태파일에 저장된
  스냅샷) 대비 보유종목이 늘거나 줄었거나, 어느 종목의 비중이
  `WEIGHT_CHANGE_THRESHOLD_PCT` 이상 바뀌었을 때만 생성한다 — 단순 가격 변동에
  따른 미세한 비중 흔들림까지 매번 리포트로 만들면 API 비용 절감이라는 목적과
  어긋나므로, "확실한 변동"만 걸러낸다. 이 임계값은 초안이다(`THRESHOLDS`처럼
  방향성 세션 확정 전까지 `provisional: true`).
- 온디맨드(`run_ondemand`, 텔레그램 `/review`): 변동 여부와 무관하게 항상 생성.
둘 다 `build_report()`를 그대로 호출한다.

**섹터 데이터는 없다.** 이 저장소에 연결된 섹터 분류 데이터 소스가 없으므로
(PER과 같은 이유, Phase3_펀더멘털신호_스펙.md §8-1) 노출 변화는 통화/국가
기준으로만 계산하고, 섹터는 `"데이터 소스 미연결"`로 명시한다. 목표 자산군
비중(로드맵의 bond/emerging/... 배분)과의 비교도 같은 이유로 계산하지 않는다
— 보유 종목을 그 자산군으로 분류할 데이터가 없다.
"""
import argparse
from datetime import datetime, timezone

import portfolio_report as pr
from analyze_lib import load_json, save_json

REAL_PORTFOLIO_FILE = "real_portfolio.json"
NEWS_CARDS_FILE = "news_event_cards.json"
STATE_FILE = "post_trade_review_state.json"
LOG_FILE = "post_trade_review_log.json"

# 배치 트리거 임계값. 방향성 세션 확정 전까지 초안(portfolio_report.THRESHOLDS와
# 같은 원칙) — 결과를 보고 사후에 맞추지 않는다.
WEIGHT_CHANGE_THRESHOLD_PCT = 3.0

# 이 리포트 전체(중첩 포함)에 절대 있으면 안 되는 필드/문구. audit()가 재귀 검사한다.
FORBIDDEN_FIELDS = ("direction", "confidence", "action", "recommendation",
                    "signal", "buy", "sell", "score", "target_weight_pct", "rating",
                    "rank", "ranking", "phase", "regime", "grade", "color", "colour")
FORBIDDEN_PHRASES = (
    "매수하세요", "매도하세요", "사세요", "파세요", "추천", "권장", "권합니다",
    "유망", "저평가", "고평가", "목표주가", "상승 전망", "하락 전망",
    "전망됩니다", "예상됩니다", "기대됩니다", "판단됩니다",
    "지금이 기회", "그래서 사도", "팔아야 합니다", "1위", "순위",
)


# ── 노출 변화 (섹션 1) ───────────────────────────────────────────────────

def compute_exposure(real, total_assets_krw=None):
    """통화/국가별 노출 비중. 섹터는 데이터 소스가 없어 계산하지 않는다."""
    positions = real.get("positions", [])
    cash = float(real.get("cash", 0) or 0)
    total = total_assets_krw if total_assets_krw is not None else (
        cash + sum(float(p.get("eval_amount_krw") or 0) for p in positions))
    by_currency, by_country = {}, {}
    for p in positions:
        amt = float(p.get("eval_amount_krw") or 0)
        cur = p.get("currency") or "미분류"
        country = p.get("market_country") or "미분류"
        by_currency[cur] = by_currency.get(cur, 0) + amt
        by_country[country] = by_country.get(country, 0) + amt
    pct = lambda d: {k: round(v / total * 100, 2) for k, v in d.items()} if total else {}
    return {"by_currency_pct": pct(by_currency), "by_country_pct": pct(by_country),
            "sector_status": "데이터 소스 미연결"}


def diff_exposure(prev_real, curr_real, curr_exposure):
    """직전 스냅샷 대비 노출 변화. prev_real이 없으면(최초 실행) 현재 상태만 기록한다."""
    curr_syms = {p["symbol"] for p in curr_real.get("positions", [])}
    if prev_real is None:
        return {
            "has_baseline": False,
            "added_symbols": [], "removed_symbols": [],
            "by_currency_pct_now": curr_exposure["by_currency_pct"],
            "by_country_pct_now": curr_exposure["by_country_pct"],
            "by_currency_pct_delta": None, "by_country_pct_delta": None,
            "sector_status": curr_exposure["sector_status"],
        }
    prev_exposure = compute_exposure(prev_real)
    prev_syms = {p["symbol"] for p in prev_real.get("positions", [])}

    def delta(prev_d, curr_d):
        keys = set(prev_d) | set(curr_d)
        return {k: round(curr_d.get(k, 0) - prev_d.get(k, 0), 2) for k in sorted(keys)}

    return {
        "has_baseline": True,
        "added_symbols": sorted(curr_syms - prev_syms),
        "removed_symbols": sorted(prev_syms - curr_syms),
        "by_currency_pct_now": curr_exposure["by_currency_pct"],
        "by_country_pct_now": curr_exposure["by_country_pct"],
        "by_currency_pct_delta": delta(prev_exposure["by_currency_pct"], curr_exposure["by_currency_pct"]),
        "by_country_pct_delta": delta(prev_exposure["by_country_pct"], curr_exposure["by_country_pct"]),
        "sector_status": curr_exposure["sector_status"],
    }


def has_material_change(prev_real, curr_real):
    """배치 트리거 판정. 종목 추가/제거는 무조건 변동으로 본다 — 가장 확실한
    매매 신호이기 때문이다. 그 외엔 종목별 비중이 임계값 이상 바뀌었을 때만
    "변동"으로 친다 — 단순 가격 변동에 따른 미세한 흔들림까지 매번 리포트를
    만들면 API 비용 절감이라는 목적과 어긋난다."""
    if prev_real is None:
        return False  # 비교 대상 자체가 없음 - "변동"을 판정할 수 없다
    prev_rows = {p["symbol"]: p for p in prev_real.get("positions", [])}
    curr_rows = {p["symbol"]: p for p in curr_real.get("positions", [])}
    if set(prev_rows) != set(curr_rows):
        return True
    prev_total = float(prev_real.get("cash", 0) or 0) + sum(
        float(p.get("eval_amount_krw") or 0) for p in prev_rows.values())
    curr_total = float(curr_real.get("cash", 0) or 0) + sum(
        float(p.get("eval_amount_krw") or 0) for p in curr_rows.values())
    for sym, p in curr_rows.items():
        prev_w = (float(prev_rows[sym].get("eval_amount_krw") or 0) / prev_total * 100) if prev_total else 0.0
        curr_w = (float(p.get("eval_amount_krw") or 0) / curr_total * 100) if curr_total else 0.0
        if abs(curr_w - prev_w) >= WEIGHT_CHANGE_THRESHOLD_PCT:
            return True
    return False


# ── 배분 규칙 대비 괴리 (섹션 2) ──────────────────────────────────────────

def compute_allocation_gap(rows, today):
    """portfolio_report.py의 집중도 규칙을 그대로 재사용한다. streaks를 빈
    dict로 넘기면 "손실 지속" 규칙은 걸리지 않는다(그건 섹션 4에서 별도
    상태로 다룬다) — evaluate_rules가 streaks.get(symbol)이 없으면 그 규칙을
    건너뛰는 동작을 그대로 이용한다."""
    matches = [m for m in pr.evaluate_rules(rows, {}, today) if m["rule"] == "집중도"]
    return {
        "concentration_matches": matches,
        "asset_class_target_status": ("데이터 소스 미연결 — 보유 종목을 로드맵의 "
                                       "자산군(bond/developed_exUS/emerging/...)으로 "
                                       "분류할 데이터가 없어 국가/통화 노출만 비교합니다."),
    }


# ── 상관관계 사각지대 (섹션 3) ────────────────────────────────────────────

def find_correlation_blind_spots(rows, flagged_pairs):
    """이미 계산된 상관계수(Risk Engine과 같은 함수)에서, 국가가 달라 겉보기엔
    분산된 것처럼 보이는데 상관계수는 기준 이상인 쌍만 사실로 연결한다."""
    row_by_symbol = {r["symbol"]: r for r in rows}
    spots = []
    for f in flagged_pairs:
        a, b = row_by_symbol.get(f["symbol_a"]), row_by_symbol.get(f["symbol_b"])
        if not a or not b:
            continue
        looks_diversified = a.get("market_country") != b.get("market_country")
        if not looks_diversified:
            continue
        spots.append({
            "symbol_a": f["symbol_a"], "name_a": a["name"],
            "symbol_b": f["symbol_b"], "name_b": b["name"],
            "correlation": f["correlation"],
            "fact": (f"{a['name']}({a.get('market_country') or '-'})과 {b['name']}"
                     f"({b.get('market_country') or '-'})은 국가가 달라 분산된 것처럼 "
                     f"보이지만, 최근 상관계수가 {f['correlation']:+.2f}로 기준(0.7) 이상입니다."),
        })
    return spots


# ── 행동 패턴 (섹션 4) ────────────────────────────────────────────────────

def describe_behavior_patterns(rows, streaks, today):
    """portfolio_report.py의 "손실 지속" 규칙(THRESHOLDS.loss_pct/loss_sustained_days,
    update_loss_streaks)을 재사용한다. analyze_lib.HARD_STOP_LOSS는 strategy_type
    (단타/스윙/장기) 분류가 있어야 쓸 수 있는데 real_portfolio.json 보유종목에는
    그 분류가 없어 여기선 쓸 수 없다 — 그래서 실계좌에도 이미 적용되는
    portfolio_report.py 쪽 규칙을 쓴다. "회피"처럼 의도를 진단하는 단어는 쓰지
    않는다 — 지속 일수와 "그 사이 매도 없이 유지"라는 관측 사실만 적는다."""
    today_dt = datetime.strptime(today, "%Y-%m-%d")
    facts = []
    for r in rows:
        since = streaks.get(r["symbol"])
        if not since:
            continue
        days = (today_dt - datetime.strptime(since, "%Y-%m-%d")).days
        facts.append({
            "symbol": r["symbol"], "name": r["name"],
            "return_pct": r["return_pct"],
            "threshold_pct": pr.THRESHOLDS["loss_pct"],
            "days_since_threshold": days,
            "fact": (f"{r['name']}({r['symbol']}) 평가손익 {r['return_pct']:.2f}%가 "
                     f"기준 {pr.THRESHOLDS['loss_pct']:.0f}% 이하로 {since}부터 {days}일째이며, "
                     f"그 사이 매도 없이 보유가 유지되고 있습니다."),
        })
    return facts


# ── 최근 뉴스 연결 (섹션 5) ───────────────────────────────────────────────

def connect_recent_news(rows, news_cards):
    """news_event_cards.json은 이미 생성·감사를 거친 파일이다 — 여기서는 새로
    만들지 않고 읽기만 하며, 보유 종목과 겹치는 카드만 사실로 연결한다.

    2026-08-10: 이 함수를 만들다가 실제로 커밋된 news_event_cards.json 한 건에
    "목표주가를 상향 조정했다"가 그대로 남아 있는 걸 발견했다(news_event_cards.py는
    금지 필드만 걸렀고 summary 문구는 검사한 적이 없었음 — 같은 커밋에서 그쪽도
    고쳤다). 그 생산자 쪽 수정과 별개로, 여기서도 인용하기 직전에 한 번 더
    검사한다 — 업스트림이 이미 오염된 과거 파일을 갖고 있거나 앞으로 같은 종류의
    구멍이 다시 생겨도, 그 카드 하나만 조용히 빼고 나머지 리포트는 정상 생성되게
    하기 위해서다(불변 저널 전체를 막는 대신 방어적으로 걸러낸다)."""
    row_by_symbol = {r["symbol"]: r for r in rows}
    links = []
    for card in news_cards.get("cards", []):
        r = row_by_symbol.get(card.get("market"))
        if not r:
            continue
        fact = (f"{r['name']}({card['market']}) 비중이 {r['weight_pct']:.1f}%인 상태에서 "
                f"최근 {card.get('event_type') or '기타'} 관련 사실이 있었습니다: "
                f"{card.get('summary') or ''}")
        if any(ph in fact for ph in FORBIDDEN_PHRASES):
            print(f"⚠️ {card.get('market')}: 뉴스 카드 문구가 자체 검사에 걸려 이 리포트에서 제외됨")
            continue
        links.append({
            "symbol": card["market"], "name": r["name"], "weight_pct": r["weight_pct"],
            "event_type": card.get("event_type"), "summary": card.get("summary"),
            "fact": fact,
        })
    return links


# ── 리포트 조립 ───────────────────────────────────────────────────────────

def build_report(real, prev_real, news_cards, state, trigger, today=None, symbol_closes=None):
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated_at = datetime.now(timezone.utc).isoformat()

    snapshot = pr.compute_positions(real)
    rows = snapshot["positions"]

    exposure_now = compute_exposure(real, snapshot["total_assets_krw"])
    exposure_change = diff_exposure(prev_real, real, exposure_now)

    allocation_gap = compute_allocation_gap(rows, today)

    if symbol_closes is None:
        symbol_closes = pr.fetch_symbol_candles(rows)
    returns_by_symbol = {
        sym: pr.calc_daily_returns(closes)[-pr.RISK_ENGINE["correlation_lookback_days"]:]
        for sym, closes in symbol_closes.items()
    }
    correlation = pr.calc_correlation_matrix(returns_by_symbol) if len(returns_by_symbol) >= 2 else {
        "lookback_days": pr.RISK_ENGINE["correlation_lookback_days"], "matrix": {}, "flagged_pairs": [],
        "flag_threshold": pr.RISK_ENGINE["correlation_flag_threshold"],
    }
    blind_spots = find_correlation_blind_spots(rows, correlation.get("flagged_pairs", []))

    streaks = pr.update_loss_streaks(rows, state, today)
    behavior_patterns = describe_behavior_patterns(rows, streaks, today)

    recent_news_links = connect_recent_news(rows, news_cards)

    report = {
        "id": f"review-{generated_at}",
        "generated_at": generated_at,
        "trigger": trigger,
        "schema": "post_trade_review_v3.2",
        "note": ("매매 이후 사람이 놓쳤을 수 있는 것을 사후에 짚어보는 기록입니다. "
                 "새 AI 판단이나 매매 제안이 아니라 이미 계산된 값을 재사용한 사실 "
                 "연결이며, 생성 시점에 확정되고 이후 수정되지 않습니다."),
        "exposure_change": exposure_change,
        "allocation_gap": allocation_gap,
        "correlation_blind_spots": {
            "flag_threshold": pr.RISK_ENGINE["correlation_flag_threshold"],
            "lookback_days": pr.RISK_ENGINE["correlation_lookback_days"],
            "spots": blind_spots,
        },
        "behavior_patterns": behavior_patterns,
        "recent_news_links": recent_news_links,
    }
    return report, streaks


def audit(obj, path="report"):
    """금지 필드/문구가 섞였는지 재귀 검사(market_indicators.py/rule_trigger_report.py와
    같은 패턴). 불변 저널이라 이 함수가 유일한 사후 방어선이다."""
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


def _append_and_save(report):
    """append-only. 기존 항목은 절대 수정하지 않는다. 위반이 있으면 저장 자체를
    거부한다(SystemExit) — 한 번 저널에 들어가면 사후 정정이 불가능하므로."""
    violations = audit(report)
    if violations:
        print("❌ 감사 위반 발견 - 저장 거부(불변 저널에는 위반 항목을 남길 수 없음):")
        for v in violations:
            print(f"   - {v}")
        raise SystemExit(1)
    log = load_json(LOG_FILE, {"reports": []})
    log["reports"].append(report)
    save_json(LOG_FILE, log)
    return report


def run_batch():
    """배치 트리거: 변동이 있을 때만 생성한다."""
    real = load_json(REAL_PORTFOLIO_FILE, None)
    if not real:
        print(f"⚠️ {REAL_PORTFOLIO_FILE} 없음 - sync_real.yml 실행 후 다시 시도")
        return None

    state = load_json(STATE_FILE, {"loss_since": {}, "last_snapshot": None})
    prev_real = state.get("last_snapshot")

    if prev_real is None:
        print("최초 실행 - 비교 대상 스냅샷이 없어 변동 여부를 판정할 수 없습니다. "
              "베이스라인만 저장하고 리포트는 생성하지 않습니다.")
        state["last_snapshot"] = real
        save_json(STATE_FILE, state)
        return None

    if not has_material_change(prev_real, real):
        print(f"변동 없음(임계 {WEIGHT_CHANGE_THRESHOLD_PCT}%p 미만, 종목 추가/제거 없음) - 리포트 생성 생략")
        return None

    news_cards = load_json(NEWS_CARDS_FILE, {"cards": []})
    report, streaks = build_report(real, prev_real, news_cards, state, trigger="batch")
    state["loss_since"] = streaks
    state["last_snapshot"] = real
    _append_and_save(report)
    save_json(STATE_FILE, state)
    print(f"리포트 생성됨 → {LOG_FILE} (트리거: batch)")
    return report


def run_ondemand():
    """온디맨드 트리거(텔레그램 /review): 변동 여부와 무관하게 항상 생성한다."""
    real = load_json(REAL_PORTFOLIO_FILE, None)
    if not real:
        return {"error": f"{REAL_PORTFOLIO_FILE} 없음 - 아직 계좌 동기화가 되지 않았습니다."}

    state = load_json(STATE_FILE, {"loss_since": {}, "last_snapshot": None})
    prev_real = state.get("last_snapshot")
    news_cards = load_json(NEWS_CARDS_FILE, {"cards": []})
    report, streaks = build_report(real, prev_real, news_cards, state, trigger="ondemand")
    state["loss_since"] = streaks
    state["last_snapshot"] = real
    _append_and_save(report)
    save_json(STATE_FILE, state)
    return report


def render_telegram(report):
    """온디맨드 요청에 대한 응답 메시지 전용 — 이건 사람이 요청한 응답이지
    자동 푸시가 아니다(지시서 §2). 배치 트리거는 텔레그램으로 보내지 않는다."""
    if "error" in report:
        return f"⚠️ {report['error']}"

    lines = [f"🗒️ 매매 사후 점검 리포트 ({report['generated_at'][:16].replace('T', ' ')} UTC)", ""]

    ec = report["exposure_change"]
    if ec["has_baseline"]:
        if ec["added_symbols"]:
            lines.append(f"➕ 신규 편입: {', '.join(ec['added_symbols'])}")
        if ec["removed_symbols"]:
            lines.append(f"➖ 편출: {', '.join(ec['removed_symbols'])}")
        cur_delta = ", ".join(f"{k} {v:+.1f}%p" for k, v in ec["by_currency_pct_delta"].items())
        if cur_delta:
            lines.append(f"통화 노출 변화: {cur_delta}")
    else:
        lines.append("비교 대상 스냅샷 없음 - 현재 상태만 기록")
    if ec["by_currency_pct_now"]:
        lines.append("현재 통화 노출: " + ", ".join(f"{k} {v:.1f}%" for k, v in ec["by_currency_pct_now"].items()))
    lines.append("")

    ag = report["allocation_gap"]
    if ag["concentration_matches"]:
        lines.append("📐 집중도 기준 초과:")
        for m in ag["concentration_matches"]:
            lines.append(f"   · {m['fact']}")
    else:
        lines.append("📐 집중도 기준 초과 없음")
    lines.append("")

    spots = report["correlation_blind_spots"]["spots"]
    if spots:
        lines.append("🔗 상관관계 사각지대:")
        for s in spots:
            lines.append(f"   · {s['fact']}")
    else:
        lines.append("🔗 상관관계 사각지대 없음")
    lines.append("")

    bp = report["behavior_patterns"]
    if bp:
        lines.append("📌 보유 패턴:")
        for b in bp:
            lines.append(f"   · {b['fact']}")
    else:
        lines.append("📌 특이 보유 패턴 없음")
    lines.append("")

    news = report["recent_news_links"]
    if news:
        lines.append("📰 최근 뉴스 연결:")
        for n in news[:5]:
            lines.append(f"   · {n['fact']}")
        lines.append("")

    lines.append("※ 사실 기록이며 매매 판단/제안이 아닙니다.")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="매매 사후 점검 리포트 (Layer 3, 예측/신규 AI판단 아님)")
    p.add_argument("--batch", action="store_true", help="배치 트리거: 변동 있을 때만 생성")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        run_self_test()
        return
    if a.batch:
        run_batch()
    else:
        report = run_ondemand()
        print(render_telegram(report))


def run_self_test():
    print("=== post_trade_review.py 자체 검증 (네트워크 미사용) ===\n")

    real_a = {"cash": 100000.0, "positions": [
        {"symbol": "K1", "name": "국내종목", "market_country": "KR", "currency": "KRW", "eval_amount_krw": 500000.0, "return_pct": 2.0},
        {"symbol": "U1", "name": "해외종목", "market_country": "US", "currency": "USD", "eval_amount_krw": 400000.0, "return_pct": -3.0},
    ]}

    # 1) has_material_change: 베이스라인 없으면 False(판정 불가), 동일 스냅샷이면 False
    assert has_material_change(None, real_a) is False
    assert has_material_change(real_a, real_a) is False
    print("[1] 베이스라인 없음/동일 스냅샷 -> 변동 없음 확인")

    # 2) 종목 추가/제거는 무조건 변동
    real_added = {"cash": 100000.0, "positions": real_a["positions"] + [
        {"symbol": "K2", "name": "신규종목", "market_country": "KR", "currency": "KRW", "eval_amount_krw": 100000.0, "return_pct": 0.0}]}
    assert has_material_change(real_a, real_added) is True
    real_removed = {"cash": 100000.0, "positions": real_a["positions"][:1]}
    assert has_material_change(real_a, real_removed) is True
    print("[2] 종목 추가/제거 -> 변동 있음 확인")

    # 3) 비중이 임계값 이상/미만 바뀌는 경우
    real_small_shift = {"cash": 100000.0, "positions": [
        {"symbol": "K1", "name": "국내종목", "market_country": "KR", "currency": "KRW", "eval_amount_krw": 510000.0, "return_pct": 2.0},
        {"symbol": "U1", "name": "해외종목", "market_country": "US", "currency": "USD", "eval_amount_krw": 390000.0, "return_pct": -3.0},
    ]}
    assert has_material_change(real_a, real_small_shift) is False, "임계값(3%p) 미만 변화는 무시해야 함"
    real_big_shift = {"cash": 100000.0, "positions": [
        {"symbol": "K1", "name": "국내종목", "market_country": "KR", "currency": "KRW", "eval_amount_krw": 700000.0, "return_pct": 2.0},
        {"symbol": "U1", "name": "해외종목", "market_country": "US", "currency": "USD", "eval_amount_krw": 200000.0, "return_pct": -3.0},
    ]}
    assert has_material_change(real_a, real_big_shift) is True, "임계값 이상 변화는 잡아야 함"
    print("[3] 비중 변화 임계값(3%p) 경계 동작 확인")

    # 4) 노출 계산/변화량 산술 검산
    exp_a = compute_exposure(real_a)
    print(f"[4] 노출: 통화={exp_a['by_currency_pct']} / 국가={exp_a['by_country_pct']} / 섹터={exp_a['sector_status']}")
    assert abs(exp_a["by_currency_pct"]["KRW"] - 500000 / 1000000 * 100) < 0.01, \
        "노출 비중은 현금을 포함한 총자산 대비여야 함(portfolio_report.compute_positions와 같은 분모)"
    assert exp_a["sector_status"] == "데이터 소스 미연결"
    change = diff_exposure(real_a, real_big_shift, compute_exposure(real_big_shift))
    print(f"[4] 통화 노출 변화: {change['by_currency_pct_delta']}")
    assert change["has_baseline"] is True
    assert change["by_currency_pct_delta"]["KRW"] > 0, "국내 비중이 늘었으면 델타도 양수여야 함"

    # 4b) 베이스라인 없을 때는 현재 상태만, delta는 None
    change_no_base = diff_exposure(None, real_a, exp_a)
    print(f"[4b] 베이스라인 없음 -> has_baseline={change_no_base['has_baseline']}, delta={change_no_base['by_currency_pct_delta']}")
    assert change_no_base["has_baseline"] is False and change_no_base["by_currency_pct_delta"] is None

    # 5) 상관관계 사각지대: 국가 다른 쌍만 잡히고, 같은 국가는 안 잡힘
    rows = [
        {"symbol": "A", "name": "가", "market_country": "KR"},
        {"symbol": "B", "name": "나", "market_country": "US"},
        {"symbol": "C", "name": "다", "market_country": "KR"},
    ]
    flagged = [{"symbol_a": "A", "symbol_b": "B", "correlation": 0.82},
               {"symbol_a": "A", "symbol_b": "C", "correlation": 0.75}]
    spots = find_correlation_blind_spots(rows, flagged)
    print(f"[5] 사각지대: {[(s['symbol_a'], s['symbol_b']) for s in spots]}")
    assert len(spots) == 1 and spots[0]["symbol_a"] == "A" and spots[0]["symbol_b"] == "B", \
        "국가가 다른 쌍(A-B)만 사각지대로 잡혀야 함(A-C는 같은 국가라 겉보기부터 분산 아님)"
    for banned in ("매수", "회피"):
        assert banned not in spots[0]["fact"]

    # 6) 행동 패턴: 손실 지속 종목만 fact가 생기고, "회피" 같은 의도 진단 단어가 없는지
    rows2 = [{"symbol": "L1", "name": "손실종목", "return_pct": -60.0},
             {"symbol": "N1", "name": "정상종목", "return_pct": 3.0}]
    state = {"loss_since": {}}
    streaks = pr.update_loss_streaks(rows2, state, "2026-08-01")
    later = "2026-10-01"
    facts = describe_behavior_patterns(rows2, streaks, later)
    print(f"[6] 행동 패턴: {[f['symbol'] for f in facts]}")
    assert [f["symbol"] for f in facts] == ["L1"], "손실 지속 종목만 잡혀야 함"
    assert facts[0]["days_since_threshold"] == (
        datetime.strptime(later, "%Y-%m-%d") - datetime.strptime("2026-08-01", "%Y-%m-%d")).days
    for banned in ("회피", "매수하세요", "매도하세요"):
        assert banned not in facts[0]["fact"]
    print("[6] 금지 문구(회피 등) 없음 확인")

    # 7) 최근 뉴스 연결: 보유 종목과 겹치는 카드만 연결되는지
    news_cards = {"cards": [
        {"market": "K1", "event_type": "공시", "summary": "테스트 공시 발생"},
        {"market": "ZZZ", "event_type": "기타", "summary": "보유하지 않은 종목 뉴스"},
    ]}
    rows3 = pr.compute_positions(real_a)["positions"]
    links = connect_recent_news(rows3, news_cards)
    print(f"[7] 뉴스 연결: {[l['symbol'] for l in links]}")
    assert [l["symbol"] for l in links] == ["K1"], "보유 종목(K1)만 연결되고 미보유(ZZZ)는 제외돼야 함"

    # 7b) [2026-08-10] 업스트림(news_event_cards.json)에 이미 금지 문구가 남아
    # 있어도(예: 과거 파일, 또는 다시 생기는 구멍) 그 카드만 조용히 빠지고
    # 나머지 리포트는 정상 생성되는지 — 실제로 커밋된 파일에서 "목표주가"가
    # 남아 있던 걸 발견해 추가한 방어선.
    contaminated_news = {"cards": [
        {"market": "K1", "event_type": "공시", "summary": "회사가 목표주가를 상향 조정했다"},
        {"market": "U1", "event_type": "기타", "summary": "정상 사실 설명"},
    ]}
    links2 = connect_recent_news(rows3, contaminated_news)
    print(f"[7b] 오염된 업스트림 카드 -> {[l['symbol'] for l in links2]}")
    assert [l["symbol"] for l in links2] == ["U1"], "금지 문구가 섞인 카드(K1)는 빠지고 U1만 남아야 함"

    # 8) audit() — 금지 필드/문구를 재귀적으로 잡아내는지
    dirty = {"behavior_patterns": [{"symbol": "K1", "action": "매도"}],
             "recent_news_links": [{"fact": "지금이 기회입니다"}]}
    violations = audit(dirty)
    print(f"[8] 오염된 리포트 -> 위반 {violations}")
    assert any("action" in v for v in violations)
    assert any("지금이 기회" in v for v in violations)

    # 9) 정상 build_report() 결과가 자체 감사를 통과하는지(네트워크 없이 - symbol_closes={})
    report, _ = build_report(real_a, None, news_cards, {"loss_since": {}}, "batch",
                              today="2026-08-10", symbol_closes={})
    clean_violations = audit(report)
    print(f"[9] 정상 build_report() 결과 감사 -> 위반 {clean_violations}")
    assert clean_violations == [], f"정상 리포트인데 위반이 잡힘: {clean_violations}"
    assert report["trigger"] == "batch"
    assert set(report) >= {"id", "generated_at", "exposure_change", "allocation_gap",
                            "correlation_blind_spots", "behavior_patterns", "recent_news_links"}

    # 10) 위반 시 전체 반려 — save_json이 호출되지 않고 SystemExit이 나야 한다(불변 저널 원칙)
    import sys
    import unittest.mock as mock
    mod = sys.modules[__name__]
    with mock.patch.object(mod, "save_json") as mock_save, \
         mock.patch.object(mod, "load_json", return_value={"reports": []}):
        try:
            _append_and_save(dirty)
            raised = False
        except SystemExit:
            raised = True
        print(f"[10] 오염된 리포트로 _append_and_save 호출 -> SystemExit={raised}, save_json 호출됨={mock_save.called}")
        assert raised, "위반이 있는데 SystemExit이 발생하지 않음"
        assert not mock_save.called, "위반이 있는데 save_json이 호출됨(불변 저널 원칙 위반)"

    # 11) 정상 리포트는 append-only로 실제 저장 경로를 타는지 (기존 항목 보존 확인)
    existing_log = {"reports": [{"id": "review-old", "note": "이전 리포트"}]}
    with mock.patch.object(mod, "save_json") as mock_save, \
         mock.patch.object(mod, "load_json", return_value=existing_log):
        result = _append_and_save(report)
        saved_arg = mock_save.call_args[0][1]
        print(f"[11] 저장된 저널 길이={len(saved_arg['reports'])} (기존 1건 + 신규 1건)")
        assert len(saved_arg["reports"]) == 2, "기존 항목을 덮어쓰지 않고 append해야 함"
        assert saved_arg["reports"][0] == existing_log["reports"][0], "기존 항목이 수정되면 안 됨(불변)"
        assert result is report

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    main()
