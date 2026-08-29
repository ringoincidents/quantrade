from datetime import datetime, timezone
from analyze_lib import *  # FORBIDDEN_FIELDS_BASE/FORBIDDEN_PHRASES_BASE도 여기로 들어온다

PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "trade_history.json"
PENDING_FILE = "pending_actions.json"
TOTAL_BUDGET = 100000
MIN_CASH_RESERVE_RATIO = 0.3  # 리스크자산 노출 상한 70% (2026-08-01: 0.2->0.3, Phase 1 게이트 미통과 반영)


def check_risk_guardrails(portfolio, total_assets):
    """[v3.2 신규 — 활성 기능] 규칙 기반 가드레일 위반 점검.

    **결정론적이다. AI 판단이 전혀 개입하지 않는다** — 사전에 정해진 상수
    (POSITION_WEIGHT_HARD_CAP, MIN_CASH_RESERVE_RATIO)와 현재 보유 상태를
    산술 비교할 뿐이다. 그래서 §2.1 통계 게이트 적용 대상이 아니다.

    **반환 항목에는 "무엇이 어떤 규칙을 얼마나 넘었나"라는 사실만 담는다.**
    어떤 종목을 사라/팔라는 제안 문구는 절대 넣지 않는다(CLAUDE.md v3.2 (b) 원칙).
    구조적으로도 제안 필드를 두지 않아, 나중에 예측성 내용이 슬쩍 끼어드는 걸
    스키마 수준에서 막는다.

    2026-08-28: 크립토 모의포지션 로직 폐기와 함께 여기 있던 "크립토는 이
    목록에서 뺀다"는 필터를 걷어냈다 — 폐기 대상 자체가 없어졌으므로 필터도
    무의미해졌다. 이제 portfolio.json에 남아있는(원칙상 stock/krx만) 포지션을
    그대로 검사한다."""
    violations = []
    if total_assets <= 0:
        return violations

    for p in portfolio["positions"]:
        weight = p["amount_krw"] / total_assets
        if weight >= POSITION_WEIGHT_HARD_CAP:
            violations.append({
                "rule": "종목별 비중 상한",
                "market": p["market"],
                "limit_pct": round(POSITION_WEIGHT_HARD_CAP * 100, 1),
                "actual_pct": round(weight * 100, 1),
                "fact": (f"{p['market']} 비중이 총자산의 {weight*100:.1f}%로 "
                         f"상한 {POSITION_WEIGHT_HARD_CAP*100:.0f}%를 초과"),
            })

    cash_ratio = portfolio["cash"] / total_assets
    if cash_ratio < MIN_CASH_RESERVE_RATIO:
        violations.append({
            "rule": "최소 현금 비율",
            "market": None,
            "limit_pct": round(MIN_CASH_RESERVE_RATIO * 100, 1),
            "actual_pct": round(cash_ratio * 100, 1),
            "fact": (f"현금 비율이 {cash_ratio*100:.1f}%로 "
                     f"하한 {MIN_CASH_RESERVE_RATIO*100:.0f}% 미만"),
        })

    return violations


def audit_guardrail_violations(violations):
    """[2026-08-10 "자유텍스트 금지문구 전수 점검"으로 신설] check_risk_guardrails()의
    "fact" 문구를 재사용 금지어 세트로 검사한다. market_indicators.py 등과 달리
    위반 시 전체 실행을 막지 않는다 — 이 함수의 출력은 하드손절 집행 등 실제
    거래 로직과 무관한 표시용 텍스트뿐이고, daily.yml 전체를 막으면 표시 텍스트
    문제 때문에 정작 중요한 손절 집행/자산 갱신까지 멈추는 게 더 위험하다.
    대신 위반이 걸린 항목의 fact만 안전한 문구로 바꾸고 계속 진행한다("빈
    칸이 틀린 텍스트보다 낫다" 원칙, rule_trigger_report.py 등과 동일)."""
    clean = []
    for v in violations:
        fact = v.get("fact", "")
        hit = next((ph for ph in FORBIDDEN_PHRASES_BASE if ph in fact), None)
        if hit:
            print(f"⚠️ 가드레일 fact 문구가 금지어 검사에 걸림 - 표시용 텍스트만 대체 ('{hit}'): {fact}")
            v = dict(v, fact="[표시 생략 - 금지 문구 감지로 검수 실패]")
        clean.append(v)
    return clean


def needs_approval(pos, total_assets):
    if pos.get("strategy_type") == "장기":
        return True
    if pos.get("asset_class") in ("stock", "krx"):
        return True
    if total_assets > 0 and (pos["amount_krw"] / total_assets) >= AUTO_TIER_WEIGHT:
        return True
    return False


def run():
    portfolio = load_json(PORTFOLIO_FILE, {"cash": TOTAL_BUDGET, "positions": []})
    history = load_json(HISTORY_FILE, {"trades": []})
    pending = load_json(PENDING_FILE, {"actions": []})
    today = datetime.now().strftime("%Y-%m-%d")
    report = [f"📅 {today} 통합 포트폴리오 리포트", ""]

    total_assets = portfolio["cash"] + sum(p["amount_krw"] for p in portfolio["positions"])

    real_portfolio = load_json("real_portfolio.json", {"positions": []})
    real_positions = real_portfolio.get("positions", [])

    # ─────────────────────────────────────────────────────────────────────
    # [기각된 연구 결과, 활성 기능 제외 — v3.2] 예측 경로.
    # entry_score 기반 후보 스캔 + ask_claude_decision의 BUY/SELL 방향 판단은
    # §2.1 게이트 미통과로 비활성이다(analyze_lib.PREDICTION_ENABLED, 기본 False).
    # 코드는 재개 대비 + 기각 사유 재구성 목적으로 보존한다 — 삭제 금지.
    # ─────────────────────────────────────────────────────────────────────
    all_cands, decision_map, ai_result = [], {}, {}
    if PREDICTION_ENABLED:
        held_all = [p["market"] for p in portfolio["positions"]]
        crypto_cands = scan_crypto(exclude=held_all, top_n=3)
        stock_cands = scan_stocks(exclude=held_all, top_n=2)
        all_cands = crypto_cands + stock_cands

        news_by_market = {}
        for c in all_cands:
            c["expected_days"] = estimate_holding_period(c["raw_closes"])
            c["strategy_type"] = classify_strategy(c["expected_days"])
            news_by_market[c["market"]] = get_news_sentiment(c["market"].replace("KRW-", ""))

        # 실계좌(토스, 조회전용) 보유종목 — 계좌번호 등 식별정보는 절대 넘기지 않는다.
        real_positions_for_ai = [
            {
                "symbol": p["symbol"], "name": p.get("name", p["symbol"]),
                "quantity": p.get("quantity"), "current_price": p.get("current_price"),
                "return_pct": p.get("return_pct", 0),
            }
            for p in real_positions
        ]

        ai_result = ask_claude_decision(portfolio["positions"], all_cands, news_by_market, real_positions_for_ai)
        report.append("🤖 AI 시장 요약")
        report.append(ai_result.get("market_summary", "요약 없음"))
        report.append("")

        decisions = ai_result.get("decisions", [])
        decision_map = {d["market"]: d for d in decisions}
    else:
        decisions = []
        report.append("🔬 예측 경로 비활성 (v3.2) — 매수/매도 방향 판단은 §2.1 게이트 "
                      "미통과로 중단된 연구입니다. 아래는 규칙 기반 점검 결과만입니다.")
        report.append("")

    # [기각된 연구 결과, 활성 기능 제외 — v3.2] 실계좌 매도/비중조정 제안.
    # PREDICTION_ENABLED=False면 decisions가 비어 있어 이 루프는 한 바퀴도 돌지
    # 않는다 — 즉 실계좌 대상 AI 제안도 더 이상 생성되지 않는다. 뉴스 방향 판단이
    # baseline 미달로 기각된 이상 실계좌 제안의 근거도 같이 사라졌기 때문이다.
    real_by_symbol = {p["symbol"]: p for p in real_positions}
    for d in decisions:
        market = d.get("market", "")
        if not market.startswith("REAL:"):
            continue
        symbol = market[len("REAL:"):]
        rp = real_by_symbol.get(symbol)
        if not rp:
            continue
        action = d.get("action")
        if action not in ("매도", "비중조정"):
            continue
        action_type = "sell" if action == "매도" else "rebalance"
        action_id = f"REAL_{symbol}_{today}"
        already_pending = any(a.get("id") == action_id for a in pending["actions"])
        if already_pending:
            continue
        dry_run = AI_SUGGESTION_DRY_RUN
        name = rp.get("name", symbol)
        reasoning = d.get("reasoning", "-")
        pending["actions"].append({
            "id": action_id,
            "action_type": action_type,
            "target_account": "real",
            "market": symbol,
            "name": name,
            "reasoning": f"[모의] {reasoning}" if dry_run else reasoning,
            "status": "waiting",
            "dry_run": dry_run,
        })
        gate_tag = " [모의] 게이트 미통과로 실행 비활성" if dry_run else ""
        report.append("")
        report.append(f"⏳ 실계좌 {action} 제안{gate_tag}: {name} ({rp.get('return_pct', 0):+.2f}%)")
        report.append(f"   AI 이유: {reasoning}")
        report.append(f"   👉 승인 /approve {action_id} / 거절 /reject {action_id}")

    # min_cash는 total_assets(현재 실제 총자산) 기준 — 예전엔 고정 TOTAL_BUDGET 기준이라
    # 자산이 불어나거나 줄어도 예비 현금이 그대로였다(버그). 실제 "총자산의 30%"가 되도록 수정.
    min_cash = total_assets * MIN_CASH_RESERVE_RATIO
    available = portfolio["cash"] - min_cash

    for c in all_cands:
        decision = decision_map.get(c["market"])
        if decision and decision.get("action") in ("매수", "비중조정") and available > 0:
            weight_pct = decision.get("target_weight_pct") or 20
            amount = round(available * (weight_pct / 100))
            amount = min(amount, available)

            # 종목당 비중 하드 상한(POSITION_WEIGHT_HARD_CAP) — 승인이 되더라도 이 비중을 넘는
            # 금액은 집행하지 않고 상한선까지만 잘라서 매수한다.
            hard_cap_amount = round(total_assets * POSITION_WEIGHT_HARD_CAP)
            if amount > hard_cap_amount:
                report.append(
                    f"⚠️ {c['market']} 요청 비중이 하드 상한({POSITION_WEIGHT_HARD_CAP*100:.0f}%)을 초과해 "
                    f"{amount:,.0f}원 → {hard_cap_amount:,.0f}원으로 조정"
                )
                amount = hard_cap_amount

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

    # [v3.2 활성 기능] 규칙 기반 가드레일 점검 — 예측 비활성과 무관하게 항상 돈다.
    guardrail_violations = audit_guardrail_violations(check_risk_guardrails(portfolio, total_assets))
    report.append("")
    if guardrail_violations:
        report.append(f"🛡️ 규칙 위반 {len(guardrail_violations)}건")
        for v in guardrail_violations:
            report.append(f"   · [{v['rule']}] {v['fact']}")
    else:
        report.append("🛡️ 규칙 위반 없음")

    report.append("")
    report.append(f"💰 현금: {portfolio['cash']:,.0f}원 / 보유 {len(portfolio['positions'])}개")
    waiting_count = len([a for a in pending["actions"] if a["status"] == "waiting"])
    if waiting_count:
        report.append(f"⏳ 승인 대기 {waiting_count}건 (v3.2: 예측 경로 중단으로 신규 생성 없음)")

    last_report = {
        "date": today,
        # 2026-08-10 방향성 세션 지시: 대시보드 기준시점 불일치 최소 조치.
        # "date"는 날짜만이라 가드레일 판정이 이 daily 실행(1일 1회) 기준인지
        # 구분이 안 된다 — check_updates.py의 refresh_last_report()는 이 필드를
        # 갱신하지 않는다(positions/cash/pending만 갱신) — guardrail_violations는
        # 여기 analyze.py의 daily 실행에서만 계산되므로, 이 값이 곧 그 판정
        # 시점이다. real_portfolio.json의 synced_at과 같은 ISO+UTC 패턴.
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "v3.2",
        # 예측 비활성 상태를 대시보드가 판별할 수 있게 명시적으로 싣는다.
        "prediction_enabled": PREDICTION_ENABLED,
        "guardrail_violations": guardrail_violations,
        "market_summary": ai_result.get("market_summary", ""),
        "positions": [
            {
                "market": p["market"], "asset_class": p.get("asset_class"),
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
