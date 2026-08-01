"""토스증권 실계좌 잔고 동기화 (초안, 조회 전용).

이 스크립트는 실계좌에 연결되는 첫 코드이므로 의도적으로 analyze_lib.py의
시뮬레이션 상태(portfolio.json 등)와 분리해뒀다 — 가상 포트폴리오와 실계좌를
같은 코드 경로에 섞으면 "분석 보조자이지 자동매매기가 아니다"라는 경계가
흐려지기 쉽다(CLAUDE.md).

토스 Open API는 실제로 존재하며(개발자센터: developers.tossinvest.com/docs,
신청: corp.tossinvest.com/ko/open-api) OAuth 2.0 인증을 사용한다는 것까지는
확인됐지만, 토큰 발급 엔드포인트 경로/파라미터와 잔고조회 엔드포인트의 정확한
스펙은 아직 확인되지 않았다(문서가 로그인 필요 — 계획서 v3 §3.4에서 다음 PC
세션에 확인 예정). 그 확인 전까지 get_access_token()/sync_portfolio()의 실제
호출부는 TODO로 남겨둔다 — 확인되지 않은 엔드포인트/파라미터를 지어내 채우지
않는다. 값은 전부 환경변수(GitHub Secrets)로만 주입한다.

이 스크립트는 잔고 "조회"만 한다. 주문 실행 로직은 포함하지 않는다.
"""
import json
import os
from datetime import datetime, timezone

import requests

PROXY_URL = os.environ.get("PROXY_URL", "")
proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

# developers.tossinvest.com/docs 확인 후 채울 값들. 코드에 하드코딩하지 않고
# GitHub Secrets -> 환경변수로만 주입한다.
TOSS_TOKEN_URL = os.environ.get("TOSS_TOKEN_URL", "")
TOSS_BALANCE_URL = os.environ.get("TOSS_BALANCE_URL", "")
TOSS_CLIENT_ID = os.environ.get("TOSS_CLIENT_ID", "")
TOSS_CLIENT_SECRET = os.environ.get("TOSS_CLIENT_SECRET", "")

REAL_PORTFOLIO_PATH = "real_portfolio.json"


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


def get_access_token():
    """OAuth 2.0 액세스 토큰 발급.

    토큰 엔드포인트 경로/grant_type/파라미터 형식이 developers.tossinvest.com/docs
    기준으로 확인되기 전까지는 미구현 — 잘못된 인증 파라미터를 지어내 실제 계좌에
    보내지 않기 위함.
    """
    if not (TOSS_TOKEN_URL and TOSS_CLIENT_ID and TOSS_CLIENT_SECRET):
        raise NotImplementedError(
            "토스 OAuth 토큰 엔드포인트가 아직 확인되지 않았습니다(계획서 v3 §3.4). "
            "TOSS_TOKEN_URL / TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 환경변수와 실제 "
            "인증 요청 로직을 developers.tossinvest.com/docs 기준으로 채운 뒤 사용하세요."
        )
    # TODO: 실제 OAuth 흐름(grant_type, 요청 바디/헤더 형식)을 문서 확인 후 구현.
    raise NotImplementedError("get_access_token() 구현이 아직 채워지지 않았습니다.")


def sync_portfolio():
    """토스증권 실계좌 잔고 조회. 엔드포인트가 확정되기 전까지는 미구현."""
    if not TOSS_BALANCE_URL:
        raise NotImplementedError(
            "토스 잔고조회 엔드포인트가 아직 확인되지 않았습니다(계획서 v3 §3.4). "
            "TOSS_BALANCE_URL 환경변수와 실제 잔고 조회 요청 로직을 채운 뒤 사용하세요."
        )
    access_token = get_access_token()
    try:
        resp = requests.get(
            TOSS_BALANCE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            proxies=proxies,
            timeout=10,
        )
    except requests.exceptions.ProxyError as e:
        raise ProxyConnectionError(f"프록시 서버(141.164.41.178:3128) 연결 실패: {e}") from e
    except requests.exceptions.RequestException as e:
        raise TossApiError(f"토스 API 요청 실패(네트워크): {e}") from e

    if resp.status_code != 200:
        raise TossApiError(f"토스 API 응답 오류 {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def save_real_portfolio(data):
    """조회 결과를 real_portfolio.json에 저장 (가상 portfolio.json과 분리 유지).

    data는 {"cash": int, "positions": [{"name", "quantity", "avg_price",
    "current_price", "eval_amount", "return_pct"}, ...]} 형태로 정규화되어
    있어야 한다 — 이 정규화는 sync_portfolio()가 실제 토스 응답 스키마를 확인한
    뒤 채워야 할 부분이다.
    """
    payload = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "cash": data.get("cash", 0),
        "positions": data.get("positions", []),
    }
    with open(REAL_PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def main():
    check_proxy_ip(expected_ip="141.164.41.178")
    try:
        data = sync_portfolio()
    except NotImplementedError as e:
        print(f"[대기] {e}")
        return
    save_real_portfolio(data)
    print(f"실계좌 잔고 저장 완료 → {REAL_PORTFOLIO_PATH}")


if __name__ == "__main__":
    main()
