# QuanTrade Research 005 — 뉴스·검색 관심도 관찰 수집기 v0.1

**2026-10-17 / research-only / no market signal / no trading authority.**

## 수집 대상 및 제한

- **GDELT DOC 2.0**의 공개 공식 API를 3개 질의(SOXL, semiconductor stocks/chip stocks, AI chips/HBM)로 각각 최대 75개 **뉴스 원본 URL과 메타데이터**만 수집한다. GitHub Actions가 3시간마다 실행되도록 구성하고 매회 6시간 창을 조회해 지연을 일부 보완한다. 원문 전체와 기자/포럼 사용자 개인정보는 수집하지 않는다. API 오류/0건/상한 초과를 구분한다. **API 응답 성공 및 실제 GitHub Actions 구동은 현재 검증 전**이다. GDELT의 `seendate`는 원 발행시각으로 간주할 수 없다.
- **네이버 데이터랩** 공식 API로 검색어 묶음 `SOXL·속슬·속쓸`, `SOXS·속스`, `반도체 주식·반도체 ETF·필라델피아 반도체`를 최근 365일의 **상대 검색 관심도**로 조회한다. `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`이 없으면 명시적으로 `NO_CREDENTIALS_NOT_FETCHED`. 원 데이터는 해당 조회 창에서 정규화된 비율이며, 절대 검색량/커뮤니티 낙관론이 아니다. 과거 조회치도 오늘 날짜에 최초 관측한 자료이므로 과거 매매 신호로 소급할 수 없다.
- **Reddit / Stocktwits / 디시 / 국내 종토방**의 자동 대량 수집은 승인된 데이터 이용 권한이 없다. 공식 API가 없거나 제한될 때 **우회하지 않는다**. `community_import.py`는 사람이 출처를 확인한 수동 CSV를 정성 사례로만 변환한다. 표집틀이 없어 예측 유효 표본 수는 0으로 유지한다.

## 데이터 구조

각 실행마다 `research/social-event-study/live/runs/yyyymmddThhmmssZ/`에 `run_status.json`, `news_metadata.json`, `naver_trends.json` 생성. `live/state.json`은 기사 URL SHA256 키의 최초 관측시각을 유지하고 중복 기사를 감지한다. 저장되는 경로는 공개 저장소에 게시될 수 있으므로 사용자 계좌·닉네임·원문 댓글을 기록하지 않는다.

실행 시각(`retrieved_utc`)과 GDELT 최초 보도 감지시각(`gdelt_seendate_utc`)은 다른 개념이다. **뉴스의 참 발행시각과 게시 시점의 시장 충격은 현재 불명확하므로 모든 수집 결과에 `predictive_eligible=false`**를 부여한다. 예측 모델 입력으로 승격하려면 공식 원본 게시 시각과 실시간 최초 발견·표본 품질 검증이 별도로 필요하다.

## 사용법

```bash
# Python 3.11+, 외부 라이브러리 설치 없음
PYTHONPATH=research/social-event-study/collector_v1 python -m unittest discover -s research/social-event-study/collector_v1/tests -v
# 실제 요청 없이 URL 설계 점검
python research/social-event-study/collector_v1/collector.py --dry-run --naver --root /tmp/quantrade-study
# 접속 가능한 환경에서, 공식 GDELT 공개 API 사용
python research/social-event-study/collector_v1/collector.py --naver --root research/social-event-study/live
# 선택된 과거 게시글을 수동/정성 데이터로 정리 (미래 예측 표본 0건)
python research/social-event-study/collector_v1/community_import.py \
  research/social-event-study/collector_v1/fixtures/manual_examples.csv \
  --out /tmp/retrospective_metadata.json
```

`--naver` 옵션을 쓰더라도 환경변수의 Naver 키가 없으면 API 호출은 수행되지 않는다. GitHub 사용자는 **Repository > Settings > Secrets and variables > Actions**에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`을 직접 등록할 수 있다. 개인키나 인증정보를 Git에 커밋하지 말 것. 1회 스케줄 수집은 GDELT API 3요청 + 네이버 키가 있다면 데이터랩 1요청이다. 3시간 간격으로 하루 최대 8회이며, 뉴스 75건 상한에 걸리는 질의는 전체량 추정에 사용하지 않는다.

### GitHub Actions

`.github/workflows/social-research-metadata.yml` 파일을 main에 등록하면 `workflow_dispatch` 또는 UTC 기준 3시간 주기의 cron으로 실행을 **시도**한다. Actions 권한이 read-only이거나 main에 branch protection이 있거나 API가 실패하면 원격 실행·commit이 실패할 수 있다. **로컬 mock 단위테스트 통과만으로 배포·API 접속 성공을 주장하지 않는다.** 기본 브랜치로의 자동 `git push`는 research/live 폴더에 한정되며 수집된 URL 외에 상품 주문이나 외부 쓰기는 없다. GitHub 서버의 cron 지연 가능성이 있으므로 관측 간 누락은 기록해야 한다. 원격 실행 확인 전에는 이 워크플로를 '운영 중'으로 보고하지 않는다.

## 연구에서 두 질문을 구분한다

1. **후행성**: 급락 또는 급등 다음에 SOXL 뉴스량·관심도가 얼마나 증가했는가?
2. **선행성**: *이전에 실제로 관측된* 뉴스·커뮤니티 반응이 이후 수익률에 가격/거래량/금리 이상의 정보를 제공했는가? — 아직 미검증.

처음 8주 동안은 주간 누락률, 첫 관찰 시차, 분류 품질, 뉴스 중복율, 네이버 정규화 일관성을 확인하고 이후 위 가설의 사전 등록을 갱신한다. 같은 사건의 제목을 여러 언론사가 복제하거나 같은 URL이 여러 카테고리에 속할 수 있으므로 기사 수 = 독립 사건 수 아님.

**검증 상태(2026-10-17):** 파이썬 **18개 로컬 모의 응답 테스트 통과**. 직접 수집 환경의 외부 DNS 연결 실패. GDELT 원격 API와 실제 GitHub Actions 스케줄 완료 **미검증**. 비밀키 없어 네이버 실제 검색 관심도 응답 **0건**. 커뮤니티 자동 수집 및 매매 우위 **미검증**.