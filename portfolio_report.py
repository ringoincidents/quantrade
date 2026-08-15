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
import math
from datetime import datetime, timezone

from analyze_lib import (
    FORBIDDEN_FIELDS_BASE, FORBIDDEN_PHRASES_BASE, HARD_STOP_LOSS,
    POSITION_WEIGHT_HARD_CAP, TRADING_COSTS, get_krx_candles, get_us_candles,
    load_json, save_json, send_telegram,
)

REAL_PORTFOLIO_FILE = "real_portfolio.json"
INCOME_SCHEDULE_FILE = "income_schedule.json"
ASSET_CLASS_MAPPING_FILE = "asset_class_mapping.json"
TARGET_ALLOCATION_FILE = "target_allocation.json"
REPORT_FILE = "portfolio_report.json"
STATE_FILE = "portfolio_report_state.json"

# "이번 달" + 다음 N-1개월. 지시서 표현("이번 달 및 다음 1~2개월") 그대로 3개월.
GAP_FILL_MONTHS_AHEAD = 3

# 사전 확정 대기 중인 초안 임계값.
# concentration_pct / loss_pct는 지시받은 값이고, loss_sustained_days는
# "N일"이 미정이라 초안으로 둔 값이다. 셋 다 방향성 세션 확정 대상.
THRESHOLDS = {
    "provisional": True,
    "concentration_pct": 30.0,      # 단일 종목 비중이 이 이상이면 플래그
    "loss_pct": -50.0,              # 평가손익률이 이 이하이고
    "loss_sustained_days": 60,      # 그 상태가 이 일수 이상 지속되면 플래그 (초안)
}

# 리포트 어디에도 들어가면 안 되는 필드/문구. self-test와 대시보드가 함께 검사한다.
# analyze_lib.FORBIDDEN_*_BASE(여러 모듈 공유, 2026-08-10 "자유텍스트 금지문구
# 전수 점검" 지시)를 쓴다. 이 파일은 지금까지 FORBIDDEN_FIELDS(필드명)만 있었고
# summary/note/fact 같은 자유텍스트 "문구" 자체는 self-test에서 몇 개 단어만
# 수동으로 확인했을 뿐 run() 저장 시점에 실제로 강제된 적이 없었다 — 이번 점검으로
# 발견해 추가한다("정리하세요"는 이 파일의 기존 self-test가 이미 걱정하던 문구라
# 그대로 가져옴).
#
# "rank"/"ranking"은 base에서 뺀다 — 이 파일의 roadmap.phases[].rank는
# 종합판단 순위가 아니라 "계급"(일병/상병/병장, 배분 로드맵의 기존 필드,
# 2026-08-01부터 있었음)이다. 실제로 실계좌 데이터로 감사를 돌려보니 이
# 충돌이 그대로 걸렸다 — 리네이밍은 index.html 렌더러까지 같이 고쳐야 하는
# 더 큰 변경이라, 여기서는 이 필드가 가리키는 게 순위가 아니라는 사실이
# 분명하므로 예외로 뺀다(다른 모듈에는 이 예외를 적용하지 않는다).
FORBIDDEN_FIELDS = tuple(f for f in FORBIDDEN_FIELDS_BASE if f not in ("rank", "ranking"))
FORBIDDEN_PHRASES = FORBIDDEN_PHRASES_BASE + ("정리하세요",)

# Risk Engine (2026-08-09, 방향성 세션 지시) — v3.0 원칙2("AI는 뭘 살지 관여,
# 얼마나 살지는 Risk Engine이 결정")의 첫 구현. 여기도 예측/신호가 아니라
# 산술이다 — "권장 금액"은 계산값이지 "사세요"라는 문장이 아니고, 최종
# 매수 여부·금액은 항상 사람이 정한다. provisional=True로 두는 이유는
# THRESHOLDS와 동일 — 사후에 결과 보고 기준을 맞추는 걸 막기 위해서다.
RISK_ENGINE = {
    "provisional": True,
    "portfolio_mdd_limit_pct": -20.0,   # backtest.py SUCCESS_CRITERIA의 mdd_limit_pct와 동일 값 재사용
    "per_trade_risk_budget_pct": 2.0,   # 1회 신규매수가 감수할 손실 예산(총자산 대비). "위험자산 20% 한도를
                                          # 대략 10개 포지션에 분산한다"는 가정의 역산값(20%/10) — 문서화된
                                          # 가정이며 방향성 세션이 확정 전까지 초안.
    "single_trade_cap_pct": 30.0,       # 지시받은 값 그대로(autoexec.py의 집중도 리밸런싱 매도 상한 30%와
                                          # 숫자는 같지만 별개 규칙 — 그쪽은 매도 상한, 이쪽은 매수 상한)
    "position_hard_cap_pct": POSITION_WEIGHT_HARD_CAP * 100,  # 기존 analyze_lib 상한(20%) 재사용
    "reference_vol_pct": 2.0,           # "보통 변동성"을 일간수익률 표준편차 2%로 정의(문서화된 가정) —
                                          # 실제 변동성이 이보다 크면 포지션을 줄이고 작으면 늘리는 기준선
    "correlation_flag_threshold": 0.7,  # 지시받은 값
    "correlation_lookback_days": 90,    # 지시받은 값
    "volatility_lookback_days": 20,     # 지시서 "20일 수익률 표준편차"
}


# ── Risk Engine: 순수 계산 (네트워크 없이 self-test 가능) ─────────────────────

def calc_daily_returns(closes):
    """종가 리스트 -> 일간 수익률(%) 리스트. 첫 봉은 기준이 없어 제외된다."""
    return [(closes[i] - closes[i - 1]) / closes[i - 1] * 100
            for i in range(1, len(closes)) if closes[i - 1]]


def calc_volatility_pct(closes, window=None):
    """최근 window일 일간수익률의 표준편차(%) — ATR 대신 이 방식을 썼다(지시서
    "20일 수익률 표준편차 또는 ATR" 중 표준편차 쪽을 선택, TRADING_COSTS 등
    이미 % 기반 계산이 많은 이 파일의 기존 관례와 맞춰서)."""
    window = window or RISK_ENGINE["volatility_lookback_days"]
    rets = calc_daily_returns(closes)[-window:]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var)


def calc_position_sizing(total_assets_krw, vol_pct):
    """"이 종목을 지금 매수한다면 권장 금액 범위" — 계산값만, 매수 여부/문구 없음.

    범위는 기존 HARD_STOP_LOSS(단타-5%/스윙-10%/장기-25%)별로 손절폭이
    다르면 같은 손실예산(per_trade_risk_budget_pct)으로 살 수 있는 금액이
    달라진다는 사실에서 나온다 — 손절이 타이트할수록(단타) 같은 예산으로
    더 큰 금액을, 손절이 넓을수록(장기) 더 작은 금액을 감당할 수 있다.
    변동성이 기준치(reference_vol_pct)보다 크면 그만큼 줄이고 작으면 늘린다.
    모든 경우에 기존 상한(single_trade_cap_pct/position_hard_cap_pct 중
    낮은 쪽)을 절대 넘지 않는다."""
    if not total_assets_krw or vol_pct is None:
        return None
    ceiling_krw = total_assets_krw * min(
        RISK_ENGINE["single_trade_cap_pct"], RISK_ENGINE["position_hard_cap_pct"]
    ) / 100
    budget_krw = total_assets_krw * RISK_ENGINE["per_trade_risk_budget_pct"] / 100
    vol_factor = RISK_ENGINE["reference_vol_pct"] / max(vol_pct, 0.1)

    by_strategy = {}
    for strategy, stop_pct in HARD_STOP_LOSS.items():
        raw_krw = budget_krw / (abs(stop_pct) / 100) * vol_factor
        by_strategy[strategy] = round(min(raw_krw, ceiling_krw))

    values = list(by_strategy.values())
    return {
        "recommended_range_krw": {"min": min(values), "max": max(values)},
        "by_strategy_krw": by_strategy,
        "ceiling_krw": round(ceiling_krw),
        "inputs": {
            "volatility_pct": round(vol_pct, 3),
            "reference_vol_pct": RISK_ENGINE["reference_vol_pct"],
            "per_trade_risk_budget_pct": RISK_ENGINE["per_trade_risk_budget_pct"],
        },
    }


def calc_mdd_budget_usage(rows, total_assets_krw):
    """전체 손실한도(-20% MDD) 대비 현재 소진율(%). 계좌 전체의 평가금액
    가중평균 수익률을 한도로 나눈 값 — 예: 포트폴리오가 -6%이고 한도가
    -20%면 소진율 30%. real_portfolio.json은 스냅샷이라 실제 고점 대비
    낙폭(진짜 MDD)은 알 수 없다 — 그래서 "현재 미실현손익 기준 소진율"이라고
    명시하고, 진짜 MDD가 아님을 필드명에도 남긴다."""
    if not total_assets_krw:
        return None
    weighted_return_pct = sum(
        (r["eval_amount_krw"] / total_assets_krw) * r["return_pct"] for r in rows
    )
    limit = RISK_ENGINE["portfolio_mdd_limit_pct"]
    usage_pct = (weighted_return_pct / limit) * 100 if limit else None
    return {
        "portfolio_unrealized_return_pct": round(weighted_return_pct, 2),
        "mdd_limit_pct": limit,
        "budget_usage_pct": round(usage_pct, 1) if usage_pct is not None else None,
        "note": ("실제 고점 대비 낙폭(진짜 MDD)이 아니라 현재 미실현손익 기준 "
                 "소진율 — real_portfolio.json은 스냅샷이라 과거 고점을 모른다."),
    }


def calc_correlation(returns_a, returns_b):
    """피어슨 상관계수. scipy/numpy 없이 직접 계산(CLAUDE.md 의존성 최소화 원칙)."""
    n = min(len(returns_a), len(returns_b))
    if n < 10:
        return None
    a, b = returns_a[-n:], returns_b[-n:]
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((x - mean_b) ** 2 for x in b)
    denom = math.sqrt(var_a * var_b)
    if denom == 0:
        return None
    return cov / denom


def calc_correlation_matrix(returns_by_symbol):
    """보유 종목 간 상관계수 행렬 + 임계치(0.7) 이상 쌍 목록. "비슷하게
    움직이는 종목" 사실만 표시 — "이 중 하나 파세요" 같은 문구는 없다."""
    symbols = list(returns_by_symbol.keys())
    matrix = {s: {} for s in symbols}
    flagged = []
    for i, s1 in enumerate(symbols):
        for s2 in symbols[i:]:
            if s1 == s2:
                matrix[s1][s2] = 1.0
                continue
            corr = calc_correlation(returns_by_symbol[s1], returns_by_symbol[s2])
            matrix[s1][s2] = round(corr, 3) if corr is not None else None
            matrix[s2][s1] = matrix[s1][s2]
            if corr is not None and abs(corr) >= RISK_ENGINE["correlation_flag_threshold"]:
                flagged.append({"symbol_a": s1, "symbol_b": s2, "correlation": round(corr, 3)})
    flagged.sort(key=lambda f: -abs(f["correlation"]))
    return {
        "lookback_days": RISK_ENGINE["correlation_lookback_days"],
        "matrix": matrix,
        "flagged_pairs": flagged,
        "flag_threshold": RISK_ENGINE["correlation_flag_threshold"],
    }


def _round_trip_cost_pct(asset_class):
    costs = TRADING_COSTS.get(asset_class, TRADING_COSTS["stock"])
    buy_pct = costs["fee_pct"] + costs["slippage_pct"]
    sell_pct = costs["fee_pct"] + costs["slippage_pct"] + costs.get("sell_tax_pct", 0)
    return buy_pct + sell_pct


def _asset_class_for(market_country, currency):
    if market_country == "KR" or currency == "KRW":
        return "krx"
    return "stock"


def calc_cost_adjusted(rows):
    """"총손익"/"평가손익" 옆에 병기할 "비용 반영 후" 수치. 국내주식은
    매매수수료+증권거래세, 해외주식은 매매수수료(+환전수수료는 별도 항목이
    없어 TRADING_COSTS["stock"]의 slippage_pct에 이미 포함된 가정치로 흡수 —
    analyze_lib.py 원 주석 "SEC 수수료 등은 미미해 생략" 참고, 환전수수료
    전용 항목은 이번에 새로 추가하지 않고 기존 가정을 그대로 씀).

    지금 시점에 판다면 나갈 매도비용만 차감한다 — 매수비용은 이미 과거에
    치른 것으로 보고 return_pct(평가손익률)에 다시 반영하지 않는다."""
    out = []
    for r in rows:
        asset_class = _asset_class_for(r.get("market_country"), r.get("currency"))
        costs = TRADING_COSTS.get(asset_class, TRADING_COSTS["stock"])
        sell_cost_pct = costs["fee_pct"] + costs["slippage_pct"] + costs.get("sell_tax_pct", 0)
        out.append({
            "symbol": r["symbol"],
            "name": r["name"],
            "return_pct": r["return_pct"],
            "sell_cost_pct": round(sell_cost_pct, 3),
            "cost_adjusted_return_pct": round(r["return_pct"] - sell_cost_pct, 3),
        })
    return out


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


def _now_iso():
    """생성 시각 표시용 — 날짜만인 _today()와 분리한다. _today()는 손실지속일수
    등 날짜 산술(strptime "%Y-%m-%d")에 쓰이므로 형식을 바꿀 수 없다(2026-08-10
    방향성 세션 지시: 대시보드 기준시점 불일치 최소 조치 — 이 리포트는 주 1회만
    갱신되므로(portfolio_report.yml), 날짜만으론 "이번 주 어느 시점"인지 알 수
    없다. real_portfolio.json의 synced_at과 같은 ISO+UTC 패턴으로 시:분까지 남긴다."""
    return datetime.now(timezone.utc).isoformat()


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


# ── (3b) 자산군 배분 갭 계산 (2026-08-10, 방향성 세션 지시) ─────────────────
#
# asset_class_mapping.json(종목→자산군)이 만들어진 뒤로 실제로 이 파일을 읽는
# 코드가 없었다(그 파일 자체의 consumed_by 필드가 그렇게 명시하고 있었음) —
# 여기서 처음 연결한다.
#
# **목표 비중 규칙은 초안이다(§1, 방향성 세션 확정 전).** target_allocation.json
# 에 전부 데이터로 뒀다 — 숫자를 코드에 하드코딩하면 나중에 규칙이 바뀔 때마다
# 이 파일을 고쳐야 하는데, 그러면 "숫자만 바꾸면 재정의 가능"이라는 지시서
# 요구를 어기게 된다.

def load_symbol_class_map(mapping):
    """종목코드 -> 자산군 딕셔너리. mapping은 asset_class_mapping.json 내용."""
    return {m["symbol"]: m["asset_class"] for m in mapping.get("mappings", [])}


def compute_class_actual_pct(rows, cash_pct, symbol_to_class):
    """종목별 weight_pct(portfolio_report.compute_positions 결과)를 자산군별로
    합산한다. 매핑 안 된 보유종목은 조용히 버리지 않고 별도로 모아 반환한다 —
    그래야 "안전+위험 비중 합이 100%보다 작아 보이는" 이유를 리포트에서 바로
    알 수 있다. 현금(cash_pct)은 "현금성" 자산군의 실제 비중에 그대로 더한다 —
    계좌 현금 잔고 자체가 현금성 자산이라는 사실이지, 별도 매핑이 필요한 보유
    종목이 아니기 때문이다."""
    by_class = {}
    unmapped = []
    for r in rows:
        cls = symbol_to_class.get(r["symbol"])
        if cls is None:
            unmapped.append({"symbol": r["symbol"], "name": r["name"], "weight_pct": r["weight_pct"]})
            continue
        by_class[cls] = round(by_class.get(cls, 0.0) + r["weight_pct"], 2)
    by_class["cash"] = round(by_class.get("cash", 0.0) + cash_pct, 2)
    return by_class, unmapped


def compute_class_target_pct(target_allocation, populated_classes, rank_name):
    """계급명 -> 자산군별 목표 비중(%) 딕셔너리. target_allocation.json의
    risk_distribution_rule에 적은 대로: 그룹(안전/위험) 총비중을, 그 그룹
    안에서 실제로 비중이 있는(populated) 자산군에만 균등분배한다 — 매핑 안 된
    자산군은 목표도 0%. 그룹 전체가 미매핑이면(고아 방지) 그룹 전체를
    균등분배한다."""
    safe_classes = target_allocation.get("safe_classes", [])
    risk_classes = target_allocation.get("risk_classes", [])
    safe_total = (target_allocation.get("safe_total_pct_by_rank") or {}).get(rank_name)
    if safe_total is None:
        return None
    risk_total = 100.0 - safe_total

    def split(classes, total_pct):
        mapped = [c for c in classes if c in populated_classes]
        active = mapped if mapped else list(classes)
        share = round(total_pct / len(active), 3) if active else 0.0
        return {c: (share if c in active else 0.0) for c in classes}

    target = {}
    target.update(split(safe_classes, safe_total))
    target.update(split(risk_classes, risk_total))
    return target


def current_rank_for_month(income, ym):
    """ym("YYYY-MM")이 속하는 계급을 income_schedule.json의 ranks[].start로
    찾는다. ranks는 이미 오름차순이라고 가정하지 않고 여기서 정렬한다."""
    ranks = [r for r in income.get("ranks", []) if r.get("start")]
    if not ranks:
        return None
    ranks = sorted(ranks, key=lambda r: r["start"])
    current = None
    for r in ranks:
        if r["start"] <= ym:
            current = r
        else:
            break
    return current


def compute_asset_class_gap(rows, cash_pct, mapping, target_allocation, rank_name):
    """자산군별 [목표비중/실제비중/갭(%p)]. 판단 문구 없이 숫자만 담는다."""
    symbol_to_class = load_symbol_class_map(mapping)
    actual_by_class, unmapped = compute_class_actual_pct(rows, cash_pct, symbol_to_class)
    populated = {c for c, pct in actual_by_class.items() if pct > 0}
    target_by_class = compute_class_target_pct(target_allocation, populated, rank_name)
    if target_by_class is None:
        return None

    safe_classes = target_allocation.get("safe_classes", [])
    risk_classes = target_allocation.get("risk_classes", [])
    labels = {**target_allocation.get("safe_class_labels", {}), **target_allocation.get("risk_class_labels", {})}
    is_safe = set(safe_classes)

    rows_out = []
    for c in list(safe_classes) + list(risk_classes):
        target_pct = target_by_class.get(c, 0.0)
        actual_pct = actual_by_class.get(c, 0.0)
        rows_out.append({
            "asset_class": c,
            "label": labels.get(c, c),
            "group": "안전자산" if c in is_safe else "위험자산",
            "target_pct": target_pct,
            "actual_pct": round(actual_pct, 2),
            "gap_pct": round(target_pct - actual_pct, 2),
            "currently_mapped": c in populated,
        })

    return {
        "provisional": bool(target_allocation.get("provisional", True)),
        "rank": rank_name,
        "rows": rows_out,
        "unmapped_holdings": unmapped,
        "unmapped_holdings_weight_pct": round(sum(u["weight_pct"] for u in unmapped), 2),
        "note": ("자산군별 목표/실제 비중과 그 차이(%p)만 나열합니다. 매핑 안 된 "
                 "자산군의 갭이 0%p인 것은 정상입니다(목표도 0%로 계산). 매핑 안 "
                 "된 보유종목은 unmapped_holdings에 따로 모았습니다 — 어떤 자산군에도 "
                 "포함되지 않았다는 사실이며, 판단이 필요하다는 뜻은 아닙니다."),
    }


def compute_monthly_gap_fill(gap, income, start_ym, months=GAP_FILL_MONTHS_AHEAD):
    """이번 달(+ 다음 N-1개월) 유입 예정액을, 갭이 양수(미달)인 자산군에 갭
    크기 비례로 배분한다 — "갭이 큰 자산군부터 채운다"(지시서 §3)를 승자독식이
    아니라 갭 비례 배분으로 구현했다(전액을 갭이 가장 큰 자산군 하나에만 넣는
    건 실제 재조정 방식으로는 지나치게 쏠린다고 판단).

    **한계**: 매달 같은 갭(현재 스냅샷 기준)을 기준으로 배분액을 계산한다 —
    이번 달 투자가 실제로 반영된 뒤의 갭을 재계산하지 않는다. 그러려면 미래
    매매를 시뮬레이션해야 하는데, 이 리포트는 계산과 사실 서술만 한다는 원칙과
    맞지 않아 하지 않았다. 자산군 단위 산술이며 개별 종목 추천이 아니다."""
    positive = [r for r in gap["rows"] if r["gap_pct"] > 0]
    total_gap = sum(r["gap_pct"] for r in positive)

    months_out = []
    y, m = (int(x) for x in start_ym.split("-"))
    for _ in range(months):
        ym = f"{y:04d}-{m:02d}"
        rank = current_rank_for_month(income, ym)
        if not rank:
            months_out.append({"month": ym, "rank": None, "monthly_investable_krw": None, "allocations": []})
        else:
            monthly_krw = rank["monthly_krw"]
            allocations = []
            if total_gap > 0:
                for r in positive:
                    share = r["gap_pct"] / total_gap
                    allocations.append({
                        "asset_class": r["asset_class"], "label": r["label"],
                        "gap_pct": r["gap_pct"], "amount_krw": round(monthly_krw * share),
                    })
            months_out.append({
                "month": ym, "rank": rank["rank"], "monthly_investable_krw": monthly_krw,
                "allocations": allocations,
            })
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return months_out


# ── 리포트 조립 ─────────────────────────────────────────────────────────────

def fetch_symbol_candles(rows, count=None):
    """보유 종목별 일봉(종가) 조회 — 변동성/상관계수 계산용. 국내는
    get_krx_candles(네이버, 실계좌 조회 API와 무관), 해외는 get_us_candles
    (Yahoo/stooq)를 그대로 재사용한다 — 이미 backtest.py/analyze.py가
    라이브 스캔·백테스트에 쓰고 있는 기존 가격 데이터 연결이라 CLAUDE.md의
    "게이트 미통과 상태에서 새 실시간 외부 커넥터 추가 금지" 원칙과는
    무관하다(신규 뉴스/판단류 커넥터가 아니라 이미 쓰이던 가격 소스).

    조회 실패한 종목은 조용히 건너뛴다(analyze.py의 기존 관례와 동일 —
    외부 API 장애로 전체 리포트가 죽으면 안 됨)."""
    count = count or max(RISK_ENGINE["correlation_lookback_days"], RISK_ENGINE["volatility_lookback_days"]) + 10
    out = {}
    for r in rows:
        symbol = r["symbol"]
        asset_class = _asset_class_for(r.get("market_country"), r.get("currency"))
        try:
            candles = get_us_candles(symbol, count) if asset_class == "stock" else get_krx_candles(symbol, count)
            out[symbol] = [c["close"] for c in candles]
        except Exception as e:
            print(f"⚠️ {symbol} 가격 이력 조회 실패(Risk Engine 변동성/상관계수 계산에서 제외): {e}")
    return out


def build_risk_engine(rows, total_assets_krw, symbol_closes):
    """v3.0 원칙2 Risk Engine 클러스터 — 전부 계산·표시 전용, 예측/신호 없음.
    symbol_closes가 비어 있으면(네트워크 없는 self-test 등) 계산 가능한
    부분(집중도/손실률/MDD소진율/비용반영후, real_portfolio.json만으로 되는
    것들)만 채우고 변동성 의존 항목(포지션 사이징/상관계수)은 빈 값으로
    남긴다 — "빈 칸이 틀린 숫자보다 낫다" 원칙."""
    symbol_closes = symbol_closes or {}

    position_sizing = []
    for r in rows:
        closes = symbol_closes.get(r["symbol"])
        vol_pct = calc_volatility_pct(closes) if closes else None
        sizing = calc_position_sizing(total_assets_krw, vol_pct) if vol_pct is not None else None
        position_sizing.append({
            "symbol": r["symbol"], "name": r["name"],
            "sizing": sizing,
            "note": None if sizing else "가격 이력 조회 실패로 변동성 계산 불가 — 사이징 계산 생략",
        })

    concentration = [
        {"symbol": r["symbol"], "name": r["name"], "weight_pct": r["weight_pct"],
         "threshold_pct": THRESHOLDS["concentration_pct"]}
        for r in rows
    ]

    returns_by_symbol = {
        sym: calc_daily_returns(closes)[-RISK_ENGINE["correlation_lookback_days"]:]
        for sym, closes in symbol_closes.items()
    }
    correlation = calc_correlation_matrix(returns_by_symbol) if len(returns_by_symbol) >= 2 else {
        "lookback_days": RISK_ENGINE["correlation_lookback_days"], "matrix": {}, "flagged_pairs": [],
        "flag_threshold": RISK_ENGINE["correlation_flag_threshold"],
        "note": "보유 종목이 2개 미만이거나 가격 이력 조회 실패 — 상관계수 계산 생략",
    }

    return {
        "provisional": RISK_ENGINE["provisional"],
        # 2026-08-10: 원래 "권장 금액"이라고 썼는데, 이 표현이 audit()의 금지 문구
        # "권장"에 실제로 걸렸다 — "이건 추천이 아니라 계산값"이라고 설명하는
        # 문장 자체가 금지어를 문자 그대로 담고 있던 자기지시적 사례
        # (market_indicators.py가 이전에 겪은 것과 같은 종류). "금액 범위"로 바꿔
        # 같은 의미를 유지하면서 금지어를 피한다.
        "note": ("전부 계산·표시 전용이다 — 예측/신호 없음. 아래 금액 범위는 계산값이지 "
                 "매수 지시가 아니고, 최종 매수 여부·금액은 항상 사람이 정한다."),
        "position_sizing": position_sizing,
        "mdd_budget": calc_mdd_budget_usage(rows, total_assets_krw),
        "concentration": concentration,
        "correlation": correlation,
        "cost_adjusted": calc_cost_adjusted(rows),
    }


def build_report(real, income, state, today=None, symbol_closes=None,
                  asset_class_mapping=None, target_allocation=None):
    today = today or _today()
    snapshot = compute_positions(real)
    streaks = update_loss_streaks(snapshot["positions"], state, today)
    matches = evaluate_rules(snapshot["positions"], streaks, today)
    risk_engine = build_risk_engine(snapshot["positions"], snapshot["total_assets_krw"], symbol_closes)

    # 2026-08-10: 자산군 배분 갭 계산. asset_class_mapping.json/target_allocation.json
    # 둘 다 있어야 계산할 수 있다 — 하나라도 없으면 계산하지 않는다("데이터 소스
    # 미연결"류 원칙과 동일, 없는 데이터를 지어내지 않는다).
    asset_class_gap = None
    if asset_class_mapping is not None and target_allocation is not None:
        current_rank = current_rank_for_month(income, today[:7]) if income else None
        rank_name = current_rank["rank"] if current_rank else None
        if rank_name:
            gap = compute_asset_class_gap(
                snapshot["positions"], snapshot["cash_pct"], asset_class_mapping,
                target_allocation, rank_name,
            )
            if gap:
                gap["monthly_gap_fill"] = compute_monthly_gap_fill(gap, income, today[:7])
                asset_class_gap = gap

    report = {
        "generated_at": _now_iso(),
        "schema": "portfolio_report_v3.2",
        "note": ("현황 계산 + 사전 정의 규칙 해당 여부만 담는다. 매매 판단/방향 예측/"
                 "확신도 필드는 스키마에 없다 - 누락이 아니라 설계."),
        "thresholds": dict(THRESHOLDS),
        "snapshot": snapshot,
        "rule_matches": matches,
        "risk_engine": risk_engine,
        "roadmap": compute_roadmap(income),
        "asset_class_gap": asset_class_gap,
    }
    return report, state


def format_telegram(report):
    s = report["snapshot"]
    # generated_at은 이제 ISO+UTC 풀 타임스탬프(대시보드용) — 텔레그램에는
    # 사람이 읽기 쉬운 "YYYY-MM-DD HH:MM UTC"로 줄여 보여준다.
    try:
        gen_dt = datetime.fromisoformat(report["generated_at"]).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        gen_dt = report.get("generated_at", "-")
    lines = [f"📋 포트폴리오 리포트 ({gen_dt})", ""]
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

    re_ = report.get("risk_engine") or {}
    lines.append("")
    tag = " [초안 기준]" if re_.get("provisional") else ""
    lines.append(f"⚖️ Risk Engine{tag} — 계산값만, 매매 지시 아님")
    mdd = re_.get("mdd_budget")
    if mdd and mdd.get("budget_usage_pct") is not None:
        lines.append(f"   · MDD 예산 소진율 {mdd['budget_usage_pct']:.1f}% "
                     f"(현재 {mdd['portfolio_unrealized_return_pct']:+.2f}% / 한도 {mdd['mdd_limit_pct']:.0f}%)")
    over = [c for c in re_.get("concentration", []) if c["weight_pct"] >= c["threshold_pct"]]
    if over:
        lines.append("   · 집중도 " + " / ".join(f"{c['name']} {c['weight_pct']:.1f}%" for c in over)
                     + f" (기준 {THRESHOLDS['concentration_pct']:.0f}%)")
    flagged = (re_.get("correlation") or {}).get("flagged_pairs", [])
    if flagged:
        lines.append(f"   · 상관계수 {re_['correlation']['flag_threshold']} 이상 {len(flagged)}쌍: "
                     + ", ".join(f"{f['symbol_a']}-{f['symbol_b']}({f['correlation']:+.2f})" for f in flagged[:3]))

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

    gap = report.get("asset_class_gap")
    lines.append("")
    if not gap:
        lines.append("📊 자산군 배분 갭: 계산 불가 (asset_class_mapping.json/target_allocation.json/계급 시작일 중 하나 없음)")
    else:
        tag = " [초안 기준]" if gap.get("provisional") else ""
        lines.append(f"📊 자산군 배분 갭 ({gap['rank']} 기준){tag} — 자산군 단위 산술이며 개별 종목을 지정하지 않습니다")
        widest = sorted(gap["rows"], key=lambda r: -r["gap_pct"])[:3]
        for r in widest:
            if r["gap_pct"] <= 0:
                continue
            lines.append(f"   · {r['label']}: 목표 {r['target_pct']:.1f}% / 실제 {r['actual_pct']:.1f}% "
                         f"/ 갭 {r['gap_pct']:+.1f}%p")
        if gap["unmapped_holdings_weight_pct"] > 0:
            lines.append(f"   ※ 미매핑 보유종목 비중 {gap['unmapped_holdings_weight_pct']:.1f}% "
                         f"(어떤 자산군에도 포함 안 됨)")
        fill = (gap.get("monthly_gap_fill") or [None])[0]
        if fill and fill.get("allocations"):
            lines.append(f"   · 이번 달({fill['month']}) 유입 {fill['monthly_investable_krw']:,.0f}원 배분:")
            for a in fill["allocations"][:3]:
                lines.append(f"      - {a['label']} {a['amount_krw']:,.0f}원")

    lines.append("")
    lines.append("※ 현황과 규칙 해당 여부만 알립니다. 매매 판단은 포함하지 않습니다.")
    return "\n".join(lines)


def audit(obj, path="report"):
    """금지 필드/문구가 섞였는지 재귀 검사(market_indicators.py/rule_trigger_report.py와
    같은 패턴). 2026-08-10 "자유텍스트 금지문구 전수 점검"으로 발견됨 — 이 파일은
    FORBIDDEN_FIELDS만 self-test에서 확인했을 뿐, 저장 시점에 실제로 강제한 적이
    없었다."""
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


def run(args):
    real = load_json(REAL_PORTFOLIO_FILE, None)
    if not real:
        print(f"⚠️ {REAL_PORTFOLIO_FILE} 없음 - sync_real.yml 실행 후 다시 시도")
        return
    income = load_json(INCOME_SCHEDULE_FILE, {"placeholder": True})
    state = load_json(STATE_FILE, {"loss_since": {}})
    asset_class_mapping = load_json(ASSET_CLASS_MAPPING_FILE, None)
    target_allocation = load_json(TARGET_ALLOCATION_FILE, None)

    snapshot_rows = compute_positions(real)["positions"]
    symbol_closes = fetch_symbol_candles(snapshot_rows)

    report, state = build_report(real, income, state, symbol_closes=symbol_closes,
                                  asset_class_mapping=asset_class_mapping,
                                  target_allocation=target_allocation)

    violations = audit(report)
    if violations:
        print("❌ 감사 위반 발견 - 저장/전송 거부:")
        for v in violations:
            print(f"   - {v}")
        raise SystemExit(1)

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

    # 5) 예측성 필드/금지 문구가 리포트 어디에도 없는지 (재귀 검사, audit() 재사용)
    report, _ = build_report(real, {"placeholder": True}, {"loss_since": {}}, "2026-08-04")
    found = audit(report)
    print(f"[5] 리포트 내 감사 위반: {found or '없음'}")
    assert not found, f"금지 필드/문구가 리포트에 있음: {found}"

    # 5b) [2026-08-10] 이 파일은 지금까지 FORBIDDEN_FIELDS만 검사했고 문구
    # 자체를 저장 시점에 강제한 적이 없었다 — 실제로 audit()가 잡아내는지,
    # 그리고 run()이 위반 시 저장/전송을 거부하는지 확인한다.
    dirty = {"rule_matches": [{"rule": "집중도", "fact": "SCHD 비중이 높아 정리하세요"}]}
    violations = audit(dirty)
    print(f"[5b] 오염된 리포트 -> 위반 {violations}")
    assert any("정리하세요" in v for v in violations)

    import sys
    import unittest.mock as mock
    mod = sys.modules[__name__]
    fake_args = type("Args", (), {"telegram": True})()
    with mock.patch.object(mod, "build_report", return_value=(dirty, {"loss_since": {}})), \
         mock.patch.object(mod, "load_json", side_effect=lambda path, default: real if path == REAL_PORTFOLIO_FILE else default), \
         mock.patch.object(mod, "save_json") as mock_save, \
         mock.patch.object(mod, "send_telegram") as mock_send, \
         mock.patch.object(mod, "fetch_symbol_candles", return_value={}):
        try:
            run(fake_args)
            raised = False
        except SystemExit:
            raised = True
        print(f"[5b] 오염된 리포트로 run() 호출 -> SystemExit={raised}, "
              f"save_json 호출됨={mock_save.called}, send_telegram 호출됨={mock_send.called}")
        assert raised, "위반이 있는데 SystemExit이 발생하지 않음"
        assert not mock_save.called, "위반이 있는데 save_json이 호출됨"
        assert not mock_send.called, "위반이 있는데 send_telegram이 호출됨"

    # 6) 매매 지시성 표현이 텍스트에 없는지 (공유 FORBIDDEN_PHRASES 전부 재사용)
    text = format_telegram(report)
    for banned in FORBIDDEN_PHRASES:
        assert banned not in text, f"리포트 텍스트에 금지 문구 '{banned}'이 있음"
    print("[6] 텔레그램 텍스트: 금지 문구 없음 확인")

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

    # 실제 입대일(2026-04-27) 기준 전역월 2027-10이면 초과 경고가 사라지는지.
    # 이 케이스가 회귀하면 로드맵이 다시 잘못된 경고를 띄우게 된다.
    fixed = json.loads(json.dumps(anchored))
    fixed["service"]["discharge"] = "2027-10"
    rm8 = compute_roadmap(fixed)
    print(f"[7g] 전역월 2027-10 반영 -> 경고 {len(rm8['schedule_warnings'])}건")
    assert rm8["schedule_warnings"] == [], f"경고가 남음: {rm8['schedule_warnings']}"
    assert rm8["total_investable_krw"] == 16950000

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

    # 9) Risk Engine — 변동성/포지션 사이징: 변동성이 클수록 권장액이 작아지는지,
    #    상한(single_trade_cap_pct/position_hard_cap_pct 중 낮은 쪽)을 절대 넘지 않는지
    low_vol = calc_position_sizing(10_000_000, 1.0)
    high_vol = calc_position_sizing(10_000_000, 8.0)
    print(f"[9] 변동성 1%: {low_vol['recommended_range_krw']} / 변동성 8%: {high_vol['recommended_range_krw']}")
    assert low_vol["recommended_range_krw"]["max"] > high_vol["recommended_range_krw"]["max"], \
        "변동성이 클수록 권장액이 작아져야 함"
    ceiling = 10_000_000 * min(RISK_ENGINE["single_trade_cap_pct"], RISK_ENGINE["position_hard_cap_pct"]) / 100
    assert low_vol["ceiling_krw"] == round(ceiling)
    assert all(v <= ceiling for v in low_vol["by_strategy_krw"].values()), "상한을 넘으면 안 됨"
    assert "매수" not in json.dumps(low_vol, ensure_ascii=False), "계산 결과에 매매 지시 문구가 섞이면 안 됨"

    # 10) Risk Engine — MDD 예산 소진율 산술 검산 (가중평균)
    rows_mdd = [{"eval_amount_krw": 600000, "return_pct": -10.0},
                {"eval_amount_krw": 400000, "return_pct": 0.0}]
    budget = calc_mdd_budget_usage(rows_mdd, 1_000_000)
    print(f"[10] MDD 소진: {budget}")
    # 가중평균 = 0.6*(-10) + 0.4*0 = -6.0%, 한도 -20% 대비 소진율 = -6/-20*100 = 30%
    assert budget["portfolio_unrealized_return_pct"] == -6.0
    assert budget["budget_usage_pct"] == 30.0

    # 11) Risk Engine — 상관계수: 완전 동일 시계열은 +1, 완전 반대는 -1에 가까워야 함
    base = [1.0, -0.5, 2.0, -1.0, 0.5, 1.5, -2.0, 0.8, -0.3, 1.2, 0.4, -0.6]
    same = calc_correlation(base, base)
    inverse = calc_correlation(base, [-x for x in base])
    print(f"[11] 동일 시계열 상관={same:.3f} / 반대 시계열 상관={inverse:.3f}")
    assert abs(same - 1.0) < 1e-9
    assert abs(inverse - (-1.0)) < 1e-9
    matrix = calc_correlation_matrix({"A": base, "B": base, "C": [-x for x in base]})
    flagged_syms = {(f["symbol_a"], f["symbol_b"]) for f in matrix["flagged_pairs"]}
    print(f"[11] 임계치(0.7) 이상 쌍: {flagged_syms}")
    assert ("A", "B") in flagged_syms and ("A", "C") in flagged_syms

    # 12) Risk Engine — 비용반영후 수치: 두 경우 다 원래 수익률보다 깎이는지.
    #     KRX(수수료0.015+슬리피지0.1+거래세0.18=0.295%)와 해외(수수료0.25+
    #     슬리피지0.1=0.35%, 거래세는 없지만 가정 수수료율 자체가 더 높음)를
    #     실측했더니 이 저장소의 기존 TRADING_COSTS 가정치 기준으로는 해외
    #     쪽이 오히려 더 많이 깎인다 — "KRX가 거래세 때문에 항상 더 비싸다"는
    #     직관과 다른 결과라 값 자체를 검산해 남긴다(기존 가정치를 바꾸지 않음).
    rows_cost = [{"symbol": "K", "name": "국내", "return_pct": 5.0, "market_country": "KR", "currency": "KRW"},
                 {"symbol": "U", "name": "해외", "return_pct": 5.0, "market_country": "US", "currency": "USD"}]
    adj = calc_cost_adjusted(rows_cost)
    krx_row = next(x for x in adj if x["symbol"] == "K")
    us_row = next(x for x in adj if x["symbol"] == "U")
    print(f"[12] KRX 비용반영후={krx_row['cost_adjusted_return_pct']} / 해외 비용반영후={us_row['cost_adjusted_return_pct']}")
    assert krx_row["sell_cost_pct"] == 0.295 and us_row["sell_cost_pct"] == 0.35
    assert krx_row["cost_adjusted_return_pct"] < krx_row["return_pct"], "비용은 항상 수익률을 깎아야 함(도움되면 버그)"
    assert us_row["cost_adjusted_return_pct"] < us_row["return_pct"], "비용은 항상 수익률을 깎아야 함(도움되면 버그)"

    # 13) Risk Engine 섹션도 예측성 필드/매매 지시 문구가 없는지(항목 5·6과 같은 규율)
    report_with_re, _ = build_report(
        real, {"placeholder": True}, {"loss_since": {}}, "2026-08-04",
        symbol_closes={"A": [100 + i * 0.3 for i in range(100)], "B": [200 - i * 0.1 for i in range(100)]},
    )
    bad2 = audit(report_with_re)
    print(f"[13] symbol_closes 채운 리포트 감사 위반: {bad2 or '없음'}")
    assert not bad2
    assert report_with_re["risk_engine"]["position_sizing"][0]["sizing"] is not None, \
        "가격 이력이 있으면 사이징이 계산돼야 함"
    text2 = format_telegram(report_with_re)
    for banned in ("매수", "매도", "파세요", "사세요", "추천", "정리하세요"):
        assert banned not in text2, f"Risk Engine 포함 텔레그램 텍스트에 매매 지시 표현 '{banned}' 있음"

    # ── 14~19) 자산군 배분 갭 계산 (2026-08-10) ──────────────────────────────
    mapping = {"mappings": [
        {"symbol": "A", "asset_class": "기존_배당"},
        {"symbol": "B", "asset_class": "developed_exUS"},
    ]}
    target_alloc = {
        "safe_classes": ["bond", "cash"],
        "safe_class_labels": {"bond": "채권", "cash": "현금성"},
        "risk_classes": ["기존_배당", "developed_exUS", "emerging"],
        "risk_class_labels": {"기존_배당": "배당", "developed_exUS": "선진국(미국 제외)", "emerging": "신흥국"},
        "safe_total_pct_by_rank": {"일병": 10, "상병": 20, "병장": 30},
        "provisional": True,
    }
    # A(기존_배당) 60%, B(developed_exUS) 30%, 현금 10%, C(미매핑) 없음
    rows14 = [{"symbol": "A", "name": "가", "weight_pct": 60.0},
              {"symbol": "B", "name": "나", "weight_pct": 30.0}]

    # 14) 실제 비중 집계 — 현금은 cash 자산군에 그대로 더해지는지
    actual, unmapped = compute_class_actual_pct(rows14, 10.0, load_symbol_class_map(mapping))
    print(f"[14] 실제 비중: {actual} / 미매핑: {unmapped}")
    assert actual["기존_배당"] == 60.0 and actual["developed_exUS"] == 30.0 and actual["cash"] == 10.0
    assert unmapped == []

    # 15) 목표 비중 — 매핑 안 된 자산군(emerging)은 목표도 0%, 매핑된 것끼리
    #     안전/위험 총비중을 균등분배해 합이 100%가 되는지
    target = compute_class_target_pct(target_alloc, {"기존_배당", "developed_exUS", "cash"}, "일병")
    print(f"[15] 목표 비중(일병): {target}")
    assert target["emerging"] == 0.0, "매핑 안 된 위험자산군은 목표도 0%여야 함"
    assert target["bond"] == 0.0, "매핑 안 된 안전자산군(채권)은 목표도 0%여야 함"
    assert target["cash"] == 10.0, "안전자산 총비중(10%)이 매핑된 cash 하나에 전부 배분돼야 함"
    assert abs(target["기존_배당"] - 45.0) < 1e-9 and abs(target["developed_exUS"] - 45.0) < 1e-9, \
        "위험자산 총비중(90%)이 매핑된 두 자산군에 균등분배(45%씩)돼야 함"
    assert abs(sum(target.values()) - 100.0) < 1e-9, "목표 비중 합은 항상 100%여야 함"

    # 16) 전체 gap 계산 — 미매핑 보유종목(C)이 있으면 별도로 잡히고, 갭 부호가
    #     맞는지(실제가 목표보다 크면 음수, 작으면 양수)
    rows16 = rows14 + [{"symbol": "C", "name": "다", "weight_pct": 5.0}]
    gap = compute_asset_class_gap(rows16, 5.0, mapping, target_alloc, "일병")
    print(f"[16] 미매핑 보유종목: {gap['unmapped_holdings']} (비중합 {gap['unmapped_holdings_weight_pct']}%)")
    assert gap["unmapped_holdings"] == [{"symbol": "C", "name": "다", "weight_pct": 5.0}]
    assert gap["unmapped_holdings_weight_pct"] == 5.0
    row_배당 = next(r for r in gap["rows"] if r["asset_class"] == "기존_배당")
    print(f"[16] 배당 자산군: 목표{row_배당['target_pct']} / 실제{row_배당['actual_pct']} / 갭{row_배당['gap_pct']}")
    assert row_배당["gap_pct"] == round(row_배당["target_pct"] - row_배당["actual_pct"], 2)
    row_emerging = next(r for r in gap["rows"] if r["asset_class"] == "emerging")
    assert row_emerging["target_pct"] == 0.0 and row_emerging["actual_pct"] == 0.0 and row_emerging["gap_pct"] == 0.0, \
        "매핑 안 된 자산군은 갭도 0%p로 나와야 함(지시서 §2 '갭 0%로 나오는 게 정상')"

    # 17) 그룹 전체가 미매핑이면(고아 방지) 그룹 전체를 균등분배하는지
    target_empty_safe = compute_class_target_pct(target_alloc, {"기존_배당", "developed_exUS"}, "상병")
    print(f"[17] 안전자산군 전부 미매핑 -> {['bond', 'cash']} 목표: "
          f"{target_empty_safe['bond']}/{target_empty_safe['cash']}")
    assert target_empty_safe["bond"] == target_empty_safe["cash"] == 10.0, \
        "그룹 전체가 미매핑이면 그 그룹을 균등분배해야 함(상병 안전자산 20%/2)"

    # 18) 계급별 월 유입액 조회 — 시작일 경계에서 올바른 계급을 찾는지
    income18 = {"ranks": [{"rank": "일병", "start": "2026-08", "monthly_krw": 850000},
                          {"rank": "상병", "start": "2027-01", "monthly_krw": 1150000}]}
    r_before = current_rank_for_month(income18, "2026-12")
    r_after = current_rank_for_month(income18, "2027-01")
    print(f"[18] 2026-12 -> {r_before['rank']} / 2027-01 -> {r_after['rank']}")
    assert r_before["rank"] == "일병" and r_after["rank"] == "상병"

    # 19) 월별 갭 채우기 — 갭이 양수인 자산군에만, 갭 크기 비례로 배분되고
    #     합이 그 달 유입액과 일치하는지(반올림 오차 허용)
    fill = compute_monthly_gap_fill(gap, income18, "2026-08", months=2)
    print(f"[19] 이번 달 배분: {fill[0]['allocations']}")
    assert fill[0]["rank"] == "일병" and fill[0]["monthly_investable_krw"] == 850000
    alloc_sum = sum(a["amount_krw"] for a in fill[0]["allocations"])
    print(f"[19] 배분액 합계={alloc_sum:,} vs 유입액={fill[0]['monthly_investable_krw']:,}")
    assert abs(alloc_sum - fill[0]["monthly_investable_krw"]) <= 1, "양수 갭 자산군에만 배분해도 유입액 전액이 소진돼야 함"
    assert all(a["asset_class"] != "emerging" or a["amount_krw"] == 0 for a in fill[0]["allocations"]) or \
        not any(a["asset_class"] == "emerging" for a in fill[0]["allocations"]), \
        "갭이 0인 자산군(emerging)에는 배분되면 안 됨"

    # 20) build_report()에 asset_class_mapping/target_allocation을 넘기면
    #     asset_class_gap이 채워지고, 안 넘기면(둘 다 None) 조용히 비는지 —
    #     감사도 통과하는지(자산군 라벨/비고 문구에 금지어가 없는지)
    real20 = {"synced_at": "2026-08-10T00:00:00+00:00", "cash": 50000.0, "positions": [
        {"symbol": "A", "name": "가", "market_country": "US", "eval_amount_krw": 600000.0, "return_pct": 1.0},
        {"symbol": "B", "name": "나", "market_country": "US", "eval_amount_krw": 300000.0, "return_pct": 1.0},
    ]}
    income20 = dict(income18, placeholder=False)
    report20, _ = build_report(real20, income20, {"loss_since": {}}, "2026-08-10",
                               symbol_closes={}, asset_class_mapping=mapping, target_allocation=target_alloc)
    print(f"[20] asset_class_gap 존재: {report20['asset_class_gap'] is not None}")
    assert report20["asset_class_gap"] is not None
    assert audit(report20) == [], f"자산군 갭 포함 리포트가 감사를 통과 못 함: {audit(report20)}"

    report21, _ = build_report(real20, income20, {"loss_since": {}}, "2026-08-10", symbol_closes={})
    print(f"[21] mapping/target_allocation 미제공 -> asset_class_gap={report21['asset_class_gap']}")
    assert report21["asset_class_gap"] is None, "데이터가 없으면 지어내지 말고 None이어야 함"

    text3 = format_telegram(report20)
    for banned in FORBIDDEN_PHRASES:
        assert banned not in text3, f"자산군 갭 포함 텔레그램 텍스트에 금지 문구 '{banned}' 있음"
    print("[20-21] asset_class_gap 포함 리포트/텔레그램 텍스트 검증 통과")

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    main()
