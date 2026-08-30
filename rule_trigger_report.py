"""규칙 발동 종목 심층분석 리포트 (2026-08-04, 방향성 세션 지시).

**승인 관문용 리포트다.** 자동실행이 "즉시 실행 + 사후 통보"에서 "발동 시 분석
리포트 + 사전 승인"으로 바뀌면서, 이 리포트가 사람이 판단을 내리기 전에 보는
자료가 된다. 그래서 정확성 기준이 다른 리포트보다 높다.

**구성**(요구사항 1):
  0. 발동 사실 — 왜 이 규칙이 발동했는지 수치로 (최상단, 요구사항 3)
  1. 기업분석 — 보유 현황 + 실적/밸류에이션
  2. 차트분석 — 최근 가격 흐름, 객관적 수치만
  3. 시장상태 — 관련 뉴스/사건 (Phase 2 설명카드 형식 그대로)

**절대 금지**(요구사항 2): BUY/SELL 라벨, confidence 점수, "사세요/파세요" 같은
행동촉구 문구. v3.2의 설명 vs 예측 분리 원칙을 그대로 적용한다. 스키마 수준에서
해당 필드를 두지 않고, 생성된 텍스트도 금지어 검사를 통과해야 한다.

**실적·밸류에이션에 대한 중요한 제약**: 이 저장소에는 PER/PBR/영업이익 같은
펀더멘털 데이터 소스가 **하나도 연결돼 있지 않다**(Phase3_펀더멘털신호_스펙.md
§8-1). 그래서 이 리포트는 해당 항목을 **비워두고 "데이터 소스 미연결"이라고
명시한다.** LLM에게 재무 수치를 쓰게 하면 그럴듯한 숫자를 지어낼 수 있고, 그
숫자가 실제 매도 승인의 근거가 된다 — 빈 칸이 틀린 숫자보다 낫다.

**두 세션 공유**(요구사항 4): `generate()`가 공개 API다. 자동실행 플로우
(autoexec.py)와 프록시 세션이 같은 함수를 호출하며, 네트워크 조회분을 미리
넘겨주면(candles/headlines) 조회 없이 순수 계산으로도 돌아간다.
"""
import argparse
import json
from datetime import datetime, timezone

from analyze_lib import FORBIDDEN_FIELDS_BASE, FORBIDDEN_PHRASES_BASE

# 리포트 어디에도 들어가면 안 되는 필드/문구. analyze_lib.FORBIDDEN_*_BASE(여러
# 모듈이 공유하는 기본 세트, 2026-08-10)에 이 리포트 고유 항목만 더한다 —
# 매수/매도 승인 근거로 쓰이는 리포트라 다른 모듈보다 엄격하게, 명사형("매수")과
# "보입니다"까지 막는다.
FORBIDDEN_FIELDS = FORBIDDEN_FIELDS_BASE
FORBIDDEN_PHRASES = FORBIDDEN_PHRASES_BASE + ("매수", "보입니다")


def _num(v, default=0.0):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ── 0. 발동 사실 (최상단) ───────────────────────────────────────────────────

def build_trigger_section(trigger):
    """왜 이 규칙이 발동했는지를 수치로. autoexec.py의 판정 결과를 그대로 옮긴다
    — 여기서 새로 계산하지 않는다(두 곳이 어긋나면 승인 근거가 흔들린다)."""
    d = trigger.get("detail", {}) or {}
    facts = []
    rule = trigger.get("rule", "")
    if rule == "집중도리밸런싱":
        facts = [
            f"현재 비중 {d.get('weight_pct')}% (기준 30% 초과)",
            f"기준 초과분 {_num(d.get('excess_krw')):,.0f}원",
            f"1회 매도 상한 {_num(d.get('cap_krw')):,.0f}원 (해당 종목 평가액의 30%)",
            f"적용 매도액 {_num(d.get('sell_krw')):,.0f}원",
        ]
    elif rule == "손실지속손절":
        facts = [
            f"평가손익 {d.get('return_pct')}% (기준선 -50% 이하)",
            f"기준선 이하 지속 {d.get('days')}일 (기준 60일 이상)",
            f"추적 시작일 {d.get('since')}",
        ]
    elif rule == "목표가부분익절":
        facts = [
            f"현재가 {_num(d.get('current_price')):,.0f} ≥ 목표가 {_num(d.get('target_price')):,.0f}",
            f"목표가 출처: 사용자 수기 입력 ({d.get('target_entered_at') or '입력일 미기재'})",
            f"부분매도 비율 {d.get('sell_ratio_pct')}% (보유 {d.get('held_qty')}주)",
        ]
    return {
        "rule": rule,
        "quantity": trigger.get("quantity"),
        "facts": facts,
        "raw_reason": trigger.get("reason", ""),
    }


# ── 1. 기업분석 ─────────────────────────────────────────────────────────────

def build_company_section(position, fundamentals=None):
    """보유 현황은 계좌 데이터에서 사실 그대로. 실적/밸류에이션은 소스가 없으면
    빈 칸으로 두고 그 사실을 명시한다 — 지어낸 숫자가 승인 근거가 되면 안 된다."""
    qty = _num(position.get("quantity"))
    avg = _num(position.get("avg_price"))
    cur = _num(position.get("current_price"))
    holding = {
        "보유 수량": f"{qty:,.0f}주",
        "평균 매입가": f"{avg:,.2f} {position.get('currency', '')}".strip(),
        "현재가": f"{cur:,.2f} {position.get('currency', '')}".strip(),
        "평가금액(원화)": f"{_num(position.get('eval_amount_krw')):,.0f}원",
        "평가손익률": f"{_num(position.get('return_pct')):+.2f}%",
        "매입원가 대비 손익": f"{(cur - avg) * qty:,.2f} {position.get('currency', '')}".strip(),
    }
    if fundamentals:
        return {"holding": holding, "fundamentals": fundamentals,
                "fundamentals_status": "제공됨", "fundamentals_source": fundamentals.get("_source")}
    return {
        "holding": holding,
        "fundamentals": None,
        "fundamentals_status": "데이터 소스 미연결",
        "fundamentals_note": (
            "실적·PER·PBR·부채비율 등 펀더멘털 지표는 이 저장소에 연결된 데이터 소스가 "
            "없어 제공하지 않습니다(Phase3_펀더멘털신호_스펙.md §8-1). 추정치를 만들어 "
            "넣지 않은 것은 의도된 것입니다 — 확인되지 않은 수치가 매도 승인의 근거가 "
            "되는 것을 막기 위함입니다. 필요하시면 증권사 앱/HTS에서 직접 확인하십시오."
        ),
    }


# ── 2. 차트분석 (객관적 수치만, 예측 문구 없음) ─────────────────────────────

def build_chart_section(closes, highs=None, lows=None, current_price=None):
    """최근 가격 흐름을 수치로 서술한다.

    지지/저항은 "최근 N일 중 저점/고점"이라는 **관측된 사실**로만 적는다 —
    "지지선이 받쳐줄 것"처럼 앞일을 말하는 표현은 쓰지 않는다(요구사항 1)."""
    if not closes or len(closes) < 5:
        return {"status": "데이터 부족", "note": f"종가 {len(closes or [])}건으로는 서술 불가"}

    cur = _num(current_price) or closes[-1]
    hi_src = highs or closes
    lo_src = lows or closes

    def window(n):
        n = min(n, len(closes))
        w_hi, w_lo = max(hi_src[-n:]), min(lo_src[-n:])
        span = w_hi - w_lo
        return {
            "기간": f"최근 {n}거래일",
            "고점": round(w_hi, 2),
            "저점": round(w_lo, 2),
            "현재가 위치": (f"{(cur - w_lo) / span * 100:.1f}% 지점"
                          if span > 0 else "고점=저점(변동 없음)"),
        }

    ma = {}
    for n in (20, 60):
        if len(closes) >= n:
            m = sum(closes[-n:]) / n
            ma[f"MA{n}"] = {"값": round(m, 2),
                            "현재가 대비": f"{(cur - m) / m * 100:+.2f}%"}

    rets = [(closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes)) if closes[i - 1]]
    vol = None
    if len(rets) >= 20:
        r = rets[-20:]
        mean = sum(r) / len(r)
        vol = round((sum((x - mean) ** 2 for x in r) / len(r)) ** 0.5 * 100, 2)

    return {
        "status": "산출됨",
        "current_price": round(cur, 2),
        "observed_range": [window(20), window(60), window(120)],
        "moving_average": ma,
        "daily_volatility_pct_20d": vol,
        "candle_count": len(closes),
        "note": ("위 수치는 관측된 과거 가격 사실입니다. 향후 가격 방향에 대한 "
                 "판단은 포함하지 않습니다."),
    }


# ── 3. 시장상태 (Phase 2 설명카드 형식 그대로) ──────────────────────────────

def build_market_section(event_card=None, headlines=None):
    """news_event_cards.py가 만드는 설명카드를 그대로 싣는다. 방향 예측 필드가
    없는 형식이며, 여기서 새로 방향을 붙이지 않는다."""
    if event_card:
        allowed = ("event_type", "summary", "headlines")
        card = {k: event_card[k] for k in allowed if k in event_card}
        return {"status": "산출됨", "card": card,
                "note": "사실 설명이며 매매 판단이 아닙니다. 방향 예측/확신도는 제공하지 않습니다."}
    if headlines:
        return {"status": "헤드라인만", "card": {"headlines": headlines[:5]},
                "note": "사건 분류 없이 헤드라인 원문만 표시합니다."}
    return {"status": "관련 뉴스 없음", "card": None}


# ── 공개 API ────────────────────────────────────────────────────────────────

def generate(symbol, position, trigger, *, closes=None, highs=None, lows=None,
            event_card=None, headlines=None, fundamentals=None, generated_at=None):
    """리포트 한 건 생성. **이것이 두 세션이 공유하는 진입점이다**(요구사항 4).

    네트워크를 타지 않는다 — 시세/뉴스는 호출자가 조회해 넘긴다. 자동실행
    플로우와 프록시 세션이 각자 다른 방식으로 데이터를 얻더라도 리포트 형식과
    금지어 규율은 이 함수 하나로 통일된다."""
    report = {
        # 2026-08-29 A2 Step 1 정규화(A2_Intelligence_Layer_Design.md §1-3):
        # 스키마 버전을 나머지 4개 생성기와 같은 "_v3.2" 체계로 통일하고,
        # generated_at을 KST naive 문자열에서 나머지 4개와 같은 UTC ISO 8601로
        # 바꿨다. 하위 호환 확인(§1-3에서 재확인한 사실): autoexec.py는 이 값을
        # 파싱하지 않고, index.html의 fmtBasis()는 naive/ISO 두 형식을 이미 다
        # 처리한다 — 형식 변경이 기존 소비처를 깨뜨리지 않는다.
        "schema": "rule_trigger_report_v3.2",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "name": position.get("name", symbol),
        "trigger": build_trigger_section(trigger),
        "company": build_company_section(position, fundamentals),
        "chart": build_chart_section(closes, highs, lows, position.get("current_price")),
        "market": build_market_section(event_card, headlines),
        "disclaimer": ("이 리포트는 규칙 발동 사실과 관련 자료를 정리한 것입니다. "
                       "매매 판단은 포함하지 않으며, 실행 여부는 사용자가 결정합니다."),
    }
    violations = audit(report)
    if violations:
        report["_audit_violations"] = violations
    return report


def audit(obj, path="report"):
    """금지 필드/문구가 섞였는지 재귀 검사. 생성기 자신을 감시한다 — 나중에
    섹션이 추가될 때 예측성 내용이 조용히 들어오는 걸 막는다."""
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


def render_summary(report):
    """승인요청 메시지에 인라인으로 넣는 한 줄 요약 (요구사항 3: "심층분석 리포트
    링크/요약"). 전체 리포트는 render_text()/`/autoexec_report <id>`로 별도 조회한다
    — 이건 그 축약판이라 같은 금지어 규율을 물려받는다(값을 report에서만 뽑아 쓰고
    새로 문구를 만들지 않는다)."""
    parts = []
    ch = report.get("chart", {})
    if ch.get("status") == "산출됨":
        parts.append(f"현재가 {ch['current_price']:,}")
        ma20 = ch.get("moving_average", {}).get("MA20")
        if ma20:
            parts.append(f"MA20 대비 {ma20['현재가 대비']}")
    m = report.get("market", {})
    card = m.get("card")
    if card and card.get("event_type"):
        parts.append(f"[{card['event_type']}] {card.get('summary', '')}")
    elif card and card.get("headlines"):
        parts.append(card["headlines"][0])
    return " · ".join(parts) if parts else "차트/뉴스 데이터 부족 - 전체 리포트 참고"


def render_text(report):
    """텔레그램/콘솔용 렌더. 승인 요청 문구를 포함하되, 어느 쪽을 택하라는
    권유는 넣지 않는다."""
    L = []
    t = report["trigger"]
    L.append(f"📑 규칙 발동 분석 리포트 — {report['name']} ({report['symbol']})")
    L.append(f"생성 {report['generated_at']}")
    L.append("")
    L.append(f"■ 발동 규칙: {t['rule']} / 대상 수량 {t.get('quantity')}주")
    for f in t["facts"]:
        L.append(f"   · {f}")
    L.append("")

    c = report["company"]
    L.append("■ 기업분석 — 보유 현황")
    for k, v in c["holding"].items():
        L.append(f"   · {k}: {v}")
    if c.get("fundamentals"):
        L.append("   실적·밸류에이션:")
        for k, v in c["fundamentals"].items():
            if not k.startswith("_"):
                L.append(f"   · {k}: {v}")
    else:
        L.append(f"   실적·밸류에이션: {c['fundamentals_status']}")
        L.append(f"   {c['fundamentals_note']}")
    L.append("")

    ch = report["chart"]
    L.append("■ 차트분석")
    if ch["status"] != "산출됨":
        L.append(f"   {ch['status']} — {ch.get('note', '')}")
    else:
        L.append(f"   현재가 {ch['current_price']:,}")
        for w in ch["observed_range"]:
            L.append(f"   · {w['기간']}: 저점 {w['저점']:,} ~ 고점 {w['고점']:,} "
                     f"(현재 {w['현재가 위치']})")
        for k, v in ch["moving_average"].items():
            L.append(f"   · {k} {v['값']:,} (현재가 {v['현재가 대비']})")
        if ch.get("daily_volatility_pct_20d"):
            L.append(f"   · 20일 일간 변동성 {ch['daily_volatility_pct_20d']}%")
        L.append(f"   {ch['note']}")
    L.append("")

    m = report["market"]
    L.append("■ 시장상태")
    if not m.get("card"):
        L.append(f"   {m['status']}")
    else:
        card = m["card"]
        if card.get("event_type"):
            L.append(f"   [{card['event_type']}] {card.get('summary', '')}")
        for h in (card.get("headlines") or [])[:4]:
            L.append(f"   · {h}")
        L.append(f"   {m['note']}")
    L.append("")
    L.append(report["disclaimer"])
    return "\n".join(L)


def run_self_test():
    print("=== rule_trigger_report.py 자체 검증 (네트워크 미사용) ===\n")

    position = {"symbol": "042660", "name": "한화오션", "quantity": "12",
                "avg_price": "68000", "current_price": "74500", "currency": "KRW",
                "eval_amount_krw": 894000.0, "return_pct": "9.56"}
    trigger = {"rule": "집중도리밸런싱", "quantity": 4,
               "reason": "비중 32.10%가 기준 30% 초과",
               "detail": {"weight_pct": 32.10, "excess_krw": 58000,
                          "cap_krw": 268200, "sell_krw": 58000}}
    closes = [60000 + (i * 137 % 9000) for i in range(140)]
    card = {"event_type": "공시", "summary": "미국 계열사 지분 추가 취득을 공시했습니다.",
            "headlines": ["한화오션, 미국 계열사 주식 1천645억원에 추가취득"],
            "direction": "호재", "confidence": 80}   # 오염 필드 - 걸러져야 함

    r = generate("042660", position, trigger, closes=closes, event_card=card)

    # 1) 발동 사실이 최상단에 수치로 들어가는지
    print(f"[1] 발동 사실 {len(r['trigger']['facts'])}줄: {r['trigger']['facts'][0]}")
    assert r["trigger"]["facts"] and "32.1" in r["trigger"]["facts"][0]

    # 2) 오염 필드가 시장상태 카드에서 제거되는지
    print(f"[2] 시장상태 카드 필드: {sorted(r['market']['card'])}")
    assert "direction" not in r["market"]["card"] and "confidence" not in r["market"]["card"]

    # 3) 금지 필드/문구가 리포트 전체에 없는지
    v = audit(r)
    print(f"[3] 감사 위반: {v or '없음'}")
    assert not v, f"금지 내용 발견: {v}"
    assert "_audit_violations" not in r

    # 4) 펀더멘털은 소스가 없으면 비워두고 명시하는지 (지어내지 않음)
    print(f"[4] 실적/밸류에이션: {r['company']['fundamentals_status']}")
    assert r["company"]["fundamentals"] is None
    assert "지어내" not in r["company"]["fundamentals_note"]  # 문구 자체는 완곡히
    assert "확인되지 않은 수치" in r["company"]["fundamentals_note"]

    # 5) 차트는 관측 사실만 (예측 표현 없음)
    ch = r["chart"]
    print(f"[5] 차트 구간 {len(ch['observed_range'])}개, MA {sorted(ch['moving_average'])}, "
          f"변동성 {ch['daily_volatility_pct_20d']}%")
    assert ch["status"] == "산출됨" and len(ch["observed_range"]) == 3
    assert "MA20" in ch["moving_average"] and "MA60" in ch["moving_average"]

    # 6) 렌더된 텍스트에도 금지 문구가 없는지
    text = render_text(r)
    hits = [p for p in FORBIDDEN_PHRASES if p in text]
    print(f"[6] 렌더 텍스트 금지문구: {hits or '없음'} ({len(text)}자)")
    assert not hits, f"렌더 텍스트에 금지 문구: {hits}"

    # 6-b) 승인요청 인라인 요약도 같은 금지어 규율을 따르는지, 내용이 비지 않는지
    summary = render_summary(r)
    hits_s = [p for p in FORBIDDEN_PHRASES if p in summary]
    print(f"[6b] 요약: {summary!r}")
    assert summary and summary != "차트/뉴스 데이터 부족 - 전체 리포트 참고", "데이터가 있는데 요약이 비어 있음"
    assert not hits_s, f"요약에 금지 문구: {hits_s}"

    # 7) 데이터가 없을 때 조용히 빈 값을 내지 않는지
    r2 = generate("X", {"name": "무데이터"}, {"rule": "손실지속손절", "quantity": 1,
                  "detail": {"return_pct": -55.0, "days": 62, "since": "2026-06-01"}})
    print(f"[7] 시세 없음 -> 차트 {r2['chart']['status']} / 뉴스 없음 -> 시장 {r2['market']['status']}")
    assert r2["chart"]["status"] == "데이터 부족"
    assert r2["market"]["status"] == "관련 뉴스 없음"
    assert not audit(r2)
    summary_nodata = render_summary(r2)
    print(f"     데이터 없을 때 요약: {summary_nodata!r}")
    assert summary_nodata == "차트/뉴스 데이터 부족 - 전체 리포트 참고"

    # 8) 세 규칙 모두 발동 사실을 채우는지
    for rule, detail in [
        ("집중도리밸런싱", {"weight_pct": 31.0, "excess_krw": 1, "cap_krw": 2, "sell_krw": 1}),
        ("손실지속손절", {"return_pct": -55.0, "days": 62, "since": "2026-06-01"}),
        ("목표가부분익절", {"current_price": 100, "target_price": 90,
                            "sell_ratio_pct": 25, "held_qty": 40}),
    ]:
        s = build_trigger_section({"rule": rule, "quantity": 1, "detail": detail})
        print(f"[8] {rule}: {len(s['facts'])}줄")
        assert s["facts"], f"{rule} 발동 사실이 비어 있음"

    print("\n모든 자체 검증 통과.")


def main():
    p = argparse.ArgumentParser(description="규칙 발동 종목 심층분석 리포트 생성기")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        run_self_test()


if __name__ == "__main__":
    main()
