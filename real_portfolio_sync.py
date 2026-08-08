"""토스증권 실계좌 잔고 동기화 (조회 전용).

이 스크립트는 실계좌에 연결되는 첫 코드이므로 의도적으로 analyze_lib.py의
시뮬레이션 상태(portfolio.json 등)와 분리해뒀다 — 가상 포트폴리오와 실계좌를
같은 코드 경로에 섞으면 "분석 보조자이지 자동매매기가 아니다"라는 경계가
흐려지기 쉽다(CLAUDE.md).

엔드포인트/스키마는 토스증권 공식 Open API 명세(2026-08-01 확인, OpenAPI
3.1.0, version 1.2.5, https://openapi.tossinvest.com)를 기준으로 구현했다.
OAuth 2.0 Client Credentials Grant로 토큰을 발급받고(`POST /oauth2/token`),
계좌 목록(`GET /api/v1/accounts`) → 보유종목(`GET /api/v1/holdings`) →
매수가능금액(`GET /api/v1/buying-power`) 순으로 조회한다. USD 보유분은
원화 환산을 위해 `GET /api/v1/exchange-rate`로 환율을 함께 조회한다.

이 스크립트는 잔고 "조회"만 한다. 주문 실행 로직은 포함하지 않는다(CLAUDE.md
원칙 — 조회 전용 단계에서 매수/매도 주문 함수는 만들지 않는다).
"""
import json
import os
from datetime import datetime, timedelta, timezone

import requests

PROXY_URL = os.environ.get("PROXY_URL", "")
proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

# client_id/client_secret은 계정별 발급값이므로 GitHub Secrets로만 주입한다.
# 엔드포인트 자체는 공식 스펙으로 확인됐으므로 코드에 고정한다.
TOSS_CLIENT_ID = os.environ.get("TOSS_CLIENT_ID", "")
TOSS_CLIENT_SECRET = os.environ.get("TOSS_CLIENT_SECRET", "")

TOSS_API_BASE = "https://openapi.tossinvest.com"

REAL_PORTFOLIO_PATH = "real_portfolio.json"

# 평가손익(자동 스냅샷) 트래킹. 2026-08-08 방향성 세션 결정(CLAUDE.md 참고):
# - 지표명은 "평가손익"(unrealized/valuation P&L)만 쓴다. 배당·이자·실현손익
#   근사치는 채우지 않는다 — 토스 Open API에 해당 조회 엔드포인트가 없어서
#   (`토스_주문API_스펙조사_2026-08-05.md` §2.1) 정확히 계산할 수 없기 때문에,
#   빈 칸을 틀린 숫자로 채우기보다 아예 다른 지표로 이름을 분리했다.
# - historical_pnl_manual.json(2023-05-17~2026-08-08, "총손익" 정적 기록)과
#   겹치지 않도록 이 날짜 이전은 기록하지 않는다.
PNL_HISTORY_PATH = "portfolio_pnl_history.json"
PNL_HISTORY_START_DATE = "2026-08-09"
KST = timezone(timedelta(hours=9))


class ProxyConnectionError(Exception):
    """프록시 서버(Vultr, 141.164.41.178:3128) 자체에 연결할 수 없을 때."""


class TossApiError(Exception):
    """프록시 연결은 됐지만 토스 API 호출/응답이 실패했을 때."""


def check_proxy_ip(expected_ip=None):
    """프록시를 거쳐 나가는 실제 egress IP 확인.

    2026-08-01 기준 Vultr 프록시(141.164.41.178:3128) 경유 확인 완료. 토스 API가
    IP 화이트리스트 기반이라 프록시 자체가 죽거나 자격증명이 바뀌면 원인을
    "프록시 문제"로 바로 좁힐 수 있도록, sync_portfolio() 실행 전 사전 점검으로
    계속 둔다.
    """
    resp = requests.get("https://api.ipify.org", proxies=proxies, timeout=10)
    actual_ip = resp.text.strip()
    print(f"프록시 경유 IP: {actual_ip}")
    if expected_ip:
        matched = actual_ip == expected_ip
        print(f"기대 IP({expected_ip}) 일치 여부: {matched}")
        return matched
    return actual_ip


def _request(method, path, token=None, account_seq=None, **kwargs):
    """공통 요청 래퍼. 프록시 실패와 토스 API 실패를 구분해서 올린다."""
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if account_seq is not None:
        headers["X-Tossinvest-Account"] = str(account_seq)
    try:
        resp = requests.request(
            method,
            f"{TOSS_API_BASE}{path}",
            headers=headers,
            proxies=proxies,
            timeout=10,
            **kwargs,
        )
    except requests.exceptions.ProxyError as e:
        raise ProxyConnectionError(f"프록시 서버(141.164.41.178:3128) 연결 실패: {e}") from e
    except requests.exceptions.RequestException as e:
        raise TossApiError(f"토스 API 요청 실패({path}): {e}") from e

    if resp.status_code != 200:
        raise TossApiError(f"토스 API 응답 오류 {path} {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def get_access_token():
    """OAuth 2.0 Client Credentials Grant로 액세스 토큰 발급 (POST /oauth2/token)."""
    if not (TOSS_CLIENT_ID and TOSS_CLIENT_SECRET):
        raise NotImplementedError(
            "TOSS_CLIENT_ID / TOSS_CLIENT_SECRET이 설정되지 않았습니다. "
            "GitHub Secrets에 등록한 뒤 사용하세요."
        )
    body = _request(
        "POST",
        "/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": TOSS_CLIENT_ID,
            "client_secret": TOSS_CLIENT_SECRET,
        },
    )
    return body["access_token"]


def _get_result(path, token, account_seq=None, params=None):
    """`{"result": ...}` envelope에서 result만 꺼낸다 (토큰 발급 API 제외 모든 API 공통)."""
    body = _request("GET", path, token=token, account_seq=account_seq, params=params)
    return body["result"]


def sync_portfolio():
    """토스증권 실계좌 잔고 조회 (계좌 → 보유종목 → 매수가능금액 → 환율 순)."""
    token = get_access_token()

    accounts = _get_result("/api/v1/accounts", token)
    if not accounts:
        raise TossApiError("토스 계좌가 없습니다 (GET /api/v1/accounts 응답이 빈 배열).")
    account_seq = accounts[0]["accountSeq"]

    holdings = _get_result("/api/v1/holdings", token, account_seq=account_seq)
    krw_buying_power = _get_result(
        "/api/v1/buying-power", token, account_seq=account_seq, params={"currency": "KRW"}
    )
    usd_buying_power = _get_result(
        "/api/v1/buying-power", token, account_seq=account_seq, params={"currency": "USD"}
    )

    try:
        rate = _get_result(
            "/api/v1/exchange-rate", token, params={"baseCurrency": "USD", "quoteCurrency": "KRW"}
        )
        usd_krw_rate = float(rate["rate"])
    except TossApiError:
        # 환율 조회 실패 시 USD 자산은 원화 합산에서 제외하고 계속 진행
        # (전체 동기화를 막을 정도는 아님 — 다음 실행에서 재시도됨).
        usd_krw_rate = 0.0

    krw_cash = float(krw_buying_power["cashBuyingPower"])
    usd_cash = float(usd_buying_power["cashBuyingPower"])
    total_cash_krw = krw_cash + usd_cash * usd_krw_rate

    positions = []
    for item in holdings.get("items", []):
        currency = item["currency"]
        eval_amount = float(item["marketValue"]["amount"])
        eval_amount_krw = eval_amount if currency == "KRW" else eval_amount * usd_krw_rate
        positions.append(
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "market_country": item["marketCountry"],
                "currency": currency,
                "quantity": item["quantity"],
                "avg_price": item["averagePurchasePrice"],
                "current_price": item["lastPrice"],
                "eval_amount": eval_amount,
                "eval_amount_krw": eval_amount_krw,
                "return_pct": float(item["profitLoss"]["rate"]) * 100,
            }
        )

    return {"cash": total_cash_krw, "positions": positions}


def save_real_portfolio(data):
    """조회 결과를 real_portfolio.json에 저장 (가상 portfolio.json과 분리 유지).

    data는 {"cash": 원화 환산 총 현금, "positions": [{"symbol", "name",
    "market_country", "currency", "quantity", "avg_price", "current_price",
    "eval_amount"(원종목통화), "eval_amount_krw"(원화환산), "return_pct"}, ...]}
    형태 — sync_portfolio()가 이 형태로 정규화해서 반환한다.
    """
    payload = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "cash": data.get("cash", 0),
        "positions": data.get("positions", []),
    }
    with open(REAL_PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def _load_pnl_history():
    if os.path.exists(PNL_HISTORY_PATH):
        with open(PNL_HISTORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "metric": "평가손익",
        "metric_label_en": "unrealized/valuation P&L",
        "metric_note": (
            "배당·이자·실현손익 근사치를 포함하지 않는다 — '총손익'이 아니다. "
            "토스 Open API에 배당/이자 조회 엔드포인트가 없어 정확히 계산할 수 "
            "없기 때문에 빈 칸을 틀린 숫자로 채우지 않고 지표 자체를 분리했다 "
            "(토스_주문API_스펙조사_2026-08-05.md §2.1). "
            "historical_pnl_manual.json(2023-05-17~2026-08-08, '총손익' 정적 기록)과 "
            "다른 지표이므로 이어붙여 그릴 때 반드시 구분 표시할 것."
        ),
        "formula": (
            "valuation_pnl_krw = eval_amount_krw(당일) - baseline.eval_amount_krw "
            "- sum(manual_net_flows[].amount_krw, baseline.date 이후)"
        ),
        "start_date": PNL_HISTORY_START_DATE,
        "baseline": None,
        "manual_net_flows": [],
        "records": [],
    }


def update_pnl_history(data, today=None):
    """실계좌 총 평가금액을 하루 1개 스냅샷으로 portfolio_pnl_history.json에 반영.

    출금/입금(순입출금액)은 토스 Open API에 조회 엔드포인트가 없어 자동으로
    알 수 없다 — `manual_net_flows`에 사용자가 직접 채워 넣는 값만 반영한다
    (기본 0). 이 한계는 CLAUDE.md와 metric_note에 명시돼 있다.
    """
    today = today or datetime.now(KST).strftime("%Y-%m-%d")
    if today < PNL_HISTORY_START_DATE:
        print(f"[평가손익 스냅샷 건너뜀] {today} < 시작일 {PNL_HISTORY_START_DATE}")
        return None

    history = _load_pnl_history()
    total_eval_krw = data.get("cash", 0) + sum(
        p.get("eval_amount_krw", 0) for p in data.get("positions", [])
    )

    if history["baseline"] is None:
        history["baseline"] = {"date": today, "eval_amount_krw": total_eval_krw}

    net_flow_krw = sum(
        f["amount_krw"]
        for f in history["manual_net_flows"]
        if history["baseline"]["date"] <= f["date"] <= today
    )
    valuation_pnl_krw = total_eval_krw - history["baseline"]["eval_amount_krw"] - net_flow_krw

    record = {
        "date": today,
        "eval_amount_krw": total_eval_krw,
        "net_flow_since_baseline_krw": net_flow_krw,
        "valuation_pnl_krw": valuation_pnl_krw,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    # 하루 여러 번 도는 스케줄(sync_real.yml 4x/일)이므로 같은 날짜는 최신값으로 덮어쓴다.
    history["records"] = [r for r in history["records"] if r["date"] != today] + [record]

    with open(PNL_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return history


def main():
    check_proxy_ip(expected_ip="141.164.41.178")
    try:
        data = sync_portfolio()
    except NotImplementedError as e:
        print(f"[대기] {e}")
        return
    save_real_portfolio(data)
    print(f"실계좌 잔고 저장 완료 → {REAL_PORTFOLIO_PATH}")
    update_pnl_history(data)


if __name__ == "__main__":
    main()
