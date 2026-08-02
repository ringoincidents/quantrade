"""Phase 2 과거 뉴스 백테스트 트랙 (2026-08-02, Phase2_과거뉴스백테스트_설계.md 구현).

**실시간 트랙(news_event_experiment.py)과 병행하는 별도 트랙이다.** 실시간 트랙은
매일 표본을 쌓느라 최초 코호트 D+20이 2026-08-21이지만, 과거(2026-02~07) 뉴스는
결과가 이미 나와 있어 즉시 대조할 수 있다 — 캘리브레이션 판정을 앞당기기 위한
가속 트랙.

**건드리지 않는 것**: 실시간 트랙 파일(news_event_calibration_log.json), 매매 로직
(analyze.py/analyze_lib.py/ask_claude_decision), 5개 상태 파일. 이 스크립트는
자기 데이터셋(BACKTEST_LOG_FILE)만 읽고 쓴다.

**선정 기준은 Phase2_과거뉴스백테스트_설계.md에서 수집 전에 사전 고정했다** —
아래 상수가 그 기준이고, 실행에 실제로 쓰인 값은 데이터셋의 selection_criteria
블록에 기록돼 사후 대조가 가능하다. 결과(수익률/방향)를 보고 표본을 거르는 조건은
하나도 없다.

**룩어헤드 3중 차단**(설계 문서 §3):
  1. 판단 함수에 도구를 주지 않는다 — news_event_experiment.ask_news_event_judgment를
     그대로 import해서 쓴다(tools 파라미터 없음, 프롬프트/모델도 실시간 트랙과 동일해야
     두 트랙 비교가 성립한다).
  2. RSS 응답의 pubDate를 직접 파싱해 판단 창 밖 기사를 전부 버린다 — Google의
     after:/before: 연산자가 동작한다고 신뢰하지 않는다. 필터가 무시돼도 오염된
     데이터가 쌓이는 대신 표본이 0건에 수렴한다(안전한 실패).
  3. 프롬프트에 가격·결과는 물론 "과거 데이터"라는 사실 자체도 넣지 않는다.

**해결 못 하는 한계**: 판단 모델이 이 기간을 학습했다면 헤드라인만으로도 결말을
"기억"할 수 있다(설계 문서 §4-1). 도구 차단으로 막을 수 없는 문제라, 이 트랙 결과
하나만으로 §2.1 게이트 통과를 선언하지 않는다.
"""
import argparse
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from analyze_lib import get_krx_candles, load_json, save_json
from backtest import KRX_MARKET_CAP_TOP
from news_event_experiment import JUDGE_MODEL, OUTCOME_WINDOWS, ask_news_event_judgment

BACKTEST_LOG_FILE = "news_event_backtest_log.json"

# --- 사전 고정 선정 기준 (Phase2_과거뉴스백테스트_설계.md §2, 수집 전 확정) ---------
# 결과를 보고 사후에 바꾸지 않는다. CLI로 덮어쓸 수는 있지만 실제 사용값이
# 데이터셋에 기록되므로 기준을 바꿔 돌린 사실이 파일에 그대로 남는다.
WINDOW_START = "2026-02-01"
WINDOW_END = "2026-07-31"
JUDGMENT_DATE_STRIDE = 5      # 거래일 5일마다 = 주 1회 꼴
HEADLINE_LOOKBACK_DAYS = 3    # 판단일 직전 3일 기사만
CALENDAR_TICKER = "005930"    # 거래일 달력 기준 종목(최대 유동성 = 거래정지로 인한 결측 없음)
CALENDAR_CANDLE_COUNT = 400   # 약 1.6년치 — 2026-02 커버에 충분

KST = timezone(timedelta(hours=9))
RSS_SLEEP = 0.2               # 실시간 트랙 UNIVERSE_SLEEP과 같은 취지(Google News RSS 유예)

# 수집 과정 계기판. pubdate_rejected는 특히 중요 — 0이면 날짜 필터가 아예 안 걸린
# 건지 의심해봐야 하고(설계 §3-2), 지나치게 높으면 해당 기간 기사가 원래 적었다는 뜻.
STATS_KEYS = ("pubdate_rejected", "no_headlines", "judge_failed", "no_price", "fetch_failed")


def _rss_url(market, start_date, end_date):
    """종목코드 + 발행일 범위로 제한한 Google News RSS 검색 URL.
    after:/before:는 경계 포함이 애매해서 넉넉히 잡고, 실제 경계 판정은
    _within_window()의 pubDate 검증이 담당한다(설계 §3-2)."""
    query = f"{market}+after:{start_date}+before:{end_date}"
    return f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"


def _to_kst_date(pub_date_text):
    """RSS pubDate(RFC 822, 보통 GMT)를 KST 기준 날짜 문자열로. 파싱 실패는 None.

    GMT->KST 변환을 빼먹으면 하루씩 어긋난다 — 한국 기사는 대개 KST 오전에
    나오는데 그건 GMT로는 전날 밤이다."""
    try:
        pub_dt = parsedate_to_datetime(pub_date_text)
    except Exception:
        return None
    if pub_dt is None:
        return None
    if pub_dt.tzinfo is None:
        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
    return pub_dt.astimezone(KST).strftime("%Y-%m-%d")


def _within_window(pub_date_text, lookback_start, judgment_date):
    """판단 창(lookback_start ~ judgment_date) 안에서 발행된 기사인지.
    판단일 이후 기사를 하나라도 통과시키면 실험이 무효이므로, 파싱 실패는
    통과가 아니라 탈락으로 처리한다."""
    pub_day = _to_kst_date(pub_date_text)
    if pub_day is None:
        return False
    return lookback_start <= pub_day <= judgment_date


def fetch_historical_headlines(market, judgment_date, lookback_days=HEADLINE_LOOKBACK_DAYS, limit=5):
    """판단일 기준 직전 lookback_days일 이내 발행된 헤드라인만.

    반환: (headlines, rejected_count). 조회 자체가 실패하면 (None, 0) —
    실시간 트랙 get_news_headlines와 같이 "조회 실패"와 "뉴스 없음"을 구분한다.
    rejected_count는 날짜 창 밖이라 버린 기사 수로, after:/before:가 실제로
    먹히는지 사후 확인하는 계기판 역할을 한다."""
    judgment_dt = datetime.strptime(judgment_date, "%Y-%m-%d")
    lookback_start = (judgment_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    # before:는 배타적으로 동작하는 경우가 있어 하루 여유를 준다 — 어차피 아래에서
    # pubDate로 판단일까지만 남기므로 여유를 줘도 미래 기사가 통과하지 못한다.
    before = (judgment_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        resp = requests.get(_rss_url(market, lookback_start, before), timeout=15)
        root = ET.fromstring(resp.content)
    except Exception:
        return None, 0, []

    accepted, rejected_dates = [], []
    for item in root.findall(".//item"):
        title_el, date_el = item.find("title"), item.find("pubDate")
        if title_el is None or title_el.text is None:
            continue
        if date_el is None or date_el.text is None:
            rejected_dates.append("(pubDate 없음)")
            continue
        pub_day = _to_kst_date(date_el.text)
        if pub_day is None or not (lookback_start <= pub_day <= judgment_date):
            rejected_dates.append(pub_day or "(파싱 실패)")
            continue
        # 기사 제목과 KST 발행일을 짝지어 보관한다 — 판단일 창이 실제로 지켜졌는지
        # 나중에 데이터셋만 보고 사람이 대조할 수 있어야 하기 때문(설계 §3-2 감사용).
        accepted.append({"title": title_el.text, "pub_date_kst": pub_day})
    return accepted[:limit], len(rejected_dates), rejected_dates


def build_judgment_dates(window_start, window_end, stride, candles=None):
    """거래일 달력에서 window 안의 날짜를 stride 간격으로 뽑는다. 무작위 없음 —
    같은 입력이면 항상 같은 날짜 목록이라 선정에 개입할 여지가 없다."""
    if candles is None:
        candles = get_krx_candles(CALENDAR_TICKER, count=CALENDAR_CANDLE_COUNT)
    trading_days = sorted(c["date"] for c in candles if window_start <= c["date"] <= window_end)
    return trading_days[::stride]


def _close_on_or_after(candles_by_date, sorted_dates, target_date):
    """target_date 이후(포함) 첫 거래일의 종가. 아직 미래면 None.
    실시간 트랙이 "D+N일이 경과한 첫 실행일의 가격"을 쓰는 것과 같은 정의."""
    for d in sorted_dates:
        if d >= target_date:
            return d, candles_by_date[d]
    return None, None


def compute_outcomes(judgment_date, candles):
    """판단일 종가 대비 D+1/D+5/D+20 수익률. 과거 데이터라 즉시 계산 가능하다
    (실시간 트랙은 날짜가 도래해야 채울 수 있는 부분).

    반환: (price_at_judgment, outcomes) — 판단일에 그 종목이 거래되지 않았으면
    (None, None)으로 해당 (종목, 날짜) 쌍을 건너뛴다."""
    by_date = {c["date"]: c["close"] for c in candles}
    sorted_dates = sorted(by_date)
    if judgment_date not in by_date:
        return None, None

    baseline = by_date[judgment_date]
    judgment_dt = datetime.strptime(judgment_date, "%Y-%m-%d")
    outcomes = {}
    for key, days in OUTCOME_WINDOWS.items():
        target = (judgment_dt + timedelta(days=days)).strftime("%Y-%m-%d")
        date, price = _close_on_or_after(by_date, sorted_dates, target)
        if price is None:  # 아직 미도래(기간 말미) - 재실행하면 채워진다
            outcomes[key] = {"date": None, "price": None, "return_pct": None}
        else:
            outcomes[key] = {
                "date": date, "price": price,
                "return_pct": round((price - baseline) / baseline * 100, 3),
            }
    return baseline, outcomes


def _init_stats(log):
    """카운터를 키 단위로 채운다. log에 stats가 아예 없을 때뿐 아니라 빈 dict거나
    일부 키만 있을 때(이전 실행/스키마 변경분 이어받기)도 안전해야 한다 —
    dict 통째로 setdefault하면 이미 있는 빈 dict가 그대로 반환돼 카운터 키가
    안 생기고, 첫 += 에서 KeyError로 죽는다(2026-08-02 첫 Actions 실행에서
    실제로 이렇게 실패했다: run()이 기본값 {"stats": {}}로 로그를 만든 탓)."""
    stats = log.setdefault("stats", {})
    for key in STATS_KEYS:
        stats.setdefault(key, 0)
    return stats


def collect(log, judgment_dates, universe, lookback_days, limit=None, sleep=RSS_SLEEP):
    """판단일 오름차순 -> 유니버스 정의 순서로 전수 수집. 중단되더라도 남는 건
    '날짜 순 앞부분'이라 결과와 무관한 부분집합이다(설계 §2)."""
    existing = {r["id"] for r in log["records"]}
    stats = _init_stats(log)
    candle_cache = {}
    collected = 0

    for judgment_date in judgment_dates:
        for market in universe:
            if limit is not None and collected >= limit:
                print(f"\n--limit {limit} 도달 - 중단(날짜 순 앞부분까지 수집됨)")
                return collected
            if f"{market}_{judgment_date}" in existing:
                continue

            items, rejected, rejected_dates = fetch_historical_headlines(
                market, judgment_date, lookback_days)
            stats["pubdate_rejected"] += rejected
            # 무엇이 왜 걸러졌는지 표본으로 남긴다 — after:/before:가 무시되고 있다면
            # 여기에 판단일 한참 뒤 날짜들이 찍혀서 바로 드러난다.
            if rejected_dates and len(log.setdefault("rejected_samples", [])) < 40:
                log["rejected_samples"].append(
                    {"market": market, "judged_at": judgment_date,
                     "rejected_pub_dates": sorted(set(rejected_dates))[:8]})
            time.sleep(sleep)
            if items is None:
                stats["fetch_failed"] += 1
                continue
            if not items:
                stats["no_headlines"] += 1
                continue

            if market not in candle_cache:
                try:
                    candle_cache[market] = get_krx_candles(market, count=CALENDAR_CANDLE_COUNT)
                except Exception as e:
                    print(f"⚠️ {market}: 일봉 조회 실패 - 이 종목 전체 건너뜀 ({e})")
                    candle_cache[market] = []
            if not candle_cache[market]:
                stats["no_price"] += 1
                continue

            price, outcomes = compute_outcomes(judgment_date, candle_cache[market])
            if price is None:
                stats["no_price"] += 1
                continue

            headlines = [it["title"] for it in items]
            judgment = ask_news_event_judgment(market, headlines)
            if judgment is None:
                stats["judge_failed"] += 1
                print(f"⚠️ {market} {judgment_date}: 판단 파싱 실패 - 건너뜀")
                continue

            log["records"].append({
                "id": f"{market}_{judgment_date}",
                "track": "backtest",  # 실시간 트랙 레코드와 섞여도 구분되게(설계 §5)
                "market": market,
                "judged_at": judgment_date,
                "headlines": headlines,
                # 판단에 쓴 기사 각각의 KST 발행일 — 창이 지켜졌는지 데이터셋만 보고
                # 사람이 대조할 수 있어야 한다(실시간 트랙엔 없는, 회고 트랙 전용 감사 필드).
                "headline_dates": [it["pub_date_kst"] for it in items],
                "event_type": judgment.get("event_type", "기타"),
                "direction": judgment.get("direction", "중립"),
                "confidence": judgment.get("confidence"),
                "reasoning": judgment.get("reasoning", "-"),
                "price_at_judgment": price,
                "outcomes": outcomes,
            })
            collected += 1
            d20 = outcomes["d20"]["return_pct"]
            print(f"📰 {judgment_date} {market} [{judgment.get('event_type')}/"
                  f"{judgment.get('direction')}/{judgment.get('confidence')}] "
                  f"D+20={'미도래' if d20 is None else f'{d20:+.2f}%'}")
    return collected


def run(args):
    log = load_json(BACKTEST_LOG_FILE, {"records": [], "stats": {}})

    judgment_dates = build_judgment_dates(args.window_start, args.window_end, args.stride)
    print(f"판단일 {len(judgment_dates)}개 x 유니버스 {len(KRX_MARKET_CAP_TOP)}종목 "
          f"({args.window_start} ~ {args.window_end}, 거래일 {args.stride}일 간격)")

    # 실행에 실제로 쓰인 기준을 그대로 박아둔다 - 사전 고정 문서와 대조 가능하게.
    log["selection_criteria"] = {
        "window_start": args.window_start, "window_end": args.window_end,
        "judgment_date_stride": args.stride, "headline_lookback_days": args.lookback,
        "universe": "backtest.KRX_MARKET_CAP_TOP", "universe_size": len(KRX_MARKET_CAP_TOP),
        "selection_method": "전수(exhaustive) - 무작위 추출 아님, 결과 기반 필터 없음",
        "judgment_dates_count": len(judgment_dates),
        "defaults_used": (args.window_start == WINDOW_START and args.window_end == WINDOW_END
                          and args.stride == JUDGMENT_DATE_STRIDE
                          and args.lookback == HEADLINE_LOOKBACK_DAYS),
        "spec_document": "Phase2_과거뉴스백테스트_설계.md",
    }
    log["judge_model"] = JUDGE_MODEL  # 학습데이터 오염 한계(설계 §4-1) 해석에 필요
    log["track"] = "backtest"
    log["last_run_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    collected = collect(log, judgment_dates, KRX_MARKET_CAP_TOP, args.lookback, args.limit)
    save_json(BACKTEST_LOG_FILE, log)

    print(f"\n이번 실행 수집 {collected}건 / 누적 {len(log['records'])}건")
    print(f"통계: {log['stats']}")
    print("\n분석: python news_event_calibration_analysis.py "
          f"--log-file {BACKTEST_LOG_FILE}")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 2 과거 뉴스 백테스트 수집 (실시간 트랙과 별도 데이터셋)")
    parser.add_argument("--window-start", default=WINDOW_START)
    parser.add_argument("--window-end", default=WINDOW_END)
    parser.add_argument("--stride", type=int, default=JUDGMENT_DATE_STRIDE,
                        help=f"판단일 간격(거래일 기준, 기본 {JUDGMENT_DATE_STRIDE})")
    parser.add_argument("--lookback", type=int, default=HEADLINE_LOOKBACK_DAYS,
                        help=f"헤드라인 조회 창(일, 기본 {HEADLINE_LOOKBACK_DAYS})")
    parser.add_argument("--limit", type=int, default=None,
                        help="이번 실행에서 수집할 최대 건수(비용 조절용, 날짜 순 앞부분부터)")
    parser.add_argument("--self-test", action="store_true",
                        help="네트워크 없이 로직만 검증하고 종료")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return
    run(args)


# ---------------------------------------------------------------------------
# Self-test — 네트워크를 전혀 타지 않고 룩어헤드 차단/선정 로직만 검증한다.
# 이 설계·구현 환경에서는 news.google.com과 api.finance.naver.com이 정책상
# 차단(403)돼 실제 수집을 검증할 수 없었다 - 실제 동작 확인은 Actions 로그로.
# ---------------------------------------------------------------------------

def run_self_test():
    import inspect
    print("=== news_event_backtest.py 자체 검증 (네트워크 미사용) ===\n")

    # 1) pubDate 창 검증: 판단일 이후 기사는 반드시 탈락해야 한다(가장 중요한 방어)
    judgment, lookback_start = "2026-03-10", "2026-03-07"
    cases = [
        ("Mon, 09 Mar 2026 05:00:00 GMT", True, "창 안(판단일 하루 전)"),
        ("Tue, 10 Mar 2026 01:00:00 GMT", True, "창 안(판단일 당일 KST 오전)"),
        ("Tue, 10 Mar 2026 20:00:00 GMT", False, "판단일 GMT 밤 = KST 익일 -> 탈락"),
        ("Wed, 11 Mar 2026 05:00:00 GMT", False, "판단일 이후 -> 탈락(룩어헤드)"),
        ("Sat, 01 Aug 2026 05:00:00 GMT", False, "필터 무시된 최신 기사 -> 탈락"),
        ("Fri, 06 Mar 2026 05:00:00 GMT", False, "창보다 이전 -> 탈락"),
        ("not a date", False, "파싱 실패 -> 통과시키지 않음"),
    ]
    for text, expected, label in cases:
        got = _within_window(text, lookback_start, judgment)
        print(f"[1] {label}: {got}")
        assert got is expected, f"pubDate 창 판정 오류: {text} -> {got}, 기대 {expected}"

    # 2) 판단일 선정이 결정적이고 stride대로인지 (무작위 요소 없음)
    fake = [{"date": f"2026-02-{d:02d}"} for d in range(1, 29)]
    dates = build_judgment_dates("2026-02-01", "2026-02-28", 5, candles=fake)
    again = build_judgment_dates("2026-02-01", "2026-02-28", 5, candles=list(reversed(fake)))
    print(f"[2] 판단일 {len(dates)}개: {dates[:4]}... / 입력 순서 바꿔도 동일={dates == again}")
    assert dates == again, "입력 순서에 따라 선정이 달라지면 안 됨(결정적이어야 함)"
    assert dates[0] == "2026-02-01" and dates[1] == "2026-02-06", "stride 적용 오류"

    # 3) outcome 계산: T+N 이후 첫 거래일 종가, 미래면 None
    candles = [{"date": "2026-03-10", "close": 100.0}, {"date": "2026-03-11", "close": 110.0},
               {"date": "2026-03-16", "close": 90.0}]
    price, outcomes = compute_outcomes("2026-03-10", candles)
    print(f"[3] 기준가={price}, d1={outcomes['d1']['return_pct']}%, "
          f"d5={outcomes['d5']['return_pct']}%, d20={outcomes['d20']['return_pct']}")
    assert price == 100.0
    assert outcomes["d1"]["return_pct"] == 10.0, "D+1은 3/11 종가 110 -> +10%"
    assert outcomes["d5"]["return_pct"] == -10.0, "D+5(3/15) 이후 첫 거래일 3/16 종가 90 -> -10%"
    assert outcomes["d20"]["return_pct"] is None, "D+20은 미도래라 None이어야 함"
    assert compute_outcomes("2026-03-12", candles) == (None, None), "미거래일은 건너뛰어야 함"

    # 4) 판단 함수에 도구가 주어지지 않는지(지시사항 2) + 실시간 트랙과 동일 함수인지
    src = inspect.getsource(ask_news_event_judgment)
    print(f"[4] 판단 함수 출처={ask_news_event_judgment.__module__}, "
          f"모델={JUDGE_MODEL}, tools 파라미터 없음={'tools' not in src}")
    assert "tools" not in src, "판단 요청에 tools가 들어가면 룩어헤드 차단이 깨진다"
    assert ask_news_event_judgment.__module__ == "news_event_experiment", \
        "실시간 트랙과 같은 프롬프트/모델을 써야 두 트랙 비교가 성립한다"

    # 5) 데이터셋 분리: 실시간 트랙 파일명을 쓰지 않는지(설계 §5)
    print(f"[5] 백테스트 데이터셋={BACKTEST_LOG_FILE}")
    assert BACKTEST_LOG_FILE != "news_event_calibration_log.json", "두 트랙 파일이 같으면 안 됨"

    # 6) stats 카운터 초기화 - 첫 Actions 실행을 죽인 회귀(KeyError)를 막는 테스트.
    #    run()이 넘기는 빈 dict, 아무것도 없는 로그, 일부 키만 있는 로그 전부 커버.
    for label, log in [("빈 stats(run 기본값)", {"stats": {}}), ("stats 키 없음", {}),
                       ("일부 키만 존재", {"stats": {"pubdate_rejected": 7}})]:
        stats = _init_stats(log)
        for key in STATS_KEYS:
            stats[key] += 1  # 실제 수집 경로가 하는 것과 같은 연산
        print(f"[6] {label}: {stats}")
        assert all(k in stats for k in STATS_KEYS), f"{label}에서 카운터 키 누락"
    assert stats["pubdate_rejected"] == 8, "기존 카운트를 덮어쓰지 말고 이어받아야 함"

    # 7) KST 변환이 실제로 적용되는지 - 감사 필드(headline_dates)에 저장되는 값이라
    #    여기서 틀리면 사후 대조 자체가 무의미해진다.
    kst_cases = [
        ("Mon, 09 Mar 2026 05:00:00 GMT", "2026-03-09", "GMT 낮 -> 같은 날 KST"),
        ("Mon, 09 Mar 2026 20:00:00 GMT", "2026-03-10", "GMT 밤 -> KST 익일(+9h)"),
        ("Mon, 09 Mar 2026 23:30:00 +0900", "2026-03-09", "이미 KST면 그대로"),
        ("garbage", None, "파싱 실패는 None"),
    ]
    for text, expected, label in kst_cases:
        got = _to_kst_date(text)
        print(f"[7] {label}: {text!r} -> {got}")
        assert got == expected, f"KST 변환 오류: {text} -> {got}, 기대 {expected}"

    print("\n모든 자체 검증 통과 - 네트워크/실제 데이터셋 파일은 건드리지 않았음.")


if __name__ == "__main__":
    main()
