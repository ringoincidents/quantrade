"""토스증권 Open API 조회 엔드포인트 검증 전용 (2026-08-09, 방향성 세션 지시).

**GET /api/v1/orders, GET /api/v1/sellable-quantity 두 개만 확인한다.** 목적은
`토스_주문API_스펙조사_2026-08-05.md`(제3자 미러 기반이라 1급 소스 확인이 아니라고
이미 명시된 문서)의 스키마가 실제 운영 계좌 응답과 맞는지 대조하는 것뿐이다.

**주문 실행 관련 코드는 이 파일에 없고, 만들지 않는다** — `place_sell_order()`나
`execute()`를 이 스크립트가 호출하거나 참조하는 일은 없다. 이 스크립트가 성공한다고
해서 실주문 구현으로 넘어갈 근거가 되지 않는다(방향성 세션 지시 4번 — 조회단계 문제
없다고 실주문 구현으로 넘어가지 말 것).

`real_portfolio_sync.py`의 인증/프록시 함수를 그대로 재사용한다(그 파일을 수정하지
않고 import만 함) — account header 조립 방식이 갈라지면 안 된다는 원칙을 그대로 따른다.

**출력 원칙**: 이 저장소는 Public이다. `real_portfolio_sync.py`와 동일하게
accountSeq/계좌번호 등 식별정보는 어떤 형태로도 print하지 않는다(요청 헤더 구성에만
메모리 상으로 쓰고 버림). 두 응답 스키마(Order, SellableQuantityResponse) 모두 계좌
식별자 필드를 포함하지 않는 것으로 스펙에서 확인됐지만, 혹시 모를 유출 방지를 위해
Order는 화이트리스트로만 출력한다. 이 스크립트는 아무 파일도 커밋하지 않는다 — 결과는
GitHub Actions 잡 로그로만 확인한다(상태 파일 신설 없음).
"""
import json

from real_portfolio_sync import (
    TossApiError,
    _get_result,
    check_proxy_ip,
    get_access_token,
)

ORDER_FIELD_WHITELIST = {
    "orderId", "symbol", "side", "orderType", "status", "quantity",
    "currency", "orderedAt", "timeInForce", "price", "orderAmount",
}


def probe_orders(token, account_seq):
    """GET /api/v1/orders?status=OPEN — 스펙상 status 파라미터 필수(OPEN|CLOSED)."""
    try:
        result = _get_result(
            "/api/v1/orders", token, account_seq=account_seq, params={"status": "OPEN"}
        )
    except TossApiError as e:
        print(f"[orders] 호출 실패: {e}")
        return {"ok": False, "error": str(e)}

    if "orders" not in result:
        print(f"[orders] 응답에 'orders' 키 없음 — 스펙과 불일치. 실제 키: {sorted(result.keys())}")
        return {"ok": False, "error": "orders 키 없음", "keys_seen": sorted(result.keys())}

    orders = result["orders"]
    print(f"[orders] 200 OK — status=OPEN, {len(orders)}건, hasNext={result.get('hasNext')}")
    for o in orders[:3]:
        print("  ", {k: v for k, v in o.items() if k in ORDER_FIELD_WHITELIST})

    unexpected_keys = set()
    for o in orders:
        unexpected_keys |= set(o.keys()) - ORDER_FIELD_WHITELIST
    if unexpected_keys:
        print(f"[orders] 스펙 화이트리스트에 없는 필드 발견(대조 필요, 값은 미출력): {sorted(unexpected_keys)}")

    return {"ok": True, "count": len(orders), "has_next": result.get("hasNext"),
            "unexpected_keys": sorted(unexpected_keys)}


def probe_sellable_quantity(token, account_seq, symbol):
    """GET /api/v1/sellable-quantity?symbol=... — 심볼 하나 지정 필요."""
    try:
        result = _get_result(
            "/api/v1/sellable-quantity", token, account_seq=account_seq, params={"symbol": symbol}
        )
    except TossApiError as e:
        print(f"[sellable-quantity] 호출 실패 (symbol={symbol}): {e}")
        return {"ok": False, "error": str(e)}

    print(f"[sellable-quantity] 200 OK — symbol={symbol}, {result}")
    if "sellableQuantity" not in result:
        print(f"[sellable-quantity] 응답에 'sellableQuantity' 키 없음 — 스펙과 불일치. 실제 키: {sorted(result.keys())}")
        return {"ok": False, "error": "sellableQuantity 키 없음", "keys_seen": sorted(result.keys())}

    return {"ok": True, "keys_seen": sorted(result.keys())}


def main():
    check_proxy_ip(expected_ip="141.164.41.178")
    token = get_access_token()

    accounts = _get_result("/api/v1/accounts", token)
    if not accounts:
        print("계좌 없음 — 검증 불가")
        return
    account_seq = accounts[0]["accountSeq"]  # 메모리에서만 사용, 출력하지 않음

    orders_result = probe_orders(token, account_seq)

    from analyze_lib import load_json
    real = load_json("real_portfolio.json", {"positions": []})
    positions = real.get("positions", [])
    if positions:
        symbol = positions[0]["symbol"]
        sq_result = probe_sellable_quantity(token, account_seq, symbol)
    else:
        print("[sellable-quantity] real_portfolio.json에 보유종목 없음 — 스킵")
        sq_result = {"ok": None, "note": "보유종목 없음"}

    print("\n=== 요약 (스펙 문서 대조용) ===")
    print(json.dumps({"orders": orders_result, "sellable_quantity": sq_result},
                      ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
