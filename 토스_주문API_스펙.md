# 토스증권 Open API — 주문 계층 스펙 정리 (2026-08-08 확보)

이 문서는 `autoexec.place_sell_order()`가 **미구현으로 남아 있던 이유였던 다섯 가지
미확보 항목**이 전부 채워졌음을 기록한다. 출처는 사용자가 세션에 붙여넣은 토스증권
Open API OpenAPI 3.1.0 스펙(version 1.2.13, 서버 `https://openapi.tossinvest.com`)이다.

**이 문서는 스펙 기록일 뿐이며, 이 저장소에는 여전히 주문을 넣는 코드가 없다.**
구현 여부·시점은 아래 §7 참조.

---

## 1. 왜 이 문서가 필요한가

`autoexec.py`의 `place_sell_order()`는 다음 다섯 가지를 몰라서 구현되지 않았다:

1. 주문 생성 엔드포인트 경로와 HTTP 메서드
2. 요청 본문 필드명과 타입
3. 응답 스키마와 주문 식별자 필드
4. 멱등키 지원 여부
5. 에러 코드 목록

필드명을 추측하면 조용히 400을 받거나 **더 나쁘게는 다른 뜻으로 해석된 주문이 나갈 수
있다**는 것이 미구현으로 둔 이유였다. 이제 다섯 항목 모두 스펙에서 확인된다.

또한 이 샌드박스에서는 `developers.tossinvest.com`과 `openapi.tossinvest.com`이
네트워크 정책상 차단(`CONNECT tunnel failed, response 403`)돼 있어 문서를 직접 읽거나
API를 호출해볼 수 없다. 그래서 스펙을 저장소 안에 남긴다 — 세션이 끝나도 남도록.

## 2. 인증 (기존 코드 그대로 재사용 가능)

`real_portfolio_sync.py`가 이미 쓰는 방식과 동일하다. 새로 만들 것이 없다.

| 항목 | 값 |
|---|---|
| 토큰 발급 | `POST /oauth2/token`, `grant_type=client_credentials` |
| 인증 헤더 | `Authorization: Bearer {access_token}` |
| 계좌 헤더 | `X-Tossinvest-Account: {accountSeq}` (정수) |
| 응답 봉투 | 토큰 발급 제외 전 API가 `{"result": ...}` |

`real_portfolio_sync._request()` / `_get_result()`가 위 세 가지를 이미 처리한다.
`accountSeq`는 메모리에만 존재하고 `real_portfolio.json`에 절대 기록되지 않는다
(저장소가 공개이므로) — 주문 계층을 만들 때도 이 규칙은 그대로 유지해야 한다.

## 3. 주문 생성 — `POST /api/v1/orders`

`operationId: createOrder`, tag `Order`.

### 요청 본문 (`OrderCreateRequest`, 수량 기준 변형)

| 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|
| `symbol` | string | ✔ | 종목코드 |
| `side` | enum | ✔ | `BUY` \| `SELL` |
| `orderType` | enum | ✔ | `LIMIT` \| `MARKET` |
| `quantity` | string | ✔ | 소수 문자열, `^\d+(\.\d+)?$` |
| `price` | string | LIMIT만 | **MARKET이면 보내면 안 된다** |
| `timeInForce` | enum | | `DAY`(기본) \| `CLS` |
| `clientOrderId` | string | | 멱등키. 최대 36자, `^[a-zA-Z0-9\-_]+$`, **유효기간 10분** |
| `confirmHighValueOrder` | boolean | | 1억원 이상 주문은 `true` 필요 |

국내(KR) 제약:
- `quantity`는 **양의 정수**여야 한다. 소수 수량은 미국 `MARKET` `SELL`에서만 허용.
- `price`는 **호가단위(tick size)에 맞아야** 한다. 어긋나면 400 `invalidTickSize`.

### 응답

```json
{"result": {"orderId": "...", "clientOrderId": "..."}}
```

### 에러 코드

| HTTP | code | 의미 |
|---|---|---|
| 400 | `invalid-request` | 요청 형식 오류. `invalidTickSize`인 경우 `data.tickSize` / `data.nearestPrices` 동봉 |
| 400 | `confirm-high-value-required` | 고액주문인데 `confirmHighValueOrder` 미설정 |
| 409 | `request-in-progress` | 동일 요청 처리 중 |
| 422 | `insufficient-buying-power` | 매수여력/잔량 부족 |
| 422 | `order-hours-closed` | 장 마감. `retryAfterAt` 동봉 |
| 422 | `stock-restricted` | 거래정지 종목 |
| 422 | `price-out-of-range` | 가격 제한폭 이탈 |
| 422 | `opposite-pending-order-exists` | 반대매매 미체결 주문 존재 |
| 422 | `account-restricted` | 계좌 제한 |
| 422 | `max-order-amount-exceeded` | 주문금액 상한 초과 |
| 422 | `idempotency-key-conflict` | 같은 `clientOrderId`로 다른 내용의 주문 |
| 429 | — | 레이트리밋 |
| 500 | `internal-error` / `maintenance` | 서버 오류 / 점검 |

**`order-hours-closed`와 `429`는 재시도 가능, `422`의 나머지는 재시도해도 같은 결과다.**
이 구분이 자동실행 루프의 재시도 정책을 좌우한다.

## 4. 주문 관련 보조 엔드포인트

| 엔드포인트 | 용도 |
|---|---|
| `GET /api/v1/sellable-quantity` | 매도 가능 수량 조회. **주문 직전 호출 권장** |
| `GET /api/v1/orders` | 주문 목록 (status `OPEN` / `CLOSED`) |
| `GET /api/v1/orders/{orderId}` | 단건 주문 조회 |
| `POST /api/v1/orders/{orderId}/cancel` | 주문 취소 |
| `POST /api/v1/orders/{orderId}/modify` | 주문 정정 |
| `GET /api/v1/market-calendar/{KR\|US}` | 영업일 캘린더 |

`sellable-quantity`가 특히 중요하다. `autoexec`의 매도 수량은
`real_portfolio.json` 스냅샷(최대 ~8시간 stale)에서 계산되므로, 그 사이 수량이
바뀌었으면 주문이 거부되거나 의도와 다른 수량이 나간다. 주문 직전에 실수량을
확인하고 `min()`을 취하는 것이 스냅샷 stale 문제에 대한 직접적 방어다.

## 5. 시세 엔드포인트 (주문과 별개, 부수적 발견)

| 엔드포인트 | 용도 |
|---|---|
| `GET /api/v1/candles` | 캔들 |
| `GET /api/v1/prices` | 현재가 |

현재 `rule_trigger_report.py`의 차트분석 섹션과 `analyze_lib.get_krx_candles()`는
네이버/야후에 의존하는데, 군 네트워크·Actions IP 차단 이슈가 반복돼 왔다. 위 두
엔드포인트가 대체재가 될 수 있다 — **다만 이건 별도 작업이며, 여기서는 존재 사실만
기록한다.**

## 6. 멱등키 운용 시 유의점 (스펙에서 직접 따라나오는 사실)

- `clientOrderId` 유효기간이 **10분**이다. 10분이 지난 뒤 같은 키로 재시도하면
  멱등 보호가 없다 — 즉 **중복 주문이 나갈 수 있다.**
- 따라서 키는 "재시도 묶음" 단위로 생성하되, 10분을 넘긴 재시도는 재시도가 아니라
  새 주문으로 취급해야 한다. 자동 재시도 창을 10분 안으로 두는 편이 안전하다.
- 같은 키에 다른 본문을 보내면 422 `idempotency-key-conflict`다. 즉 키는 주문 내용에
  종속적으로 만들어야 하고, 수량이 바뀌면 키도 바뀌어야 한다.

## 7. 구현 상태와 남은 순서

**2026-08-08 현재 이 저장소에는 주문을 생성·정정·취소하는 코드가 없다.**
`place_sell_order()`는 여전히 `OrderLayerUnavailable`을 던진다.

주문 실행 코드를 `autoexec.py`에 추가하는 것은 CLAUDE.md가 "실계좌 코드 경로 변경"으로
분류하는 작업이며, **자기 세션 포함 사전 방향성 세션 승인을 요구한다.** 스펙이
확보됐다는 사실이 그 승인을 대체하지 않으므로, 코드 세션 판단으로 진행하지 않았다.

승인 후의 순서(건너뛰지 말 것):

1. `place_sell_order()` 구현 — 위 §3 스키마 그대로, `side="SELL"` 고정.
2. **무해한 엔드포인트로 인증·스키마 검증** — 샌드박스에서 `openapi.tossinvest.com`이
   차단돼 있으므로 GitHub Actions에서 `GET /api/v1/orders`(조회)와
   `GET /api/v1/sellable-quantity`부터 호출해 토큰·헤더·프록시 IP 화이트리스트가
   실제로 동작하는지 확인한다. 실주문이 첫 호출이 되면 안 된다.
3. 그 다음에만 `RULE_BASED_AUTOEXEC_ENABLED` 전환 검토.

기존 활성화 순서(킬스위치 테스트 → 안전장치 전부 검증 → 플래그 `true`)는 그대로 유효하며,
위 1~3은 그 안에서 "안전장치 검증" 뒤에 끼어드는 단계다.
