# QuanTrade Client Intelligence / 고객정보관리실 운영 프로토콜

**Status**: ACTIVE DIRECTION  
**Date**: 2026-10-03

## 목적

QuanTrade의 Client Intelligence는 단순 고객정보 보관소가 아니다.

역할은 다음 세 가지다.

1. 투자·자본배분 판단에 필요한 고객정보 중 무엇이 부족한지 식별한다.
2. Founder에게 필요한 질문을 보고서 형식으로 올리고, 답변을 구조화·버전관리한다.
3. Strategy / Portfolio Management / Risk & Compliance / Investment Committee 등이 고객정보를 요청하면 필요 최소한의 Client context를 들고 회의에 참가한다.

Client Intelligence는 고객의 사실·목표·제약을 설명하지만 투자 추천, 포트폴리오 결정, 주문 승인 권한은 갖지 않는다.

## 핵심 흐름

```text
Client Intelligence
  ↓
Information Gap Detection
  ↓
Founder Question Report
  ↓
Founder Answer
  ↓
Versioned ClientFact
  ↓
Strategy / Portfolio / Risk request
  ↓
Need-to-know Meeting Brief
  ↓
Client Intelligence joins meeting
```

## 질문 보고서

질문은 무작정 많은 개인정보를 수집하기 위한 것이 아니다.

각 질문에는 반드시 다음이 따라야 한다.

- question_key
- category
- priority
- question
- why_needed
- used_by

예:

```text
[Critical]
질문:
앞으로 12개월 안에 예정된 큰 지출이나 반드시 확보해야 할 자금이 있나요?

왜 필요한가:
단기 투자자금이 예정 지출과 충돌하지 않도록 하기 위해 필요합니다.

사용 부서:
Strategy / Portfolio Management / Risk & Compliance
```

이미 답을 알고 있는 질문은 다시 묻지 않는다.

## ClientFact

Founder 답변은 문서를 덮어써 저장하지 않는다.

```text
Fact v1
  ↓ superseded by
Fact v2
```

과거 값은 남고 현재값만 projection된다.

각 Fact는 최소 다음을 가진다.

- client_id
- fact_key
- category
- value
- status
- visibility
- source_type / source_id
- supersedes_fact_id
- effective_at
- created_at

## 회의 참가

다른 부서는 고객정보 전체를 직접 가져가지 않는다.

회의 요청 시:

```text
requesting_department
agenda
purpose
requested_keys
```

를 Client Intelligence에 전달한다.

Client Intelligence는:

- 요청된 key만 조회;
- 현재 유효한 Fact만 사용;
- client_office_only 정보는 제외;
- 없는 정보는 missing_information으로 표시;
- 회의에서 고객 상황·목표·제약을 설명;
- 투자 결론은 내리지 않음.

## 권한 분리

```text
Client Intelligence
"고객의 상황은 이렇습니다."

Strategy
"이 상황에서 자본배분 방향을 설계합니다."

Portfolio Management
"투자 포트폴리오 구조를 제안합니다."

Risk & Compliance
"위험 한도와 정책 충돌을 확인합니다."

Investment Committee
"근거와 충돌을 검토합니다."

Founder / Client
"중요 자본배분을 최종 승인합니다."
```

## 개인정보 저장 경계

QuanTrade repository는 민감한 Client 답변의 canonical storage가 아니다.

실제 ClientFact / 질문 답변 / meeting brief는 private LLM Holdings Runtime DB에 저장한다.

Public QuanTrade repo에는 다음만 둘 수 있다.

- 운영 프로토콜;
- 비민감 schema;
- 공개해도 안전한 client context artifact;
- read-only integration code.

다음은 Public repo에 plaintext로 커밋하지 않는다.

- 상세 자산·부채 정보;
- 생활비/지출 계획;
- 민감한 장기 목표;
- 개인 식별정보;
- Client Intelligence 질문에 대한 raw private answer.

## 초기 질문 범위

MVP 질문은 다음 정보 공백을 다룬다.

- minimum liquidity reserve;
- essential monthly outflow;
- next 12-month obligations;
- short-term goals;
- long-term goals;
- risk preference;
- financial risk capacity;
- planned non-investment capital uses.

향후 질문 추가는 실제 downstream decision need가 확인될 때만 한다.

## Development Environment 사례

`client_development_environment.json`은 Client Capital Use context의 첫 실사례다.

향후 QuanTrade가 지속 가능한 수익을 만들면 Client Intelligence는 이 정보를 함께 가져와:

- 재투자;
- 현금 reserve;
- 교육;
- 사업;
- 개발환경;
- 기타 Client goal

사이의 자본배분 검토에 제공할 수 있다.

단, 이 artifact 자체는 하드웨어 구매 권한이나 증권 매도 권한을 주지 않는다.

## 현재 구현 위치

실제 Client Intelligence Runtime 구현은 private `ringoincidents/llm-holdings-runtime`에서 운영한다.

QuanTrade는 Client Intelligence를 자신의 조직 기능으로 사용하지만 민감정보 저장과 권한 enforcement는 private Holdings Runtime이 담당한다.
