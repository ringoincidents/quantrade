# Git 히스토리 비밀값 전수 스캔 결과 — 2026-08-28

> 이 문서는 스캔 사실과 결과만 기록한다. 재발급/히스토리 재작성 여부는 PM
> 세션의 판단 대상이며, 이 문서는 그 판단을 대신하지 않는다("State facts,
> don't render verdicts" 원칙). **이 저장소는 현재 GitHub상 Public이므로
> 이 문서에는 발견된 비밀값의 전체 원문을 싣지 않는다** — 원문 전체는 이
> 코드 세션이 PM 세션에 별도 채널(대화)로 직접 보고했다.

## 0. 사전 조치 — shallow clone → full clone 전환

세션 시작 시 저장소가 `.git/shallow` 경계를 가진 shallow clone(약 50커밋
제한) 상태였다. `git fetch --unshallow origin`으로 전체 히스토리를
확보했다.

- 전환 전: `git rev-parse --is-shallow-repository` → `true`
- 전환 후: `git rev-parse --is-shallow-repository` → `false`, `.git/shallow`
  파일 자체가 사라짐
- 전환 후 원격 브랜치 8개 전부 로컬에 확보됨(`main` +
  `claude/backtest-session-pumg1v`,
  `claude/claude-md-docs-bpuvud`,
  `claude/news-experiment-push-race-fix`,
  `claude/news-live-cohort-d20-report`,
  `claude/phase-1-backtest-engine-s4yya4`,
  `claude/real-portfolio-sync-proxy`,
  `claude/toss-api-proxy-integration-b83ydz`)
- 전체 히스토리 첫 커밋: `170febc "Initial commit"` (2026-07-28)
- `main` 브랜치 커밋 수: 338개. 전체 참조(`--all`) 도달 가능 커밋 수: 430개.

## 1. 스캔 방법

두 개의 독립된 도구로 교차 검증했다(하나만 쓰면 도구별 탐지 규칙 공백을
놓칠 수 있다는 게 실제로 확인됐다 — §3 참고).

| 도구 | 버전 | 설치 방법 | 스캔 범위 |
|---|---|---|---|
| gitleaks | v8.21.2 | GitHub 릴리스 바이너리 직접 다운로드(`gitleaks_8.21.2_linux_x64.tar.gz`) | `gitleaks git --log-opts="--all" .` — 전체 참조 히스토리 |
| trufflehog | v3.83.7 | GitHub 릴리스 바이너리 직접 다운로드(`trufflehog_3.83.7_linux_amd64.tar.gz`) | `trufflehog git file://.` (브랜치 미지정 시 전체 참조 스캔 — `--branch=main` 단독 실행과 결과 대조해 전체 스캔이 main만 스캔한 것보다 더 많은 데이터(4.5MB vs 103KB)를 훑었음을 확인, 그런데도 발견 건수는 동일해 다른 브랜치에 별도 유출이 없음을 교차 확인) |

두 도구 다 이 세션이 직접 GitHub 릴리스에서 받아 로컬(`/tmp` 스크래치
디렉터리, 저장소 바깥)에 설치했다 — 저장소에는 어떤 바이너리도 커밋하지
않았다.

## 2. 결과 요약

| 도구 | 발견 건수 |
|---|---|
| gitleaks (기본 규칙셋, `--all` 히스토리) | **0건** |
| trufflehog (`git file://.`, 전체 참조) | **3건** (고유 비밀값 2종) |

**gitleaks가 놓친 것을 trufflehog가 잡았다** — 같은 두 값을 파일시스템에
직접 써서 gitleaks 기본 규칙셋으로 단독 재확인했을 때도 0건이었다(§3).
즉 히스토리 순회 범위 문제가 아니라 gitleaks 기본 규칙셋에 텔레그램 봇
토큰/Anthropic API 키 패턴에 대한 전용 탐지 규칙이 없어서 생긴 공백으로
보인다. 지시서가 "gitleaks 또는 trufflehog"라고 했지만 이번 결과는 왜 두
도구를 교차 검증하는 게 의미 있는지 보여준다.

## 3. 상세 발견 내역 (trufflehog, 원문은 별도 보고 — 아래는 식별 정보만)

### 발견 1·2 — Anthropic API 키 패턴 (같은 값, 두 커밋에 등장)

- **탐지기**: `Anthropic` (DetectorType 933)
- **검증 상태**: `Verified: false`, `VerificationError: "unexpected HTTP response status 404"` — trufflehog가 Anthropic 쪽에 실제 검증 요청을 보냈고 404를 받았다는 뜻이다. **이것이 "키가 무효/폐기됐다"는 증거는 아니다** — 어떤 이유로 404가 왔는지(엔드포인트 문제·키 형식 문제·실제 무효화 등) 이 세션은 판정하지 않는다.
- **값 형태(레닥션)**: `sk-ant-api03-19tE****(중략, 총 108자)****ahaWMAAA` — 전체 원문은 PM 세션에 별도 보고.
- **등장 위치**:
  | 커밋 | 시각(KST) | 파일 | 줄 |
  |---|---|---|---|
  | `9656148ee40520c63a11712f120daf6d62f3d9fa` | 2026-07-30 19:34:13 | `analyze.py` | 293 |
  | `c291b566677ce407b9d81f9356a87a19e9801b5e` | 2026-07-30 19:41:13 | `analyze.py` | 10 |

### 발견 3 — Telegram Bot Token

- **탐지기**: `TelegramBotToken` (DetectorType 91)
- **검증 상태**: `Verified: false` (VerificationError 필드 없음 — trufflehog 로그상 이 탐지기는 Anthropic 탐지기와 달리 검증 시도 자체를 안 했거나 무응답으로 처리된 것으로 보인다. 이 세션이 직접 Telegram API에 조회를 시도하지는 않았다 — 실제 유효한 채널로 살아있는 크리덴셜에 조회를 날리는 건 이 세션의 판단 밖이라고 봤다.)
- **값 형태(레닥션)**: `89784323**(중략, 총 46자)**owiIlNc` — 전체 원문은 PM 세션에 별도 보고.
- **등장 위치**:
  | 커밋 | 시각(KST) | 파일 | 줄 |
  |---|---|---|---|
  | `3aa4116fccdcaef69db3e47d0f22652e96128296` | 2026-07-29 18:27:50 | `analyze.py` | 5 |

## 4. 노출 기간 관련 사실

- 이 저장소는 **생성 시점(2026-07-28)부터 지금까지 계속 Public**이다
  (`gh api`/GitHub 검색 API로 확인: `"private": false, "visibility": "public"`).
  Private였다가 바뀐 이력이 아니라 처음부터 공개 상태였다.
- 위 세 커밋(2026-07-29~30)이 만들어진 시점부터 지금(2026-08-28)까지 —
  약 한 달간 — 이 값들은 공개 저장소의 커밋 히스토리를 통해 누구나
  `git clone`/GitHub 웹 UI로 접근 가능했다.
- 현재 `main`의 `analyze.py`/`analyze_lib.py`에는 이 값들이 하드코딩돼
  있지 않다 — 2026-07-31 `analyze_lib.py` 신설 커밋(`7b1bdea`)에서
  `os.environ.get("TELEGRAM_TOKEN", "")` / `os.environ.get("CLAUDE_API_KEY", "")`
  패턴으로 바뀌었다. **즉 노출은 히스토리에만 남아 있고 현재 워킹트리에는
  없다** — `grep -rn`으로 현재 트리 전체를 직접 재확인함(결과 없음).

## 5. 이 세션이 하지 않은 것 (지시서 원칙 그대로)

- **비밀값을 히스토리에서 삭제(rewrite/BFG/filter-repo 등)하지 않았다.**
  지시서가 "삭제 전에 먼저 PM 세션에 알릴 것"이라고 명시했고, 이 보고서가
  그 통보다 — 삭제는 이후 별도 판단·별도 작업이다.
- **키/토큰 재발급을 요청하거나 트리거하지 않았다.** "재발급 여부는 PM
  판단"이라는 지시를 그대로 따랐다.
- **Private/Public 전환을 하지 않았다.** 이 스캔이 완료되기 전까지
  보류하라는 지시대로, 완료된 지금도 전환 자체는 이 세션의 판단 밖이라
  실행하지 않았다 — 위 §4의 사실(현재 Public, 생성 이후 계속 Public)만
  전달한다.

## 6. 다음 단계 (PM 판단 대기, 이 세션이 결정하지 않음)

- Telegram Bot Token(발견 3) 재발급 여부.
- Anthropic API 키로 보이는 값(발견 1·2) 재발급 여부 — 실제로 이 문자열이
  지금도 유효한 키인지부터 PM 쪽에서 Anthropic 콘솔로 직접 확인 필요(이
  세션은 그 확인을 시도하지 않았다).
- 재발급을 결정한다면, 히스토리에서 완전히 제거할지(`git filter-repo`
  등, 강제 푸시 필요 — 파괴적 작업이라 별도 승인 필요) 아니면 "이미
  재발급했으니 과거 값은 무의미"로 두고 히스토리는 그대로 둘지.
- Private/Public 전환 여부 — 이 문서의 §4 사실을 참고 자료로 쓸 것.
