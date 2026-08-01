"""토스증권 실계좌 잔고 동기화 (초안, 조회 전용).

이 스크립트는 실계좌에 연결되는 첫 코드이므로 의도적으로 analyze_lib.py의
시뮬레이션 상태(portfolio.json 등)와 분리해뒀다 — 가상 포트폴리오와 실계좌를
같은 코드 경로에 섞으면 "분석 보조자이지 자동매매기가 아니다"라는 경계가
흐려지기 쉽다(CLAUDE.md).

토스 Open API의 실제 엔드포인트/인증 방식은 아직 확인되지 않았다(계획서 v3
§3.4: 권한 범위, IP 제한, 모의투자 여부, Rate Limit을 다음 PC 세션에서 확인
예정). 그 확인 전까지 sync_portfolio()의 실제 호출부는 TODO로 남겨둔다 —
확인되지 않은 엔드포인트를 지어내 채우지 않는다.

이 스크립트는 잔고 "조회"만 한다. 주문 실행 로직은 포함하지 않는다.
"""
import os
import requests

PROXY_URL = os.environ.get("PROXY_URL", "")
proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

TOSS_API_BASE_URL = os.environ.get("TOSS_API_BASE_URL", "")  # 계획서 §3.4 확인 후 채울 것
TOSS_API_KEY = os.environ.get("TOSS_API_KEY", "")


def check_proxy_ip(expected_ip=None):
    """[임시 테스트용 - 검증 끝나면 제거 예정] 프록시를 거쳐 나가는 실제 egress IP 확인."""
    resp = requests.get("https://api.ipify.org", proxies=proxies, timeout=10)
    actual_ip = resp.text.strip()
    print(f"프록시 경유 IP: {actual_ip}")
    if expected_ip:
        matched = actual_ip == expected_ip
        print(f"기대 IP({expected_ip}) 일치 여부: {matched}")
        return matched
    return actual_ip


def sync_portfolio():
    """토스증권 실계좌 잔고 조회. 엔드포인트/인증 방식이 확정되기 전까지는 미구현."""
    if not TOSS_API_BASE_URL:
        raise NotImplementedError(
            "토스 API 엔드포인트가 아직 확인되지 않았습니다(계획서 v3 §3.4). "
            "TOSS_API_BASE_URL 환경변수와 실제 잔고 조회 요청 로직을 채운 뒤 사용하세요."
        )
    resp = requests.get(
        TOSS_API_BASE_URL,  # TODO: 실제 잔고 조회 엔드포인트 경로로 교체
        headers={"Authorization": f"Bearer {TOSS_API_KEY}"},
        proxies=proxies,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    check_proxy_ip(expected_ip="141.164.41.178")
