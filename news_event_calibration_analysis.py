"""뉴스 이벤트 캘리브레이션 분석 (Phase2_뉴스이벤트추출_인수인계.md §7 설계를 코드로 구현,
2026-08-02 ECE/MCE + 통계적 유의성 검증 모듈로 확장 — "다운타운 상시 작업 목록 A-4").

**읽기 전용 분석 스크립트다.** `news_event_experiment.py`(매일 판단을 기록하고
outcomes를 채우는 파이프라인)와 물리적으로 분리했다 — 이 파일은
`news_event_calibration_log.json`을 읽기만 하고 절대 쓰지 않는다. 매매 로직
(`analyze.py`/`analyze_lib.py`/`ask_claude_decision`)은 이 파일에서 전혀 건드리지
않는다 — 순수 사후 분석 도구.

적중(hit) 정의: direction이 "호재"이고 해당 window의 return_pct > 0, 또는 "악재"이고
return_pct < 0이면 적중. "중립"은 무엇이 "맞았다"인지 모호하므로 승률 계산(hit/miss)
에서 제외하고 표본 수만 별도 집계한다 — 강제로 0/1 분류해 승률을 왜곡시키지 않기
위함. ECE/MCE 계산에서도 같은 원칙으로 중립을 제외한다.

고확신/저확신 분리: confidence >= HIGH_CONFIDENCE_THRESHOLD(70) 고정 임계값.
중앙값(median) 분리는 표본이 늘 때마다 경계선이 움직여서 같은 판단이 시점에 따라
고확신/저확신을 오갈 수 있어 비교가 불안정해진다 — 그래서 고정값을 쓴다. 다만
실제 confidence 분포와 맞는지는 표본이 쌓인 뒤 재검토가 필요할 수 있다.

window(d1/d5/d20)는 독립적으로 계산한다 — 단기 반응과 중장기 반응이 다를 수 있어
하나로 합치지 않는다.

표본 부족 처리: 버킷(고확신/저확신 × window, 또는 ECE 계산 대상 전체)당 표본이
MIN_BUCKET_SAMPLES 미만이면 숫자를 내지 않고 "판단 보류"로 명시한다 — backtest.py의
SUCCESS_CRITERIA와 같은 취지(근거 없는 숫자로 성급한 결론을 내지 않기 위함).

2026-08-21(최초 코호트 D+20 도달) 전까지는 outcomes가 전부 null이라 이 스크립트를
실행해도 모든 window가 "판단 보류"로만 나온다 — 그게 정상이다. 실제 outcomes가
채워지면 이 파일을 그대로 실행하면 된다. `--self-test`로 실제 로그 없이도(더미
데이터로) 모듈 동작 자체는 지금 바로 검증할 수 있다.
"""
import argparse
import json
import math

NEWS_LOG_FILE = "news_event_calibration_log.json"
HIGH_CONFIDENCE_THRESHOLD = 70
MIN_BUCKET_SAMPLES = 10
WINDOWS = ("d1", "d5", "d20")
DEFAULT_ECE_BINS = 10
SIGNIFICANCE_ALPHA = 0.05


def classify_hit(direction, return_pct):
    """"hit"/"miss"/"neutral"(판정 대상 아님) 중 하나."""
    if direction == "호재":
        return "hit" if return_pct > 0 else "miss"
    if direction == "악재":
        return "hit" if return_pct < 0 else "miss"
    return "neutral"


def eligible_records(records, window):
    """해당 window의 outcome이 채워진(return_pct가 null이 아닌) 레코드만."""
    out = []
    for r in records:
        outcome = r.get("outcomes", {}).get(window)
        if outcome and outcome.get("return_pct") is not None:
            out.append(r)
    return out


def _scored(records, window):
    """중립 제외, (confidence, hit 1/0) 쌍 리스트 + 제외된 중립 개수."""
    scored, neutral_count = [], 0
    for r in records:
        return_pct = r["outcomes"][window]["return_pct"]
        result = classify_hit(r.get("direction"), return_pct)
        if result == "neutral":
            neutral_count += 1
            continue
        if r.get("confidence") is None:
            continue
        scored.append((r["confidence"], 1 if result == "hit" else 0))
    return scored, neutral_count


def win_rate_for(records, window):
    """중립 제외 hit/(hit+miss) 비율. 표본 부족이면 win_rate_pct=None + verdict 사유.
    Fisher 검정에 쓸 수 있게 hits/misses 원시 카운트도 함께 반환한다."""
    scored, neutral_count = _scored(records, window)
    hits = sum(h for _, h in scored)
    misses = len(scored) - hits

    if len(scored) < MIN_BUCKET_SAMPLES:
        return {
            "sample_count": len(scored),
            "neutral_excluded": neutral_count,
            "hits": hits,
            "misses": misses,
            "win_rate_pct": None,
            "verdict": f"표본 부족({len(scored)}건 < 최소 {MIN_BUCKET_SAMPLES}건) - 판단 보류",
        }
    win_rate = hits / len(scored) * 100
    return {
        "sample_count": len(scored),
        "neutral_excluded": neutral_count,
        "hits": hits,
        "misses": misses,
        "win_rate_pct": round(win_rate, 2),
        "verdict": None,
    }


def _hypergeom_pmf(a, r1, r2, c1):
    """2x2 분할표에서 좌상단 셀이 정확히 a일 초기하분포 확률."""
    n = r1 + r2
    b, c = r1 - a, c1 - a
    d = (n - c1) - c
    if a < 0 or b < 0 or c < 0 or d < 0:
        return 0.0
    return (math.comb(r1, a) * math.comb(r2, c)) / math.comb(n, c1)


def fisher_exact_p_value(a, b, c, d):
    """2x2 분할표 [[a,b],[c,d]]의 Fisher's exact test 양측(two-tailed) p-value.
    scipy 없이 순수 stdlib(math.comb)로 계산 — 이 프로젝트는 의존성을 최소로
    유지한다(CLAUDE.md, 유일한 서드파티 의존성은 requests). 표본이 작을 걸
    감안해 정규근사(z-test)가 아니라 정확검정을 쓴다 — 초기 표본 규모에서
    z-test의 정규근사는 부정확할 수 있다."""
    r1, r2 = a + b, c + d
    c1 = a + c
    n = r1 + r2
    if n == 0 or r1 == 0 or r2 == 0 or c1 == 0 or c1 == n:
        return None
    lo, hi = max(0, c1 - r2), min(r1, c1)
    observed_p = _hypergeom_pmf(a, r1, r2, c1)
    total = 0.0
    for x in range(lo, hi + 1):
        px = _hypergeom_pmf(x, r1, r2, c1)
        if px <= observed_p * (1 + 1e-9):
            total += px
    return min(total, 1.0)


def significance_test(high_stats, low_stats):
    """고확신군/저확신군 승률 차이가 통계적으로 유의미한지 Fisher's exact test로
    검증. 두 그룹 다 hits/misses 카운트가 있어야 계산 가능 — win_rate_for()가
    표본 부족으로 win_rate_pct=None을 반환한 그룹은 hits/misses는 있어도(0일 수
    있음) 신뢰도가 낮다는 걸 감안해, MIN_BUCKET_SAMPLES 미만이면 검정 자체를
    "판단 보류"로 건너뛴다 — 승률 비교와 같은 표본 기준을 그대로 쓴다."""
    if high_stats["sample_count"] < MIN_BUCKET_SAMPLES or low_stats["sample_count"] < MIN_BUCKET_SAMPLES:
        return {
            "p_value": None,
            "significant": None,
            "method": "fisher_exact",
            "verdict": "표본 부족 - 유의성 검정 판단 보류",
        }
    p_value = fisher_exact_p_value(
        high_stats["hits"], high_stats["misses"], low_stats["hits"], low_stats["misses"]
    )
    return {
        "p_value": round(p_value, 4) if p_value is not None else None,
        "significant": (p_value is not None and p_value < SIGNIFICANCE_ALPHA),
        "method": "fisher_exact",
        "alpha": SIGNIFICANCE_ALPHA,
        "verdict": None,
    }


def compute_ece_mce(records, window, n_bins=DEFAULT_ECE_BINS):
    """Expected/Maximum Calibration Error. confidence(0-100)를 n_bins개 등폭
    구간으로 나눠, 구간별 평균 확신도(0-1 스케일)와 실제 적중률(accuracy) 차이를
    낸다. ECE = 구간별 |avg_confidence - accuracy|의 표본수 가중평균, MCE = 그
    중 최댓값. 표본이 MIN_BUCKET_SAMPLES 미만이면 계산하지 않고 판단 보류
    (구간이 n_bins개로 쪼개지면 표본이 더 작은 경우가 많아 신뢰도가 특히 낮다)."""
    eligible = eligible_records(records, window)
    scored, neutral_count = _scored(eligible, window)
    total_n = len(scored)

    if total_n < MIN_BUCKET_SAMPLES:
        return {
            "n_bins": n_bins, "sample_count": total_n, "neutral_excluded": neutral_count,
            "ece": None, "mce": None, "bins": [],
            "verdict": f"표본 부족({total_n}건 < 최소 {MIN_BUCKET_SAMPLES}건) - 판단 보류",
        }

    bin_width = 100 / n_bins
    bins = [[] for _ in range(n_bins)]
    for conf, hit in scored:
        idx = min(int(conf // bin_width), n_bins - 1)
        bins[idx].append((conf, hit))

    ece, mce, bin_details = 0.0, 0.0, []
    for i, b in enumerate(bins):
        lo, hi = i * bin_width, (i + 1) * bin_width
        if not b:
            bin_details.append({"range": f"{lo:.0f}-{hi:.0f}", "count": 0,
                                 "avg_confidence": None, "accuracy": None, "gap": None})
            continue
        avg_conf = sum(c for c, _ in b) / len(b) / 100
        accuracy = sum(h for _, h in b) / len(b)
        gap = abs(avg_conf - accuracy)
        weight = len(b) / total_n
        ece += weight * gap
        mce = max(mce, gap)
        bin_details.append({"range": f"{lo:.0f}-{hi:.0f}", "count": len(b),
                             "avg_confidence": round(avg_conf, 4), "accuracy": round(accuracy, 4),
                             "gap": round(gap, 4)})

    return {
        "n_bins": n_bins, "sample_count": total_n, "neutral_excluded": neutral_count,
        "ece": round(ece, 4), "mce": round(mce, 4), "bins": bin_details, "verdict": None,
    }


def calibration_report(records, n_bins=DEFAULT_ECE_BINS):
    """§2.1 "고확신군 승률 > 저확신군 승률" 조건 + 통계적 유의성(Fisher's exact) +
    ECE/MCE를 window별로 계산."""
    report = {}
    for window in WINDOWS:
        eligible = eligible_records(records, window)
        high = [r for r in eligible
                if r.get("confidence") is not None and r["confidence"] >= HIGH_CONFIDENCE_THRESHOLD]
        low = [r for r in eligible
               if r.get("confidence") is not None and r["confidence"] < HIGH_CONFIDENCE_THRESHOLD]

        high_stats = win_rate_for(high, window)
        low_stats = win_rate_for(low, window)

        if high_stats["win_rate_pct"] is None or low_stats["win_rate_pct"] is None:
            calibration_holds = None  # 판단 보류 - 표본 부족
        else:
            calibration_holds = high_stats["win_rate_pct"] > low_stats["win_rate_pct"]

        report[window] = {
            "eligible_total": len(eligible),
            "high_confidence": high_stats,
            "low_confidence": low_stats,
            "calibration_holds": calibration_holds,
            "significance": significance_test(high_stats, low_stats),
            "ece_mce": compute_ece_mce(records, window, n_bins),
        }
    return report


def main():
    parser = argparse.ArgumentParser(description="뉴스 이벤트 캘리브레이션 분석 (읽기 전용)")
    parser.add_argument("--bins", type=int, default=DEFAULT_ECE_BINS,
                         help=f"ECE/MCE 계산용 confidence 구간 개수 (기본 {DEFAULT_ECE_BINS})")
    parser.add_argument("--self-test", action="store_true",
                         help="실제 로그 파일 대신 더미 데이터로 모듈 자체 검증만 하고 종료")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return None

    with open(NEWS_LOG_FILE, encoding="utf-8") as f:
        log = json.load(f)
    records = log.get("records", [])
    report = calibration_report(records, args.bins)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


# ---------------------------------------------------------------------------
# Dummy data test — 실제 news_event_calibration_log.json은 절대 건드리지 않고,
# 메모리 안에서만 합성 레코드를 만들어 모듈이 올바르게 동작하는지 확인한다.
# `python3 news_event_calibration_analysis.py --self-test`로 바로 실행 가능.
# ---------------------------------------------------------------------------

def _make_dummy_record(idx, direction, confidence, return_pct):
    return {
        "id": f"DUMMY_{idx}", "market": "000000", "judged_at": "2000-01-01",
        "headlines": ["(더미 테스트 데이터)"], "event_type": "기타",
        "direction": direction, "confidence": confidence,
        "reasoning": "더미 테스트용", "price_at_judgment": 10000,
        "outcomes": {
            "d1": {"date": "2000-01-02", "price": 10000 * (1 + return_pct / 100), "return_pct": return_pct},
            "d5": {"date": None, "price": None, "return_pct": None},
            "d20": {"date": None, "price": None, "return_pct": None},
        },
    }


def _dummy_well_calibrated(n_per_bucket=30):
    """confidence 구간과 실제 적중률이 거의 일치하도록 만든 데이터 - ECE가 낮게
    나와야 정상."""
    import random
    rng = random.Random(42)
    records = []
    idx = 0
    for conf in (20, 40, 60, 80, 95):
        hit_prob = conf / 100
        for _ in range(n_per_bucket):
            hit = rng.random() < hit_prob
            direction = "호재"
            return_pct = rng.uniform(0.5, 5.0) if hit else -rng.uniform(0.5, 5.0)
            records.append(_make_dummy_record(idx, direction, conf, return_pct))
            idx += 1
    return records


def _dummy_overconfident(n=200):
    """confidence는 항상 90 이상인데 실제 적중률은 동전던지기(50%) 수준 -
    ECE/MCE가 크게 나와야 정상(과신 모델)."""
    import random
    rng = random.Random(7)
    records = []
    for i in range(n):
        hit = rng.random() < 0.5
        direction = "호재"
        return_pct = rng.uniform(0.5, 5.0) if hit else -rng.uniform(0.5, 5.0)
        records.append(_make_dummy_record(i, direction, rng.randint(90, 100), return_pct))
    return records


def _dummy_real_gap(n_per_group=30):
    """고확신군(90+) 승률 90%, 저확신군(50 근처) 승률 40%로 실제 차이가 있는
    데이터 - 유의성 검정에서 유의미(p<0.05)하게 나와야 정상."""
    import random
    rng = random.Random(1)
    records = []
    idx = 0
    for conf, hit_prob in ((95, 0.9), (55, 0.4)):
        for _ in range(n_per_group):
            hit = rng.random() < hit_prob
            direction = "호재"
            return_pct = rng.uniform(0.5, 5.0) if hit else -rng.uniform(0.5, 5.0)
            records.append(_make_dummy_record(idx, direction, conf, return_pct))
            idx += 1
    return records


def _dummy_no_gap(n_per_group=30):
    """고확신/저확신 두 그룹 다 승률 60% 근처로 실제 차이가 없는 데이터 -
    유의성 검정에서 보통 유의미하지 않게(p>=0.05) 나와야 정상(고정 시드라
    결정적)."""
    import random
    rng = random.Random(2)
    records = []
    idx = 0
    for conf in (95, 55):
        for _ in range(n_per_group):
            hit = rng.random() < 0.6
            direction = "호재"
            return_pct = rng.uniform(0.5, 5.0) if hit else -rng.uniform(0.5, 5.0)
            records.append(_make_dummy_record(idx, direction, conf, return_pct))
            idx += 1
    return records


def run_self_test():
    """더미 데이터로 ECE/MCE·유의성 검정·전체 리포트가 말이 되게 나오는지 확인.
    실제 로그 파일은 전혀 열지 않는다. 실패하면 AssertionError로 즉시 중단."""
    print("=== news_event_calibration_analysis.py 자체 검증 (더미 데이터) ===\n")

    # 1) 잘 보정된(well-calibrated) 데이터 -> ECE 낮아야 함
    report = calibration_report(_dummy_well_calibrated(), n_bins=5)
    ece = report["d1"]["ece_mce"]["ece"]
    print(f"[1] 잘 보정된 더미 데이터 ECE(5bins) = {ece}")
    assert ece is not None and ece < 0.15, f"잘 보정된 데이터인데 ECE가 너무 큼: {ece}"

    # 2) 과신(overconfident) 데이터 -> ECE/MCE 커야 함
    report = calibration_report(_dummy_overconfident(), n_bins=5)
    ece_over = report["d1"]["ece_mce"]["ece"]
    mce_over = report["d1"]["ece_mce"]["mce"]
    print(f"[2] 과신 더미 데이터 ECE={ece_over}, MCE={mce_over}")
    assert ece_over is not None and ece_over > 0.25, f"과신 데이터인데 ECE가 너무 작음: {ece_over}"
    assert mce_over is not None and mce_over >= ece_over, "MCE는 항상 ECE 이상이어야 함"

    # 3) 실제 승률 차이가 있는 데이터 -> 유의미(p<0.05)해야 함
    report = calibration_report(_dummy_real_gap())
    sig = report["d1"]["significance"]
    print(f"[3] 실제 차이 있는 더미 데이터: high={report['d1']['high_confidence']['win_rate_pct']}%, "
          f"low={report['d1']['low_confidence']['win_rate_pct']}%, p={sig['p_value']}, significant={sig['significant']}")
    assert sig["p_value"] is not None and sig["p_value"] < 0.05, f"실제 차이가 있는데 유의미하지 않게 나옴: p={sig['p_value']}"
    assert sig["significant"] is True
    assert report["d1"]["calibration_holds"] is True, "고확신군 승률이 더 높아야 하는데 아님"

    # 4) 실제 차이가 없는 데이터 -> 보통 유의미하지 않아야 함(고정 시드, 결정적)
    report = calibration_report(_dummy_no_gap())
    sig = report["d1"]["significance"]
    print(f"[4] 차이 없는 더미 데이터: high={report['d1']['high_confidence']['win_rate_pct']}%, "
          f"low={report['d1']['low_confidence']['win_rate_pct']}%, p={sig['p_value']}, significant={sig['significant']}")
    assert sig["significant"] is False, f"실제 차이가 없는데 유의미하다고 나옴: p={sig['p_value']}"

    # 5) 표본 부족 시 전부 판단 보류(None)로 나오는지
    tiny = _dummy_well_calibrated(n_per_bucket=1)  # 버킷당 1건 -> 표본 부족
    report = calibration_report(tiny)
    hc = report["d1"]["high_confidence"]
    sig = report["d1"]["significance"]
    ece_mce = report["d1"]["ece_mce"]
    print(f"[5] 표본 부족 데이터: win_rate_pct={hc['win_rate_pct']}, "
          f"significance.p_value={sig['p_value']}, ece={ece_mce['ece']}")
    assert hc["win_rate_pct"] is None and hc["verdict"] is not None
    assert sig["p_value"] is None and sig["verdict"] is not None

    # 6) bin 개수(n_bins) 파라미터가 실제로 반영되는지
    r10 = calibration_report(_dummy_well_calibrated(), n_bins=10)["d1"]["ece_mce"]
    r4 = calibration_report(_dummy_well_calibrated(), n_bins=4)["d1"]["ece_mce"]
    print(f"[6] n_bins=10 -> {len(r10['bins'])}개 구간, n_bins=4 -> {len(r4['bins'])}개 구간")
    assert len(r10["bins"]) == 10 and len(r4["bins"]) == 4

    # 7) 실제 로그 파일을 열지 않았는지(read-only 원칙) - 이 프로세스 안에서
    #    NEWS_LOG_FILE을 open()한 적이 없다는 걸 별도로 보장할 순 없지만,
    #    위 모든 테스트가 인메모리 더미 레코드만 사용했다는 사실 자체가 보장.
    print("\n모든 더미 데이터 테스트 통과 - 실제 news_event_calibration_log.json은 열지 않았음.")


if __name__ == "__main__":
    main()
