"""[v3.2 활성 기능] 시장 상태 수치판 + 지표 병렬 표시판 (2026-08-09, 방향성 세션 지시).

**"국면 판별"도 "종목 스코어링"도 아니다.** 지시 원문의 공통 규칙을 그대로 코드
수준 제약으로 옮긴다:

  - "국면", "점수", "스코어" 등 종합 판단으로 보일 수 있는 단일 지표·순위 생성 금지
  - 개별 계산값을 항목별로 나열만 — 합산 점수, 순위 정렬, 색상 신호등 전부 금지
  - "그래서 사도 됨/팔아야 함"으로 해석될 수 있는 결론 문장 금지

**1. 시장 상태 수치판** (국면 판별의 재정의): 변동성은 "최근 20일 변동성의 과거
분포 안에서의 백분위"까지만 — "상승장 진입" 같은 라벨을 만들지 않는다. 추세
강도는 `calc_adx`가 반환하는 숫자 그 자체이며, 이 파일은 그 값에 아무 해석도
얹지 않는다(25 이상이면 "추세가 있다"는 게이트로 쓰는 건 entry_score/backtest의
용법이지 여기 용법이 아니다). 상관관계는 보유 종목 간 일간수익률의 평균 쌍별
피어슨 상관계수 — 지시 원문이 "보유 종목 간"이라고 명시했으므로 관심종목은
포함하지 않는다.

**2. 지표 병렬 표시판** (종목 스코어링의 재정의): 종목별 객관적 지표를 표로만
나열한다. 합산도, 순위도 매기지 않는다 — **출력 리스트 순서는 항상
`real_portfolio.json`/관심종목 원본 순서를 그대로 보존**하고, 어떤 계산값으로도
재정렬하지 않는다(대시보드에서 사람이 직접 정렬하는 건 허용 — 프로그램이 먼저
정렬해서 제시하지 않을 뿐). PER은 이 저장소에 연결된 펀더멘털 데이터 소스가
없으므로(Phase3_펀더멘털신호_스펙.md §8-1, rule_trigger_report.py와 동일 원칙)
`null` + `"데이터 소스 미연결"`로만 표시한다 — 숫자를 지어내지 않는다.

**대상 종목**: 상태판의 개별 지표 행과 지표 표시판은 뉴스 카드와 같은 유니버스
(보유+관심, `news_event_cards.build_universe()` 재사용)를 쓴다. 상관관계
집계만 지시 원문대로 보유종목으로 한정한다.

**위반 시 전체 반려**: `audit()`가 금지 필드/문구를 하나라도 찾으면 `run()`은
파일을 저장하지 않고 0이 아닌 코드로 종료한다(rule_trigger_report.py처럼 위반을
태그만 달아 그대로 저장하지 않는다 — 이 작업의 지시가 "위반 시 전체 반려"를
명시했기 때문에 더 엄격한 동작을 쓴다).
"""
import argparse
from datetime import datetime, timezone

from analyze_lib import calc_adx, load_json, save_json
from news_event_cards import build_universe, fetch_candles_for_anomaly as fetch_candles

INDICATORS_FILE = "market_indicators.json"
REAL_PORTFOLIO_FILE = "real_portfolio.json"

STATE_VOL_WINDOW = 20          # 변동성 계산 창(거래일)
STATE_LOOKBACK_CANDLES = 300   # 백분위를 매길 과거 분포 확보용 캔들 수
CORRELATION_WINDOW = 60        # 상관계수 계산에 쓰는 최근 거래일수
MOMENTUM_WINDOW = 20           # 모멘텀(가격 변화율) 계산 창
ADX_PERIOD = 14

# 이 표/판에 실릴 수 있는 필드. 이 목록 밖의 키는 만들지 않는다(뉴스 카드
# CARD_FIELDS와 같은 패턴 — 화이트리스트가 곧 "종합판단 필드를 안 만든다"는
# 설계의 강제 장치다).
STATE_ROW_FIELDS = ("symbol", "name", "volatility_20d_pct", "volatility_percentile",
                     "adx_14", "data_status")
INDICATOR_ROW_FIELDS = ("symbol", "name", "per", "per_status",
                         "volatility_20d_pct", "momentum_20d_pct", "adx_14", "data_status")

# 이 리포트 전체(중첩 포함)에 절대 있으면 안 되는 필드/문구. audit()가 재귀 검사한다.
FORBIDDEN_FIELDS = ("score", "rank", "ranking", "phase", "regime", "국면", "점수", "순위",
                     "signal", "color", "colour", "grade", "rating", "recommendation",
                     "direction", "confidence", "action", "buy", "sell", "등급", "신호등")
FORBIDDEN_PHRASES = (
    "상승장", "하락장", "국면 전환", "국면 진입", "진입 임박",
    "매수", "매도하세요", "사세요", "파세요", "추천", "권장", "권합니다",
    "사도 됨", "팔아야", "1위", "순위",
)


# ── 순수 계산 (numpy 없이) ───────────────────────────────────────────────

def daily_returns(closes):
    return [(closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes)) if closes[i - 1]]


def rolling_volatility_series(closes, window=STATE_VOL_WINDOW):
    """일간수익률의 표준편차를 window 구간씩 굴려가며 계산한 시계열.
    마지막 값이 "오늘의 20일 변동성"이고, 시계열 전체가 백분위를 매길
    과거 분포다."""
    rets = daily_returns(closes)
    series = []
    for i in range(window, len(rets) + 1):
        chunk = rets[i - window:i]
        mean = sum(chunk) / len(chunk)
        var = sum((r - mean) ** 2 for r in chunk) / len(chunk)
        series.append(var ** 0.5)
    return series


def historical_percentile(series):
    """series의 마지막 값이 series 전체 분포에서 몇 번째 백분위인지.
    "지금 값 / 과거 분포에서의 위치"만 반환 — 라벨을 붙이지 않는다."""
    if not series:
        return None
    current = series[-1]
    rank = sum(1 for v in series if v <= current)
    return round(100 * rank / len(series), 1)


def pearson_corr(a, b):
    n = min(len(a), len(b))
    if n < 2:
        return None
    a, b = a[-n:], b[-n:]
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((x - mean_b) ** 2 for x in b)
    denom = (var_a * var_b) ** 0.5
    if denom == 0:
        return None
    return cov / denom


# ── 캔들 → 지표 ───────────────────────────────────────────────────────

def _fetch(symbol, market_country):
    return fetch_candles(symbol, market_country, count=STATE_LOOKBACK_CANDLES)


def _vol_and_adx(candles):
    """캔들에서 (volatility_20d_pct, volatility_percentile, adx_14)를 뽑는다.
    데이터가 부족하면 계산 가능한 것만 채우고 나머지는 None."""
    if not candles or len(candles) < STATE_VOL_WINDOW + 2:
        return None, None, None
    closes = [c["close"] for c in candles]
    vol_series = rolling_volatility_series(closes, STATE_VOL_WINDOW)
    vol_pct = round(vol_series[-1] * 100, 2) if vol_series else None
    vol_percentile = historical_percentile(vol_series)
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    adx = calc_adx(highs, lows, closes, period=ADX_PERIOD)
    adx_val = round(adx, 1) if len(closes) >= ADX_PERIOD + 1 else None
    return vol_pct, vol_percentile, adx_val


def _momentum(candles, window=MOMENTUM_WINDOW):
    if not candles or len(candles) < window + 1:
        return None
    closes = [c["close"] for c in candles]
    base = closes[-1 - window]
    if not base:
        return None
    return round((closes[-1] - base) / base * 100, 2)


# ── 리포트 조립 ───────────────────────────────────────────────────────

def compute_state_board(universe, candles_by_symbol):
    rows = []
    for u in universe:
        candles = candles_by_symbol.get(u["symbol"])
        vol_pct, vol_percentile, adx_val = _vol_and_adx(candles)
        status = None if candles else "시세 조회 실패"
        if candles and vol_pct is None:
            status = "데이터 부족"
        row = {"symbol": u["symbol"], "name": u["name"],
               "volatility_20d_pct": vol_pct, "volatility_percentile": vol_percentile,
               "adx_14": adx_val, "data_status": status}
        rows.append({k: row[k] for k in STATE_ROW_FIELDS})
    return rows


def compute_correlation_summary(real_positions, candles_by_symbol, window=CORRELATION_WINDOW):
    """지시 원문 "보유 종목 간 평균 상관계수" — 관심종목은 포함하지 않는다."""
    returns_by_symbol = {}
    for p in real_positions:
        sym = p.get("symbol")
        candles = candles_by_symbol.get(sym)
        if candles and len(candles) >= 2:
            returns_by_symbol[sym] = daily_returns([c["close"] for c in candles])

    syms = list(returns_by_symbol.keys())
    pairs = []
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            r = pearson_corr(returns_by_symbol[syms[i]][-window:], returns_by_symbol[syms[j]][-window:])
            if r is not None:
                pairs.append(r)
    avg = round(sum(pairs) / len(pairs), 3) if pairs else None
    return {
        "avg_pairwise_correlation": avg,
        "pair_count": len(pairs),
        "symbol_count": len(syms),
        "window_days": window,
    }


def compute_indicator_board(universe, candles_by_symbol):
    """순서는 universe 순서를 그대로 따른다 — 어떤 계산값으로도 재정렬하지 않는다."""
    rows = []
    for u in universe:
        candles = candles_by_symbol.get(u["symbol"])
        vol_pct, _vol_percentile, adx_val = _vol_and_adx(candles)
        momentum = _momentum(candles)
        status = None if candles else "시세 조회 실패"
        row = {
            "symbol": u["symbol"], "name": u["name"],
            "per": None, "per_status": "데이터 소스 미연결",
            "volatility_20d_pct": vol_pct, "momentum_20d_pct": momentum,
            "adx_14": adx_val, "data_status": status,
        }
        rows.append({k: row[k] for k in INDICATOR_ROW_FIELDS})
    return rows


def audit(obj, path="report"):
    """금지 필드/문구가 섞였는지 재귀 검사(rule_trigger_report.py의 audit()과
    같은 패턴). 이 파일은 위반 시 저장 자체를 거부하므로 이 함수가 곧 게이트다."""
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


def build_report():
    # 2026-08-10 방향성 세션 지시: 대시보드 기준시점 불일치 최소 조치 —
    # 날짜만으론 패널 간 신선도 차이(동기화 4x/일 vs 이 파일 1일 1회)가
    # 안 보인다. 시:분까지 담아 프런트가 "기준: YYYY-MM-DD HH:MM"으로
    # 그대로 표시할 수 있게 한다. UTC ISO로 저장하고(real_portfolio.json의
    # synced_at과 같은 패턴), 타임존 변환은 대시보드(브라우저 로컬)에서 한다.
    generated_at = datetime.now(timezone.utc).isoformat()
    real = load_json(REAL_PORTFOLIO_FILE, {"positions": []})
    real_positions = real.get("positions", [])
    universe = build_universe()  # 보유 + 관심종목 (news_event_cards와 동일 유니버스)

    candles_by_symbol = {}
    for u in universe:
        candles_by_symbol[u["symbol"]] = _fetch(u["symbol"], u["market_country"])

    return {
        "generated_at": generated_at,
        "schema": "market_indicators_v3.2",
        "note": ("개별 계산값을 항목별로만 나열합니다. 지표들을 하나로 합치지 않고, "
                 "종목 간 우열을 매겨 배열하지 않으며, 색을 이용한 강조도 하지 않습니다. "
                 "표의 나열 순서는 원본(보유+관심종목) 그대로이며 계산값 크기로 다시 "
                 "배열하지 않습니다."),
        "state_board": {
            "note": "지금 값 / 과거 분포에서의 위치만 표시합니다. 라벨을 붙이지 않습니다.",
            "rows": compute_state_board(universe, candles_by_symbol),
            "correlation": compute_correlation_summary(real_positions, candles_by_symbol),
        },
        "indicator_board": {
            "note": "종목별 지표를 병렬로만 나열합니다. 정렬은 표시 화면에서 사람이 합니다.",
            "rows": compute_indicator_board(universe, candles_by_symbol),
        },
    }


def save_if_clean(report):
    violations = audit(report)
    if violations:
        print("❌ 감사 위반 발견 - 저장 거부(위반 시 전체 반려):")
        for v in violations:
            print(f"   - {v}")
        raise SystemExit(1)
    save_json(INDICATORS_FILE, report)
    print(f"저장 완료 → {INDICATORS_FILE} "
          f"(state_board {len(report['state_board']['rows'])}건, "
          f"indicator_board {len(report['indicator_board']['rows'])}건)")
    return report


def run(args):
    save_if_clean(build_report())


def main():
    p = argparse.ArgumentParser(description="시장 상태 수치판 + 지표 병렬 표시판 (종합판단 아님)")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        run_self_test()
        return
    run(a)


def run_self_test():
    print("=== market_indicators.py 자체 검증 (네트워크 미사용) ===\n")

    # 1) 변동성 백분위: 갈수록 변동성이 커지는 합성 시계열이면 마지막 값이
    #    분포 최상단(100)에 가까워야 한다.
    import math
    closes = [100.0]
    for i in range(1, 260):
        # 뒤로 갈수록 진폭이 커지는 사인파 — 뒷부분 변동성이 항상 더 크다.
        amp = 0.001 + (i / 260) * 0.05
        closes.append(closes[-1] * (1 + amp * math.sin(i)))
    series = rolling_volatility_series(closes, STATE_VOL_WINDOW)
    pct = historical_percentile(series)
    print(f"[1] 증가 변동성 합성 데이터 -> 마지막 값 백분위 {pct}")
    assert pct is not None and pct >= 70, f"증가 추세인데 백분위가 낮음: {pct}"

    # 2) 피어슨 상관계수: 완전 동행/역행 시계열에서 +-1에 근접해야 한다.
    a_series = [i * 0.01 for i in range(30)]
    b_same = [x * 2 for x in a_series]
    b_inv = [-x for x in a_series]
    r_pos = pearson_corr(a_series, b_same)
    r_neg = pearson_corr(a_series, b_inv)
    print(f"[2] 완전동행 상관계수={r_pos:.3f}, 완전역행 상관계수={r_neg:.3f}")
    assert r_pos > 0.99, "완전 동행 시계열의 상관계수가 1에 가깝지 않음"
    assert r_neg < -0.99, "완전 역행 시계열의 상관계수가 -1에 가깝지 않음"

    # 3) 지표 병렬 표시판 순서 보존 — 계산값으로 재정렬하면 안 된다.
    #    변동성이 큰 종목을 일부러 universe 뒤쪽에 둬서, 재정렬 로직이 있었다면
    #    순서가 바뀌었을 상황을 만든다.
    def make_candles(n, prices):
        out = []
        for i in range(n):
            p = prices[i % len(prices)]
            out.append({"open": p, "high": p * 1.01, "low": p * 0.99, "close": p, "volume": 1000})
        return out

    quiet = make_candles(60, [100.0])
    volatile = make_candles(60, [100.0, 130.0, 80.0, 140.0, 70.0])
    fake_universe = [
        {"symbol": "AAA", "name": "가", "market_country": "US"},
        {"symbol": "BBB", "name": "나", "market_country": "US"},
        {"symbol": "CCC", "name": "다", "market_country": "US"},
    ]
    fake_candles = {"AAA": quiet, "BBB": volatile, "CCC": quiet}
    board = compute_indicator_board(fake_universe, fake_candles)
    order = [r["symbol"] for r in board]
    print(f"[3] 입력 순서=[AAA, BBB, CCC] -> 출력 순서={order}")
    assert order == ["AAA", "BBB", "CCC"], "지표 표시판이 입력 순서를 보존하지 않음(재정렬 의심)"
    for r in board:
        assert set(r) == set(INDICATOR_ROW_FIELDS), f"허용 필드 밖의 키가 있음: {r}"
        assert r["per"] is None and r["per_status"] == "데이터 소스 미연결"

    # 4) PER 미연결 표시가 숫자를 지어내지 않는지, 상태판도 화이트리스트를 지키는지
    state_rows = compute_state_board(fake_universe, fake_candles)
    for r in state_rows:
        assert set(r) == set(STATE_ROW_FIELDS), f"상태판에 허용 밖 키: {r}"
    print(f"[4] 상태판 필드 집합 확인: {sorted(STATE_ROW_FIELDS)}")

    # 5) 감사(audit) — 금지 필드/문구를 재귀적으로 잡아내는지
    dirty = {
        "state_board": {"rows": [{"symbol": "005930", "score": 87}]},
        "indicator_board": {"rows": [{"symbol": "NVDA", "note": "지금이 매수 적기입니다"}]},
    }
    violations = audit(dirty)
    print(f"[5] 오염된 리포트 -> 위반 {violations}")
    assert any("score" in v for v in violations), "금지 필드(score)를 못 잡음"
    assert any("매수" in v for v in violations), "금지 문구(매수)를 못 잡음"

    clean = build_report_stub_for_test()
    assert audit(clean) == [], f"정상 리포트인데 위반이 잡힘: {audit(clean)}"
    print("[5] 정상 리포트는 위반 0건 확인")

    # 6) 위반 시 전체 반려 — save_json이 호출되지 않고 SystemExit이 나야 한다
    import sys
    import unittest.mock as mock
    mod = sys.modules[__name__]
    with mock.patch.object(mod, "save_json") as mock_save:
        try:
            save_if_clean(dirty)
            raised = False
        except SystemExit:
            raised = True
        print(f"[6] 오염된 리포트로 save_if_clean 호출 -> SystemExit={raised}, save_json 호출됨={mock_save.called}")
        assert raised, "위반이 있는데 SystemExit이 발생하지 않음"
        assert not mock_save.called, "위반이 있는데 save_json이 호출됨(전체 반려 원칙 위반)"

    # 7) 정상 리포트는 실제로 저장 경로를 타는지 (save_json 자체는 모킹)
    with mock.patch.object(mod, "save_json") as mock_save:
        result = save_if_clean(clean)
        print(f"[7] 정상 리포트 -> save_json 호출됨={mock_save.called}")
        assert mock_save.called, "위반이 없는데도 저장되지 않음"
        assert result is clean

    # 8) build_report() 자체가 만드는 고정 문구(note 등)가 감사를 통과하는지 —
    #    "이걸 안 한다"고 설명하는 문장 자체가 금지어를 문자 그대로 담아버리는
    #    실수(news_event_cards.py self-test가 겪었던 자기지시적 함정과 같은 종류)를
    #    잡는다. 네트워크 호출은 build_universe를 빈 리스트로 모킹해 건너뛴다.
    with mock.patch.object(mod, "build_universe", return_value=[]), \
         mock.patch.object(mod, "load_json", return_value={"positions": []}):
        report = build_report()
    violations = audit(report)
    print(f"[8] build_report() 고정 문구 감사 -> 위반 {violations}")
    assert violations == [], f"build_report()의 고정 문구가 자체 감사를 통과 못 함: {violations}"

    print("\n모든 자체 검증 통과.")


def build_report_stub_for_test():
    return {
        "generated_at": "2026-08-09",
        "schema": "market_indicators_v3.2",
        "note": "개별 계산값을 항목별로만 나열합니다.",
        "state_board": {
            "note": "지금 값 / 과거 분포에서의 위치만 표시합니다.",
            "rows": [{"symbol": "005930", "name": "삼성전자", "volatility_20d_pct": 1.2,
                      "volatility_percentile": 55.0, "adx_14": 21.3, "data_status": None}],
            "correlation": {"avg_pairwise_correlation": 0.42, "pair_count": 3,
                             "symbol_count": 3, "window_days": 60},
        },
        "indicator_board": {
            "note": "종목별 지표를 병렬로만 나열합니다.",
            "rows": [{"symbol": "005930", "name": "삼성전자", "per": None,
                      "per_status": "데이터 소스 미연결", "volatility_20d_pct": 1.2,
                      "momentum_20d_pct": 3.4, "adx_14": 21.3, "data_status": None}],
        },
    }


if __name__ == "__main__":
    main()
