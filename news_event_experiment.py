"""[Alpha Lab — 격리됨, v4.0 §15] Phase 2 뉴스 이벤트 추출 실험 스크립트 (2026-08-01, Phase2_뉴스이벤트추출_인수인계.md §2).

**analyze.py/ask_claude_decision과 분리된 독립 실험이다.** 이 스크립트는 어떤 매매도
실행하지 않고, portfolio.json 등 5개 상태 파일도 건드리지 않는다 — 자기 로그 파일
(NEWS_LOG_FILE)만 읽고 쓴다. daily.yml/poll.yml/backtest.yml과 커밋 레이스가 날 일이
없다.

매일 실행되며 두 단계를 순서대로 한다:
  1. 판단(judge): KRX 유니버스(backtest.KRX_MARKET_CAP_TOP, "[Phase 2 승인 유니버스]")를
     훑어 오늘 아직 판단 안 한 종목 중 관련 헤드라인이 있는 것만 Claude에게 사건유형/
     방향/확신도 판단을 물어 새 레코드로 남긴다.
  2. 결과 채우기(fill_outcomes): 이미 남아있는 레코드 중 D+1/D+5/D+20이 지났는데 아직
     안 채워진 시점을 오늘 가격으로 채운다.

과거 시점의 AI 판단은 재현할 수 없다(backtest.py와 같은 제약 — 비용·비결정성)는 이유로,
캘리브레이션은 전향적으로(prospectively) 기록 후 나중에 결과와 짝짓는 방식으로만
가능하다. 그래서 이 스크립트는 "한 번 돌려서 과거를 계산"하는 게 아니라 매일 조금씩
표본을 쌓아가는 방식이다.

[Alpha Lab 격리] Core(v3.2 활성 기능 — analyze.py/analyze_lib.py/news_event_cards.py 등)와
연결 없음. 재개 절차(v4.0 §15) 완료 전 통합 금지. 물리적 파일 이동 없이 이 태그로만
격리를 표시한다(옵션 B — 상세는 CLAUDE.md "Alpha Lab 격리" 절 참고).

예외(얕은 의존 1건, 제거하지 않고 사실만 기록): news_event_cards.py(Core, v3.2 활성
기능)가 이 파일의 JUDGE_MODEL 상수를 import한다 — 격리 대상인 이 파일에서 Core로
나가는 게 아니라, Core에서 이 파일로 들어오는 역방향 의존이다.
"""
import time
from datetime import datetime

from analyze_lib import (
    CLAUDE_API_KEY, get_news_headlines, get_krx_price,
    load_json, save_json, send_telegram,
)
from backtest import KRX_MARKET_CAP_TOP

import requests
import json

NEWS_LOG_FILE = "news_event_calibration_log.json"

OUTCOME_WINDOWS = {"d1": 1, "d5": 5, "d20": 20}
SAMPLE_SIZE_ALERT = 30
# 판단 모델을 상수로 뺀 이유(2026-08-02): 과거 뉴스 백테스트 트랙
# (news_event_backtest.py)이 이 파일의 ask_news_event_judgment를 그대로 import해
# 쓰는데, 두 트랙의 캘리브레이션을 비교하려면 프롬프트뿐 아니라 모델도 반드시
# 같아야 한다. 리터럴이 두 군데로 갈라지지 않게 단일 출처로 고정한다.
# 동작 변경은 없다 - 기존에 하드코딩돼 있던 값 그대로.
JUDGE_MODEL = "claude-sonnet-4-6"
UNIVERSE_SLEEP = 0.2  # 종목 사이 Google News RSS 유예 - crypto의 UPBIT_MARKET_SLEEP과 같은 취지


def ask_news_event_judgment(market, headlines):
    """뉴스 헤드라인 원문만 보고 사건유형/방향/확신도를 판단시킨다. 인수인계 문서
    §2-2 설계 그대로: 가격 지표는 이 프롬프트에 안 준다 — 뉴스 단독 예측력을 순수하게
    보기 위함. ask_claude_decision과는 별개 함수/별개 프롬프트로 분리해서, 이 실험이
    analyze_lib.py의 라이브 판단 경로와 절대 안 섞이게 한다.

    2026-08-02: 사건유형에 "지정학/거시"(전쟁, 금리, 환율, 공급망 등 종목 개별 이슈가
    아니라 시장 전체에 영향을 주는 거시 사건) 카테고리 추가 — 새 데이터소스 연결 없이
    기존 get_news_headlines 파이프라인 안에서 분류 라벨만 확장한 것. 이런 뉴스는
    실적발표/공시/M&A/규제 어디에도 안 맞아 기존엔 전부 "기타"로 뭉뚱그려졌었다."""
    headline_text = "\n".join(f"- {h}" for h in headlines)
    prompt_text = (
        "너는 한국 주식 뉴스 헤드라인만 보고 사건을 분류하고 판단하는 애널리스트야.\n"
        "가격 지표는 주지 않을 거야 - 오직 아래 헤드라인 원문만 보고 판단해.\n\n"
        f"[종목코드] {market}\n"
        f"[최근 헤드라인]\n{headline_text}\n\n"
        "다음 JSON 형식으로만 답해줘. 매우 중요한 규칙:\n"
        "- 다른 설명 텍스트 없이 순수 JSON만 출력\n"
        "- 모든 문자열 값은 반드시 큰따옴표로 감싸고, 문자열 안에는 줄바꿈이나 큰따옴표를 절대 넣지 마\n"
        "- reasoning은 한 줄로, 쉼표나 마침표로만 문장을 구분해\n\n"
        "{\n"
        '  "event_type": "실적발표 또는 공시 또는 M&A 또는 규제 또는 지정학/거시 또는 기타",\n'
        '  "direction": "호재 또는 악재 또는 중립",\n'
        '  "confidence": 0에서100사이정수,\n'
        '  "reasoning": "한 줄로 된 판단 근거"\n'
        "}"
    )

    for attempt in range(2):  # ask_claude_decision과 동일하게 실패 시 한 번 더 시도
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": JUDGE_MODEL, "max_tokens": 500, "messages": [{"role": "user", "content": prompt_text}]},
                timeout=30
            )
            data = response.json()
            if "content" not in data:
                return None
            raw_text = data["content"][0]["text"]
            cleaned = raw_text.strip().replace("```json", "").replace("```", "").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end + 1]
            return json.loads(cleaned)
        except Exception:
            if attempt == 0:
                continue
            return None
    return None


def judge_new_events(log, today):
    already_judged_today = {r["market"] for r in log["records"] if r["judged_at"] == today}

    for market in KRX_MARKET_CAP_TOP:
        if market in already_judged_today:
            continue

        headlines = get_news_headlines(market)
        time.sleep(UNIVERSE_SLEEP)
        if not headlines:  # None(조회 실패) 또는 []( 관련 뉴스 없음) 둘 다 판단할 사건이 없음
            continue

        judgment = ask_news_event_judgment(market, headlines)
        if judgment is None:
            print(f"⚠️ {market}: 판단 파싱 실패 - 건너뜀")
            continue

        try:
            price = get_krx_price(market)
        except Exception as e:
            print(f"⚠️ {market}: 판단시점 가격 조회 실패 - 건너뜀 ({e})")
            continue

        record = {
            "id": f"{market}_{today}",
            "market": market,
            "judged_at": today,
            "headlines": headlines,
            "event_type": judgment.get("event_type", "기타"),
            "direction": judgment.get("direction", "중립"),
            "confidence": judgment.get("confidence"),
            "reasoning": judgment.get("reasoning", "-"),
            "price_at_judgment": price,
            "outcomes": {k: {"date": None, "price": None, "return_pct": None} for k in OUTCOME_WINDOWS},
        }
        log["records"].append(record)
        print(f"📰 {market} [{record['event_type']}/{record['direction']}/{record['confidence']}] {record['reasoning']}")


def fill_outcomes(log, today_dt, today):
    for record in log["records"]:
        judged_dt = datetime.strptime(record["judged_at"], "%Y-%m-%d")
        days_elapsed = (today_dt - judged_dt).days

        for key, window in OUTCOME_WINDOWS.items():
            if days_elapsed < window or record["outcomes"][key]["date"] is not None:
                continue
            try:
                price = get_krx_price(record["market"])
                return_pct = (price - record["price_at_judgment"]) / record["price_at_judgment"] * 100
                record["outcomes"][key] = {
                    "date": today, "price": price, "return_pct": round(return_pct, 3),
                }
            except Exception as e:
                print(f"⚠️ {record['market']} {key} 결과 채우기 실패 - 다음 실행에 재시도 ({e})")


def maybe_notify_sample_size(log):
    """표본 30건 도달 시 1회만 텔레그램 알림 - 중간 점검 시점 신호일 뿐,
    자동 판정/게이트 적용은 하지 않는다(인수인계 문서 §결정사항 5)."""
    count = len(log["records"])
    if count >= SAMPLE_SIZE_ALERT and not log.get("notified_30"):
        send_telegram(
            f"📰 뉴스 이벤트 실험 표본 {count}건 도달 (기준 {SAMPLE_SIZE_ALERT}건)\n"
            "중간 점검 가능 시점 - 참고용 알림이며 자동 판정/게이트에는 반영되지 않습니다.\n"
            "판단 기록 30건 누적 — outcomes(D+1/5/20)는 아직 미확정, 캘리브레이션 분석은 "
            "최초 코호트 D+20 도달 후 가능합니다."
        )
        log["notified_30"] = True


def run():
    log = load_json(NEWS_LOG_FILE, {"records": [], "notified_30": False})
    today_dt = datetime.now()
    today = today_dt.strftime("%Y-%m-%d")

    judge_new_events(log, today)
    fill_outcomes(log, today_dt, today)
    maybe_notify_sample_size(log)

    save_json(NEWS_LOG_FILE, log)
    print(f"\n누적 판단 표본: {len(log['records'])}건")


if __name__ == "__main__":
    run()
