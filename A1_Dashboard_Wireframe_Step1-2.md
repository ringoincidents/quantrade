# QuanTrade A1 Dashboard Wireframe — Step 1·2 (2026-08-29)

> **코드 수정 없음 — Wireframe/문서 산출물만.** `index.html`을 직접 읽어 실제
> 렌더링되는 13개 블록을 그대로 추출했다(가정·재구성 없음). 판정성 서술은
> "이번 지시가 명시적으로 요구한 분류·매핑" 범위에서만 내렸고, PM 보류로
> 지정된 두 항목(§4)은 옵션만 제시하고 결정하지 않았다.
>
> 이 문서는 `A1-1`(블록 추출)/`A1-2`(13→7 매핑)/`A1-3`(Data Dependency Map)의
> 결과다. `A1-4`(Wireframe)/`A1-5`(Migration Plan)는 이 문서를 PM이 검토한
> 뒤 별도로 진행한다.

---

## 0. 조사 방법

`index.html`(1190줄)을 전체 읽어 `<h2>` 태그와 그 뒤를 잇는 `<div class="card" id="...">` 블록, 그리고 해당 블록을 채우는 `load*()` JS 함수의 `fetch()` 호출을 대조해 데이터 소스를 확인했다. `loadData()`(1170번째 줄)의 호출 순서가 렌더 순서와 일치함을 확인했다. Alpha Lab 잔재 여부는 2026-08-29 기준 `origin/main`에 이미 반영된 커밋(`c3afea4`, "Tag Alpha Lab files as isolated (v4.0 §15), no physical move")의 인라인 주석("Alpha Lab 데이터 — 참고용, Core 판단에 사용 안 함")을 근거로 표시했다 — 이 세션이 새로 판단한 게 아니라 이미 코드에 표시돼 있던 사실을 옮긴 것이다.

---

## 1. A1-1: 13개 블록 전수 추출

| # | 블록명 (`<h2>`) | 데이터 소스 (JSON/모듈) | 목적 | 현재 사용자 가치 | Alpha Lab 잔재 | v4.0 7영역 귀속(안) | 판정 |
|---|---|---|---|---|---|---|---|
| 1 | 🏦 계좌현황 | `real_portfolio.json` (`loadRealAccount`) | 실계좌 현금/보유비중(도넛차트)/종목별 수익률 표시 | 높음 — 유일한 실계좌 잔고 조회 화면 | 없음. 단, 내부 서브카드 "⏳ AI 매매 제안"(`last_report.json`의 `target_account==real` pending, `loadRetiredPending`)은 `badge-retired`로 이미 "연구 종료" 표시됨(예측 경로 v3.2 비활성) | **MY PORTFOLIO** | 유지 (서브카드는 통합 시 제거 검토 대상 — 이미 죽은 기능의 화면 잔재) |
| 2 | 📈 손익 추이 | `historical_pnl_manual.json` + `portfolio_pnl_history.json` (`loadPnlHistory`) | 총손익(정적)+평가손익(자동) 병합 차트 | 높음 — 유일한 시계열 손익 화면 | 없음 | **MY PORTFOLIO** | 유지 |
| 3 | 📋 현황 및 규칙 점검 | `portfolio_report.json` (`loadPortfolioReport`) — 내부에 `asset_class_mapping.json`/`target_allocation.json`/`portfolio_role_mapping.json`/`income_schedule.json` 기반 계산 결과 포함 | 포지션 현황, 규칙 해당 매치, 자산군 배분 갭, 포트폴리오 역할 계층, 배분 로드맵 4가지가 한 블록에 번들 | 높음이나 밀도 과다 — 서로 다른 4개 기능이 한 카드에 있음 | 없음 | **MY PORTFOLIO** (규칙 해당 매치 부분만 TODAY 성격) | 통합(분해 재구성) — 포지션목록→MY PORTFOLIO 요약, 규칙매치→TODAY 알림, 배분갭/역할계층/로드맵→MY PORTFOLIO "배분" 하위뷰로 분리 필요 |
| 4 | ⚖️ 포지션 사이징 · 리스크 · 상관관계 | `portfolio_report.json`의 `risk_engine` 필드 (`loadRiskEngine`, #3과 같은 파일) | 신규매수 권장금액 범위/MDD예산/집중도/상관관계/비용반영후 수익률 | 중간 — Risk Engine이 provisional 표시된 초안 기준 | 없음 | **MY PORTFOLIO**("리스크" 하위뷰) | 통합 — #3과 데이터 소스가 이미 같은 파일이므로 하나의 "MY PORTFOLIO → 배분/리스크" 화면으로 합치는 게 자연스러움 |
| 5 | 📚 118티커 통계 검증 결과 | `indicator_significance_report.json` (`loadIndicatorLearning`) | 보조지표 118티커 통계 유의성 검증 결과(학습 기록, 신호 아님) | 낮음 — workflow_dispatch 수동 실행 전용, 스케줄 없어 갱신 안 됨 | **있음**(코드 주석 명시) | 7영역 밖(Alpha Lab/Research) | **PM 보류 — §4-A 참고, 판정 안 함** |
| 6 | 🛡️ 규칙 위반 점검 | `last_report.json`의 `guardrail_violations` (`loadGuardrails`) | 비중 상한·최소 현금 비율 위반 사실만 표시(결정론적 산술) | 높음 — v3.2에서 AI가 담당하는 두 역할 중 하나(리스크 가드레일)의 직접 출력 | 없음 | **TODAY** | 유지, 귀속만 TODAY로 이동 |
| 7 | 📄 오늘의 사건 카드 | `news_event_cards.json` (`loadNewsCards`) | 뉴스 사건 설명 + 이상행동(거래량/갭/변동성) 카드 | 높음 — v3.2 AI 역할 (b), 대상은 보유+관심종목(`watchlist.json`)으로 스코프됨 | 없음(v3.2 활성 기능) | **EVENTS** (종목별 카드는 STOCK DETAIL에도 교차 노출 가능) | 이동(EVENTS) + TODAY 요약/STOCK DETAIL 교차 노출 |
| 8 | 📈 현재 시장 상태 수치판 | `market_indicators.json`의 `state_board` (`loadMarketIndicators` 전반부, #9와 같은 파일) | 변동성 백분위/ADX/보유종목간 상관계수, 라벨·판정 없이 값만 나열 | 중간 — 대상이 보유+관심종목으로 한정(시장 전체 아님) | 없음 | **MARKET** | 이동(MARKET) + STOCK DETAIL 교차 노출 |
| 9 | 📊 지표 병렬 표시판 | `market_indicators.json`의 `indicator_board` (`loadMarketIndicators` 후반부, #8과 같은 파일·같은 fetch) | PER(미연결)/변동성/모멘텀/ADX를 종목별 병렬 나열, 원본 순서 고정 | 중간 — PER 데이터 소스 미연결로 항상 공란 | 없음 | **STOCK DETAIL**(1차) / MARKET(2차) | 이동(STOCK DETAIL 우선) |
| 10 | 🗒️ Layer 3 — 사후 점검 리포트 | `post_trade_review_log.json` (`loadPostTradeReview`) | 노출변화/배분갭매치/상관관계사각지대/행동패턴/최근뉴스연결 — append-only 불변 저널 | 중간 — "경고 후 실제 행동 변화 추적"이라는 v3.2 새 성공지표와 가장 가까운 화면 | 없음 | **TODAY**(활동 요약) 또는 MY PORTFOLIO(활동 로그 탭) | 유지(내용), 귀속만 이동 — §4-B(로깅 훅 후보 위치)와 직결 |
| 11 | 📊 게이트 판정 요약 | `backtest_report.json` (`loadGate`) | Phase 1 백테스트 §2.1 게이트 판정(고정값, 완료된 연구) | 낮음 — 재실행 전까지 값이 절대 안 바뀜, 이미 기각 결론 | **있음**(코드 주석 명시) | 7영역 밖(Alpha Lab/Research) | **PM 보류 — §4-A 참고, 판정 안 함** |
| 12 | 📰 데이터수집 진행상황 | `news_event_calibration_log.json` (`loadPhase2`) | Phase 2 뉴스 방향판단 코호트 진행상황(건수/D+20 도달일) | 낮음 — 코호트 cron 자체가 이번 주 초 dispatch-only로 전환됨(§18 별도 기록) | **있음**(코드 주석 명시) | 7영역 밖(Alpha Lab/Research) | **PM 보류 — §4-A 참고, 판정 안 함** |
| 13 | 🛑 킬스위치 상태 | `autoexec_state.json` (`loadAutoexecStatus`) | 규칙 기반 자동실행 킬스위치 정지/해제 상태 | 낮음 — `autoexec_state.json` 자체가 아직 한 번도 생성된 적 없음(킬스위치가 실사용된 적 없음, Gap Analysis §5-5 기존 확인 사실) | 없음(활성화 전 인프라) | **TODAY**(시스템 상태 위젯) | 유지, 귀속만 TODAY로 이동 |

**집계**: 유지 5 / 통합 2 / 이동 3 / PM 보류(판정 유보) 3.

---

## 2. A1-2: 13→7 매핑표 확정

| v4.0 7영역 | 대응하는 기존 블록(#) | 비고 |
|---|---|---|
| **TODAY** | #6(규칙위반점검), #10(Layer3, 부분), #13(킬스위치) — 그리고 #3의 "규칙 해당 매치" 부분 | 4개 블록에서 요약을 발췌해 만드는 **합성 화면**. 오늘 하루치를 그대로 보여주는 기존 블록은 없음. |
| **MY PORTFOLIO** | #1(계좌현황), #2(손익추이), #3(현황·규칙점검 — 배분갭/역할계층/로드맵 부분), #4(포지션사이징·리스크) | 13개 중 4개(외 #3 일부)가 이 영역에 몰려 있음 — 현재 대시보드의 실질적 중심. |
| **MARKET** | #8(시장상태수치판) | 1개뿐. 현재 스코프가 보유+관심종목으로 한정돼 있어 "시장 전체"라는 이름에 비해 좁음 — 이름과 실제 범위 불일치는 v4.0 설계 시 확인 필요(판정 아님, 사실만). |
| **EVENTS** | #7(오늘의사건카드) | 1개뿐. 현재도 EVENTS 성격이 가장 뚜렷한 블록. |
| **WATCHLIST** | **없음** | 대응하는 기존 블록이 하나도 없다. `watchlist.json`은 존재하지만(현재 `symbols: []`, 비어있음) 이를 직접 보여주는 화면이 없다 — 완전 신규. |
| **STOCK DETAIL** | #9(지표병렬표시판, 1차) | 종목별 상세를 목적으로 만들어진 블록이 없다 — #9는 "병렬 나열 표"이지 종목 하나를 드릴다운하는 상세 화면이 아니다. 사실상 신규에 가까움. |
| **ORDER** | **없음** | 대응하는 기존 블록이 없다. `pending_actions.json`(승인 대기 큐)이 개념적으로 가장 가깝지만 이건 텔레그램 승인 플로우의 데이터이지 대시보드 화면이 아니고, `autoexec.place_sell_order()` 자체가 미구현이라 완전 신규. |
| **(7영역 밖) Alpha Lab/Research** | #5, #11, #12 | §4-A 참고. |

**핵심 사실**: 13개 블록 중 9개(#1/#2/#3/#4/#6/#7/#8/#9/#10, #13 포함 시 10개)가 MY PORTFOLIO+TODAY+MARKET+EVENTS 4영역에 재배치 가능하지만, **WATCHLIST와 ORDER는 대응 블록이 0개** — 기존 화면을 이동/통합해서 채울 수 없고 새로 설계해야 한다.

---

## 3. A1-3: Data Dependency Map

| v4.0 영역 | 의존 JSON | 의존 모듈(생성기) | 비고 |
|---|---|---|---|
| **TODAY** | `last_report.json`, `autoexec_state.json`, `post_trade_review_log.json`(발췌), `news_event_cards.json`(오늘자 발췌) | `analyze.py`(가드레일), `autoexec_stop_fast.py`/`autoexec.py`(킬스위치), `post_trade_review.py`, `news_event_cards.py` | 단일 소유 모듈 없음 — 4개 생성기의 출력을 화면단에서 합성해야 함. 오늘 이 파일들을 하나로 묶는 백엔드 로직은 없음(대시보드 JS가 개별 fetch). |
| **MY PORTFOLIO** | `real_portfolio.json`, `historical_pnl_manual.json`, `portfolio_pnl_history.json`, `portfolio_report.json`, `asset_class_mapping.json`, `target_allocation.json`, `portfolio_role_mapping.json`, `income_schedule.json` | `real_portfolio_sync.py`, `portfolio_report.py` | 가장 많은 의존성. `portfolio_report.py`가 사실상 이 영역의 백엔드 역할(포지션/배분갭/역할계층/로드맵/Risk Engine 전부 이 한 모듈이 생성). |
| **MARKET** | `market_indicators.json`(`state_board`) | `market_indicators.py` | 대상 유니버스가 `real_portfolio.json`+`watchlist.json` 조합(`build_universe()`)이라, "시장 전체"가 아니라 "내가 보는 종목들의 시장 상태"에 가까움. |
| **EVENTS** | `news_event_cards.json` | `news_event_cards.py` | 대상 유니버스 동일(`build_universe()`). `watchlist.json`이 입력으로 쓰이지만 WATCHLIST 화면 자체를 위한 게 아니라 이 모듈의 필터링 용도. |
| **WATCHLIST** | `watchlist.json`(사람이 수기 입력, 현재 비어있음) | 없음 — 이 파일을 읽어 화면을 그리는 코드가 index.html에 없음 | 데이터는 존재, 화면 없음. `target_prices.json`(목표가, 역시 수기 입력·현재 비어있음)도 개념적으로 이 영역과 가까움(관심종목+목표가는 같이 관리되는 게 자연스러움). |
| **STOCK DETAIL** | `market_indicators.json`(`indicator_board`), `news_event_cards.json`(종목 필터), `real_portfolio.json`(보유 시), `target_prices.json`(목표가 설정 시) | `market_indicators.py`, `news_event_cards.py` | 여러 소스를 종목코드(symbol) 기준으로 조인해야 하는데, 현재 이런 조인 로직 자체가 없음(각 블록이 독립적으로 렌더링됨) — 신규 조인 계층 필요. |
| **ORDER** | 없음(직접 대응 파일 없음) | 없음 | 가장 가까운 기존 데이터는 `pending_actions.json`(텔레그램 승인 큐)과 `autoexec.py`의 `queue_for_approval()`/`autoexec_reports.json`(규칙 발동 시 심층분석 리포트) — 하지만 이건 텔레그램 플로우이지 대시보드 화면이 아니고, 실주문 실행 코드(`place_sell_order`) 자체가 미구현. |

---

## 4. PM 보류 항목 — 판단만, 실행 없음

### 4-A. Alpha Lab 3개 JSON 블록(#5/#11/#12) — 메인 잔류 vs Research 분리, 옵션만 제시

세 블록 모두 이미 코드 주석(`c3afea4`)으로 "Alpha Lab 데이터 — 참고용, Core 판단에 사용 안 함"이라고 표시돼 있으나, **물리적으로는 아직 메인 `index.html`에 있다**(같은 커밋 메시지가 "no physical move"라고 명시). 옵션:

| 옵션 | 내용 | 장점 | 단점 |
|---|---|---|---|
| **A. 완전 분리** | 메인 `index.html`에서 세 블록을 제거하고 별도 페이지(예: `research.html`)로 이동 | 7영역 구조가 순수해짐, 메인 화면이 가벼워짐 | 별도 정적 페이지 빌드/배포 경로 추가 필요(현재 GitHub Pages 브랜치 배포 방식과 맞물려 확인 필요 — Gap Analysis §5-4), 기존 링크/북마크 깨짐 |
| **B. 메인 유지 + 섹션 구분 강화** | 물리적 이동 없이 현재처럼 메인 하단에 두되, 이미 있는 배지(`badge-retired`/`badge-phase2`)와 주석 태그를 화면에도 노출해 "Research" 섹션 구분선을 더 명확히 함 | 변경 최소, 이미 절반은 돼 있음(주석은 있음, 화면 라벨은 없음) | 7영역 IA 순수성이 떨어짐, "메인에 있다"는 사실 자체가 오인 소지 |
| **C. 기본 접힘(collapsed) + 토글** | 메인에 남기되 기본적으로 접혀 있고 클릭해야 펼쳐짐 | A와 B의 중간 — 물리적 이동 없이 시각적 분리 | 접힘 상태 관리(로컬스토리지 등) 신규 구현 필요 |

이 세 옵션 중 무엇을 택할지, 혹은 §4-A를 A1-4/A1-5로 넘길지는 PM 판단.

### 4-B. §16.1 사용기록 로깅 훅 — 위치 후보만 제안, 구현은 A5

CLAUDE.md의 새 성공지표("경고 후 실제 행동 변화 추적")와 맞물리는 후보 위치 3곳:

1. **TODAY의 규칙위반점검(#6) 카드** — 가장 직접적인 후보. 경고 발생 시점과 이후 포지션 조정 여부를 같은 화면 맥락에서 추적하는 게 가장 자연스러움.
2. **EVENTS의 오늘의 사건 카드(#7)** — 특히 이상행동 카드(거래량 급변 등) 노출 후 실제 행동 여부 추적. 뉴스 사건 카드 쪽은 판단 여지가 더 커서 로깅 대상 정의가 상대적으로 애매할 수 있음.
3. **Layer 3 사후 점검 리포트(#10)** — 이미 `behavior_patterns` 필드가 스키마에 있어(§1의 #10 참고), 로깅 결과를 이어붙이기 가장 자연스러운 기존 자리. append-only 저널이라는 성격도 로그 축적과 맞음.

세 곳 중 어디에 넣을지, 혹은 세 곳 모두에 넣을지는 A5에서 구현 설계와 함께 결정 — 이 문서는 후보 위치만 제시.

---

## 5. 이번 조사에서 확인된 부수 사실

- `origin/main`이 이 세션 시작 시점 기준 `2c4c0fb`까지 진행돼 있었고, 그 중 `c3afea4`가 §4-A의 세 블록에 이미 "Alpha Lab" 주석 태그를 달아 놓은 상태였다 — 이 작업이 언제 누구 지시로 됐는지는 이 문서가 조사한 범위 밖이다.
- WATCHLIST/ORDER 두 영역에 대응하는 기존 블록이 0개라는 사실은 A1-4(Wireframe) 단계에서 "이동/재배치"가 아니라 "신규 설계" 작업이 상당 비중을 차지할 것임을 시사한다(판정 아님, 이후 단계의 작업량 관련 사실만 기록).

---

## 부록 — 참고용 원본 매핑 (블록ID ↔ 로드 함수)

| DOM id | 로드 함수 |
|---|---|
| `real-section` / `real-pending-section` | `loadRealAccount`, `loadRetiredPending` |
| `pnlhistory-section` | `loadPnlHistory` |
| `preport-section` | `loadPortfolioReport` |
| `riskengine-section` | `loadRiskEngine` |
| `indicatorlearning-section` | `loadIndicatorLearning` |
| `guardrail-section` | `loadGuardrails` |
| `newscard-section` | `loadNewsCards` |
| `marketstate-section` / `indicatorboard-section` | `loadMarketIndicators`(동일 함수, 같은 fetch로 두 섹션 채움) |
| `postreview-section` | `loadPostTradeReview` |
| `gate-section` | `loadGate` |
| `phase2-section` | `loadPhase2` |
| `autoexec-section` | `loadAutoexecStatus` |
