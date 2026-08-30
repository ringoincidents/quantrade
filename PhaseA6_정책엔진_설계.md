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

---

## Step 3 — 구현 결과 (2026-08-30, 진행 지시 반영)

### 3-1. 노출 강화 (신규 설계 없이 바로 구현)

- **텔레그램**: `portfolio_report.py`의 `format_telegram()`에 `role_gap` 섹션을 추가했다(`asset_class_gap` 섹션 바로 다음). 이전까지는 `build_report()`가 계산은 하면서도 텔레그램 렌더 함수가 읽지 않아 누락돼 있었다 — 이번 변경은 새 계산을 추가한 게 아니라 이미 있던 값을 마저 노출한 것이다. 목표가 있는 역할만 목표/실제/갭을 나열하고, `gap_pct < 0`(실제가 목표를 초과)인 역할은 별도로 "⚠️ 목표 초과" 블록에 다시 짚는다.
- **대시보드**: `index.html`의 `renderRoleGap()`에 목표 초과 역할을 위한 경고 카드를 추가했다. **`.gate-banner`(초록/빨강 배너)는 쓰지 않았다** — 그 스타일 바로 위 CSS 주석에 "게이트 배너/칩: 통과·미통과라는 실제 판정 결과라 초록/빨강 사용이 타당한 유일한 배너류 — 그 외 배너·카드는 색을 넣지 않는다"고 명시돼 있어서다. 대신 `rule_matches`/`schedule_warnings`에 이미 쓰이고 있는 `.guardrail-card`(위반 카드 전용으로 유일하게 색 악센트가 허용된 클래스)를 그대로 재사용했다.

**허용오차 관련 사실 확인**: 진행 지시는 "임계값(±5%p 같은 허용범위)은 기존 파일에 이미 있는 값을 재사용"하라고 했으나, `target_allocation.json`/`portfolio_role_mapping.json`을 재확인한 결과 그런 허용오차 값은 **어디에도 없다**(전체 저장소를 "이탈"/"편차"/"허용범위"/"threshold"로 재검색해도 역할 배분 관련 값은 없음 — 있는 건 Risk Engine의 `concentration_pct=30.0`뿐이고 이건 개별 종목 집중도 규칙이라 역할 배분 이탈과는 다른 규칙이다). 새 숫자를 만들지 말라는 지시를 따르기 위해, 허용오차를 발명하는 대신 **목표 초과 여부(0%p 기준) 자체**를 경고 조건으로 썼다 — `compute_role_gap()`이 이미 계산해 두는 `gap_pct`의 부호만 본다. 오차 허용범위가 필요하다고 판단되면 그건 새 숫자를 도입하는 결정이므로 별도 확인이 필요하다.

### 3-2. 예외 승인 기록 (신규)

- **`policy_exception.py`** (신규 파일) — `post_trade_review_log.json`과 동일한 불변 저널(append-only) 패턴. `build_record(role_row, reason, approved_by)`가 `compute_role_gap()`의 행을 그대로 옮겨 레코드를 만들고(새로 계산하지 않음), `append_and_save()`가 `audit()`(금지 필드/문구 검사)를 통과 못하면 저장하지 않는다.
  - 스키마(`policy_exception_log_v1`): `id` / `schema` / `created_at` / `violated_rule` / `role` / `label` / `target_vs_actual`(`target_pct`/`actual_pct`/`gap_pct`) / `reason` / `approved_at` / `approved_by`. 진행 지시의 `event_id`는 `id`로, `target_vs_actual`은 지시 그대로 이름 붙였다.
  - **`post_trade_review.py`의 `_append_and_save()`와 다른 점 하나**: 감사 위반 시 `SystemExit`을 던지지 않고 `AuditViolation` 예외를 던진다. `post_trade_review.py`는 스스로가 최상위 진입점(cron 단위 실행)이라 죽어도 안전하지만, 이 모듈은 `check_updates.py`의 텔레그램 폴링 루프 안에서 메시지 하나당 호출된다 — `run()`의 `telegram_offset.json` 저장이 루프 밖 맨 끝에 있어서 `SystemExit`을 쓰면 offset이 갱신되지 못해 같은 메시지가 다음 폴링에서 무한 재처리될 수 있다. 이 차이를 `policy_exception.py` 상단 docstring과 `AuditViolation` 클래스에 남겨뒀다.
- **`check_updates.py`**: `/approve_exception <역할> <사유>` 명령 추가(기존 `/autoexec_report <id>` 등과 같은 `parts[0]`/`parts[1:]` 파싱 그대로 재사용). `handle_approve_exception()`이 하는 일:
  1. `portfolio_report.json`의 `role_gap`에서 해당 역할을 찾는다(없으면 사용 가능한 역할 목록과 함께 안내).
  2. **그 역할이 실제로 목표를 초과한 상태(`gap_pct < 0`)가 아니면 거부한다** — "예외 승인"은 실제로 존재하는 이탈에 대한 것이어야지, 임의 역할에 대해 만들 수 있는 게 아니라고 판단했다.
  3. 사유가 없으면 거부(빈 사유를 기록하지 않는다).
  4. 텔레그램 발신자(`message["from"]`)에서 `username`/`first_name`+`id`로 `approved_by` 문자열을 만든다 — Telegram API가 주는 정보를 그대로 옮길 뿐, 발신자를 제한하는 인가 로직은 추가하지 않았다(기존 `/autoexec_approve` 등 다른 명령도 발신자 제한이 없어 이 파일의 기존 보안 모델과 동일하게 맞췄다 — 발신자 제한이 필요하다면 그건 이 명령만이 아니라 봇 전체에 걸친 별도 결정이다).
  5. `policy_exception.append_and_save()` 호출, `AuditViolation`이면 사유를 텔레그램으로 알리고 저장하지 않는다.
- **새 상태 파일**: `policy_exception_log.json` (repo root, `check_updates.py`가 씀 — `poll.yml`의 "Commit state" 스텝에 추가해야 실제로 영속된다. **이번 구현에 워크플로 파일 변경은 포함하지 않았다** — `poll.yml` 수정은 별도 확인 후 진행 여부를 판단해야 한다, 2026-08-08 `autoexec_state.json` 미영속화 버그와 같은 유형의 실수를 피하기 위해 명시적으로 남긴다).

### 3-3. 검증

- `python3 portfolio_report.py --self-test` — 기존 27개 항목 + 신규 28번(텔레그램 role_gap 섹션 노출, 목표 초과 경고 줄 렌더링, role_gap 없을 때 "계산 불가" 처리, 매매 지시 문구 부재) 전부 통과.
- `python3 policy_exception.py` 자체 self-test 3개 항목(정상 레코드/금지 문구 거부·미저장/append-only 누적) 통과.
- `check_updates.handle_approve_exception()`을 `send_telegram`/`load_json` mock으로 4개 시나리오(역할 오타, 목표 초과 아닌 역할, 사유 누락, 정상 승인) 통합 테스트 — 전부 기대한 텔레그램 응답과 저장 결과 확인, 테스트 산출물(`policy_exception_log.json`)은 커밋 전 삭제함.
- 대시보드는 Playwright(사전 설치된 Chromium)로 실제 렌더링해 스크린샷 확인 — "포트폴리오 역할 계층" 섹션에 "⚠️ 역할 배분 초과" 카드("스윙-전술 비중이 목표보다 27.9%p 높습니다")가 기존 "집중도" 위반 카드와 동일한 스타일로 표시됨을 확인했다. 테스트에 쓴 `portfolio_report.json`은 스크린샷 후 원본으로 복구했다(git status 깨끗함 확인).
- 텔레그램 렌더 샘플(동일 시나리오):
  ```
  🧭 포트폴리오 역할 계층 (위험자산 총액 99.3% 기준) — 역할 단위 산술이며 매매 지시가 아닙니다
     · 코어: 목표 65.0% / 실제 57.1% / 갭 +7.8%p
     · 위성-장기: 목표 15.0% / 실제 0.0% / 갭 +15.0%p
     · 스윙-전술: 목표 15.0% / 실제 42.9% / 갭 -27.9%p
     ⚠️ 목표 초과:
        - 스윙-전술 비중이 목표보다 27.9%p 높습니다 (목표 15.0% / 실제 42.9%)
  ```

### 3-4. 이번 구현에서 하지 않은 것 (범위 밖, 명시)

- `poll.yml`에 `policy_exception_log.json` 커밋 스텝 추가 — 워크플로 변경은 하지 않았다.
- 허용오차(±X%p) 숫자 도입 — 3-1에서 설명한 대로 새 숫자를 만들지 않기로 했다.
- 발신자 인가(승인 가능한 텔레그램 계정 제한) — 기존 명령들과 같은 수준(제한 없음)으로 맞췄을 뿐 새로 강화하지 않았다.
- A5(`usage_log.json`) 패턴 재사용 — 지시대로 A5 완료 전이라 `post_trade_review_log.json` 패턴을 대신 썼다(이미 위에 기록).
