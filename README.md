# quantrade

> **Current canonical direction:** [QUANTRADE_CANONICAL_VISION.md](./QUANTRADE_CANONICAL_VISION.md)

QuanTrade is an AI-native Private Investment Office for one Client. The repository contains the investment-domain engines, evidence, experiments and operating artifacts that support that mission.

Historical shorthand such as “분석, 추후엔 자동 거래” is no longer sufficient as the project definition. Read the canonical vision before material architecture or product changes.

## PC 접근 후 QuanTrade 재개 — 우선 보고 목록

**최우선 보류 과제:** 반복적인 과거 데이터/API 확보 실패를 막기 위한 **Market Data Vault 영구 비공개 저장공간 구축**. 2026-11-23 사용자 요청으로 PC 접근 가능할 때까지 **보류(DEFERRED)** 했습니다. 새 개발에 착수하기 전 아래 기록을 확인하세요.

1. [PC 접근 시 재개 체크리스트·완료/미완료 인수인계](research/PC_ACCESS_RESUME_PRIORITY_2026-11-23.md) — **첫 읽기**. 권한·비용·백업을 결정하기 전 저장소나 구독을 임의로 만들지 마세요.
2. [Data Vault Issue #137](https://github.com/ringoincidents/quantrade/issues/137) / [Draft PR #138](https://github.com/ringoincidents/quantrade/pull/138) — P0 코드와 29개 합성 테스트, 공식 미국 국채금리 2008·2020·2025년 임시 수집/복구 시험. **영구 보관 미완료, main 미병합**.
3. [Market Regime 복합지수 Issue #135](https://github.com/ringoincidents/quantrade/issues/135) / [Draft PR #136](https://github.com/ringoincidents/quantrade/pull/136) — Data Vault의 합법적인 장기 시계열과 PIT 품질 확보 이후에 VIX·신용스프레드 선행성 연구 재개.

**진행 순서:** Canonical Vision → 재개 목록 → Data Vault 저장소/백업 → 원천 데이터 권리·시계열 검증 → QT-MRI 연구. 이 목록은 탐색용이며 매매 권한·예측 기능을 활성화하지 않습니다.
