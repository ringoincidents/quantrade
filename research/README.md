# QuanTrade Research — durable entry points

This is a **research index**, not implementation authority. The canonical company direction remains in [QUANTRADE_CANONICAL_VISION.md](../QUANTRADE_CANONICAL_VISION.md), and the earlier alpha failure/prediction-disablement gates remain in [CLAUDE.md](../CLAUDE.md).

## PC 접근 시 최우선 재개 과제 — 2026-11-23 보류

**[PC 접근 시 첫 읽기: Market Data Vault 재개 체크리스트](PC_ACCESS_RESUME_PRIORITY_2026-11-23.md)**. 사용자가 영구 저장공간 구성은 PC를 사용할 수 있을 때까지 미루기로 했습니다. 재개 시 **[Data Vault Issue #137](https://github.com/ringoincidents/quantrade/issues/137) / [Draft PR #138](https://github.com/ringoincidents/quantrade/pull/138)**을 먼저 확인하세요. 실데이터 3개 연도는 GitHub Actions 임시 수집/복원 시험에만 존재했고 영구 보관하지 않았습니다. QQQ·SPY·KRX·VIX 원천/약관·배당분할/릴리스 검증은 아직 남아 있습니다. **[시장 복합지수 Issue #135](https://github.com/ringoincidents/quantrade/issues/135)**는 이 데이터 기반 검증 이후 재개합니다. **실거래·운영 코드·유료 저장소 변경 없음.**

## First retrieve before restarting similar work

| Topic / trigger | Durable record | Next action |
| --- | --- | --- |
| **Market-bottom research; VIX / high-yield OAS / DXY / RSI / US rates / exports / gold / oil; composite market state index; 10,000 Monte Carlo forecast fan; one-chart UX** | [QT-MRI-2026-11-22 — Complete Founder intake & experiment plan](2026-11-22_MARKET_REGIME_COMPOSITE_SCENARIO_RESEARCH_V0.md), [tracking Issue #135](https://github.com/ringoincidents/quantrade/issues/135) | **STOP / read first.** G0 provenance-safe data registry + G1 VIX/HY credit spread lead-lag study. NOT VALIDATED; no forecasting activation or order authority. |
| SOXL year-end rebound / market seasonality | [2026-10-17_SOXL_YEAR_END_REVERSAL_RESEARCH_V0.md](2026-10-17_SOXL_YEAR_END_REVERSAL_RESEARCH_V0.md) | Review existing gate and ICE NYSE Semiconductor Index/LETF path-dependence before duplicate research. |
| SOXL, IONQ, TE capital rotation and risk | [2026-10-19_IONQ_TE_TO_SOXL_ROTATION_RESEARCH_CASE_V0.md](2026-10-19_IONQ_TE_TO_SOXL_ROTATION_RESEARCH_CASE_V0.md), [2026-11-18 risk review](2026-11-18_SOXL_IONQ_TE_INCREMENTAL_RISK_REVIEW.md) | Review evidence blockers and independent risk, no assumed live trade. |
| External quant OSS assimilation | [TRADING_OSS_RESEARCH_PROGRAM.md](TRADING_OSS_RESEARCH_PROGRAM.md) | Research first, pin upstream version/license, promote only through validated gates. |

## Intake rule

New market strategy ideas and external forecasting projects are `OBSERVED` sources until reproducible, point-in-time and out-of-sample evaluation supports them. Keep sources, old predictions, data limitations, negative tests and supersession append-only. A future worker should look up this index and active GitHub issues **before** building yet another predictor or dashboard. Neither this index nor an open issue authorizes capital movement or core architecture changes.
