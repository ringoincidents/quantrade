# QuanTrade v4.0 Phase A6 — Personal Policy Engine 설계

**작성일**: 2026-08-30
**목적**: Core/Satellite/Cash 등 목표 배분 대비 이탈 감지·경고·예외 승인 기록. 계산이지 추천이 아님.
**지시사항**: 기존 자산 재확인 먼저 — 이미 있는 걸 새로 만들지 않는다.

---

## Step 1 — 기존 자산 조사 결과 (사실)

### 1-1. `portfolio_role_mapping.json` (실제 구조)

`schema: portfolio_role_mapping_v1`, 2026-08-17 생성, 원 지시는 "방향성 세션 지시 2026-08-10 — 초안, 확정 아님".

- `roles`: 코어(65%) / 위성-장기(15%) / 스윙-전술(15%) / 정리대상(목표 없음, `target_weight_pct: null`)
- `target_weight_pct`는 **포트폴리오 전체 비중이 아니라 위험자산 총액 대비 비율** (파일 자체의 `risk_bucket_suballocation_note`에 명시)
- `mappings`: 종목 5개(SCHD/196170/004000/TE/NMR)에 역할 태깅, `asset_class_mapping.json`(자산군 축)과는 독립된 두 번째 분류 축

### 1-2. `target_allocation.json` (실제 구조)

`schema: target_allocation_v1`, 2026-08-10 생성, 마찬가지로 "초안, 확정 아님".

- `safe_classes`(채권/현금성) vs `risk_classes`(8개 자산군)의 목표비중
- `safe_total_pct_by_rank`: 계급(일병/상병/병장) 구간별 안전자산 비중 선형 증가
- 위험자산군 내부는 매핑된 자산군에 한해 균등분배(1/n)

### 1-3. `portfolio_report.py`의 Risk Engine — 이미 이 계산을 하고 있는가?

**예.** 다음 함수들이 이미 구현·self-test까지 완료된 상태로 존재한다 (`portfolio_report.py:747-899`):

| 함수 | 하는 일 |
|---|---|
| `load_symbol_role_map()` | 종목코드 → 역할 딕셔너리 (active:false 제외) |
| `compute_risk_asset_total_pct()` | 포트폴리오 전체 대비 위험자산 총액 비중(%) — `target_allocation.json`의 `safe_classes` 실보유 비중을 100에서 뺀 값 |
| `compute_role_actual_pct()` | 역할별 실제 비중을 **위험자산 총액 대비**로 환산 |
| `compute_role_members()` | 역할별 실제 보유종목 상세(비중, note) |
| **`compute_role_gap()`** | 역할별 **[목표비중 / 실제비중 / 갭(%p)]** — 이번에 요청된 "이탈 감지 계산식" 그 자체 |
| `compute_role_monthly_fill()` | 위성-장기+스윙-전술 실제 합이 목표 합(30%)을 초과하면 이번 달 위험자산 배정분 전액을 코어로 유도하는 규칙 (매매 실행은 안 함, 계산·문서화만) |

`build_report()`가 `role_mapping` 인자를 받아 위 체인을 실행하고 결과를 `report["role_gap"]`에 담는다. self-test 25~27번이 이 경로를 검증한다 (`portfolio_report.py:1604-1674`).

**결론: 이탈 감지 계산 자체는 이미 존재한다. 새로 설계할 필요 없음.**

### 1-4. 노출 현황 (사실 — 여기가 실제로 비어있는 부분)

- **대시보드(`index.html`)**: `renderRoleGap()`(1053-1056행 근처)이 `role_gap`을 이미 렌더링한다 — 역할별 목표/실제/갭 표 + 이번 달 배분 계산 안내. 하지만 **"정책 위반" 경고로서의 시각적 강조는 없다** — 갭이 양수(미달)일 때 `gapCls='negative'`로 색만 바뀔 뿐, 임계값 기반 경고 배너/문구는 없다.
- **텔레그램(`format_telegram_report` 계열)**: `asset_class_gap`은 텔레그램 리포트 텍스트에 렌더링되는데(`portfolio_report.py:1116-1132`), **`role_gap`은 텔레그램에 전혀 노출되지 않는다.** `build_report()`는 계산해서 반환하지만 텔레그램 렌더 함수가 `report.get("role_gap")`을 읽는 코드 자체가 없다 — 계산은 되는데 반쪽만 보여주고 있었다는 사실.

### 1-5. "예외 승인 기록" 관련 기존 자산

- `usage_log.json`은 리포에 **존재하지 않는다** (지시대로 A5 완료 전이므로 이 재사용 여부는 여기서 판정하지 않음).
- 가장 가까운 기존 패턴은 `post_trade_review_log.json` / `post_trade_review.py`의 **불변 저널(append-only journal)**:
  - 레코드 필드: `id`, `generated_at`, `trigger`, `schema`
  - `_append_and_save()`가 `audit()`(금지 필드/문구 검사)를 통과 못하면 `SystemExit`으로 저장 자체를 거부 — "불변 저널 원칙"
  - self-test로 위반 시 `save_json`/`send_telegram` 미호출 검증(10번 항목)
  - 단, 이건 **사후 관찰 기록**이지 승인/거절 워크플로가 아니다 — "정책 이탈을 사람이 알고 예외로 승인했다"는 개념 자체는 이 로그에도 없다.
- `pending_actions.json` / `autoexec_state.json`의 `pending_approvals`(`waiting`/`approved`/`rejected`, `APPROVAL_TTL_DAYS` 만료)도 근접 사례이지만, 이건 **매매 실행 승인**이지 배분 이탈에 대한 예외 승인이 아니다.

**결론: 예외 승인 기록 스키마는 리포에 선례가 없다.** 가장 가까운 재사용 후보는 `post_trade_review_log.json`의 불변 저널 패턴.

---

## Step 1 종합 판정

> Core/Satellite 목표배분 대비 이탈 **감지 계산**은 이미 `portfolio_report.py`에 구현돼 있고, `portfolio_role_mapping.json`/`target_allocation.json`은 v3.1에서 승계된 것이 맞으며 이번에 제안된 모델과 **동일한 것**이다(이름만 Core/Satellite/Cash가 아니라 코어/위성-장기/스윙-전술/정리대상 + 안전자산 별도 축). 대시보드에는 이미 노출돼 있으나 **경고로서의 시각적 강조는 없고, 텔레그램에는 아예 노출되지 않는다.** "예외 승인 기록" 스키마는 리포에 선례가 없다(A5의 `usage_log.json`은 미완성, 가장 가까운 선례는 `post_trade_review_log.json`의 불변 저널 패턴).

→ **A6은 대부분 신규 개발이 아니라 기존 기능의 노출 강화**(Step 2의 첫 번째 분기)다. 예외 승인 기록만 실제로 새로 만들어야 하는 컴포넌트다.

(이 판정은 task 지시문이 "Step 1 결과에 따라 판정하라"고 직접 위임한 범위다. CLAUDE.md의 "verdict는 direction-setting session 몫" 규칙은 Track B/실계좌 승인 경로에 한정된 것이지, 이 문서가 다루는 배분 이탈 계산·UI 노출 설계에는 적용되지 않는다 — real_portfolio.json은 읽기만 하고, 주문 경로는 건드리지 않는다.)

---

## Step 2 — 설계

### 2-1. 신규 개발 불필요 항목

- 목표 배분 정의 스키마 → `portfolio_role_mapping.json`(역할축) + `target_allocation.json`(자산군/안전-위험축) 그대로 사용.
- 이탈 감지 계산식 → `compute_role_gap()` / `compute_asset_class_gap()` 그대로 사용.
- (참고) 두 파일 모두 `provisional: true` / "초안, 확정 아님" 상태다. A6이 이걸 "확정"으로 바꾸는 것은 방향성 세션 몫이며, 이 설계 문서가 정할 사안이 아니다.

### 2-2. 필요한 작업 — §39 형태(정책 위반 경고) 노출

1. **텔레그램 리포트에 `role_gap` 섹션 추가.** 현재 `asset_class_gap`만 렌더링되고 `role_gap`은 계산되고도 누락돼 있다 — 이건 신규 기능이 아니라 이미 계산된 값을 마저 보여주는 누락 보완에 가깝다.
2. **대시보드에 임계값 기반 경고 배너 추가.** 현재는 색상(`negative` 클래스)만 있고 "정책 위반" 문구/아이콘이 없다. 예: `gap_pct`가 일정 %p 이상이면 "⚠️ 목표 대비 이탈 X%p" 명시적 경고 노출.
3. **임계값 저장 위치는 미정 — 확인 필요.** 기존 파일(`portfolio_role_mapping.json`/`target_allocation.json`)에 필드를 추가할지, 별도 파일(`policy_engine_config.json`)을 새로 만들지는 설계 선택지다. 제안: 신규 파일 난립을 피하려면 기존 파일에 필드 추가 쪽이 이 저장소의 관례(상태파일을 최소한으로 유지)에 더 맞는다.

### 2-3. 신규 필요 — 예외 승인 기록

- A5의 `usage_log.json` 패턴 재사용 여부는 지시대로 **A5 Step 2 결과가 나온 뒤 다시 확인** — 지금은 판단 보류.
- 대신 이미 존재하는 `post_trade_review_log.json`의 불변 저널 패턴(append-only, `id`+`generated_at`+`trigger`+`schema`, `audit()`로 금지 문구 검사, 위반 시 `SystemExit`로 저장 자체 거부)을 우선 참고 후보로 제안.
- 스키마 초안 (제안일 뿐, 미확정):

```json
{
  "id": "policy_exception-<timestamp>",
  "created_at": "...",
  "role": "위성-장기",
  "observed_gap_pct": 12.3,
  "target_pct": 15,
  "actual_pct": 27.3,
  "decision": "approved_exception",
  "reason": "<사용자 입력 텍스트, 자유서술>",
  "expires_at": null,
  "schema": "policy_exception_log_v1"
}
```

- 승인 채널 제안: `check_updates.py`의 기존 텔레그램 명령 패턴(`/approve`, `/keep` 등)과 동일하게 `/policy_exception <role>` 류 명령을 추가하는 안이 "신규 UI를 만들지 않고 기존 텔레그램 루프를 재사용한다"는 이 저장소의 관례와 가장 잘 맞는다.

---

## 확인이 필요한 사항 (사용자)

1. `role_gap`을 텔레그램에도 노출할지 — 원하면 2-2(1)은 바로 진행 가능한 작업이다.
2. 경고 임계값 숫자와 저장 위치 (기존 파일에 필드 추가 vs 신규 파일).
3. 예외 승인 기록의 구체 스키마/명령어 이름 확정.
4. A5(`usage_log.json`) 완료를 기다릴지, 지금은 `post_trade_review_log.json` 패턴으로 먼저 만들지.

이 문서는 설계 초안이다 — 코드 변경은 포함하지 않았다.
