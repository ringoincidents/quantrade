"""뉴스 이벤트 캘리브레이션 분석 (Phase2_뉴스이벤트추출_인수인계.md §7 설계를 코드로 구현).

**읽기 전용 분석 스크립트다.** `news_event_experiment.py`(매일 판단을 기록하고
outcomes를 채우는 파이프라인)와 물리적으로 분리했다 — 이 파일은
`news_event_calibration_log.json`을 읽기만 하고 절대 쓰지 않는다. 계획서 v3.1
§2.1의 캘리브레이션 조건 "고확신군 승률 > 저확신군 승률"을 계산한다.

적중(hit) 정의: direction이 "호재"이고 해당 window의 return_pct > 0, 또는 "악재"이고
return_pct < 0이면 적중. "중립"은 무엇이 "맞았다"인지 모호하므로 승률 계산(hit/miss)
에서 제외하고 표본 수만 별도 집계한다 — 강제로 0/1 분류해 승률을 왜곡시키지 않기
위함.

고확신/저확신 분리: confidence >= HIGH_CONFIDENCE_THRESHOLD(70) 고정 임계값.
중앙값(median) 분리는 표본이 늘 때마다 경계선이 움직여서 같은 판단이 시점에 따라
고확신/저확신을 오갈 수 있어 비교가 불안정해진다 — 그래서 고정값을 쓴다. 다만
실제 confidence 분포와 맞는지는 표본이 쌓인 뒤 재검토가 필요할 수 있다.

window(d1/d5/d20)는 독립적으로 계산한다 — 단기 반응과 중장기 반응이 다를 수 있어
하나로 합치지 않는다.

표본 부족 처리: 버킷(고확신/저확신 × window)당 표본이 MIN_BUCKET_SAMPLES 미만이면
승률 숫자를 내지 않고 "판단 보류"로 명시한다 — backtest.py의 SUCCESS_CRITERIA와
같은 취지(근거 없는 숫자로 성급한 결론을 내지 않기 위함).

2026-08-21(최초 코호트 D+20 도달) 전까지는 outcomes가 전부 null이라 이 스크립트를
실행해도 모든 window가 "판단 보류"로만 나온다 — 그게 정상이다. 실제 outcomes가
채워지면 이 파일을 그대로 실행하면 된다.
"""
import json

NEWS_LOG_FILE = "news_event_calibration_log.json"
HIGH_CONFIDENCE_THRESHOLD = 70
MIN_BUCKET_SAMPLES = 10
WINDOWS = ("d1", "d5", "d20")


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


def win_rate_for(records, window):
    """중립 제외 hit/(hit+miss) 비율. 표본 부족이면 win_rate_pct=None + verdict 사유."""
    scored = []
    neutral_count = 0
    for r in records:
        return_pct = r["outcomes"][window]["return_pct"]
        result = classify_hit(r.get("direction"), return_pct)
        if result == "neutral":
            neutral_count += 1
            continue
        scored.append(1 if result == "hit" else 0)

    if len(scored) < MIN_BUCKET_SAMPLES:
        return {
            "sample_count": len(scored),
            "neutral_excluded": neutral_count,
            "win_rate_pct": None,
            "verdict": f"표본 부족({len(scored)}건 < 최소 {MIN_BUCKET_SAMPLES}건) - 판단 보류",
        }
    win_rate = sum(scored) / len(scored) * 100
    return {
        "sample_count": len(scored),
        "neutral_excluded": neutral_count,
        "win_rate_pct": round(win_rate, 2),
        "verdict": None,
    }


def calibration_report(records):
    """§2.1 "고확신군 승률 > 저확신군 승률" 조건을 window별로 계산."""
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
        }
    return report


def main():
    with open(NEWS_LOG_FILE, encoding="utf-8") as f:
        log = json.load(f)
    records = log.get("records", [])
    report = calibration_report(records)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    main()
