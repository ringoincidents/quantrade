# QT-CASE-002 Result — Samsung Cash-Flow & Cross-Method Robustness

Status: **COMPLETED / RESEARCH-PAPER ONLY / NO TRADE AUTHORITY**

## Frozen Case

- Asset: KRX:005930
- As-of: 2026-10-05T23:59:59+09:00
- Market close: 276,000 KRW

## Cash-flow reconstruction

- FY2025 owner-cash-flow proxy: 33.16T KRW
- 2025-H1 owner-cash-flow proxy: 6.74T KRW
- 2026-H1 owner-cash-flow proxy: 112.39T KRW
- TTM owner-cash-flow proxy: **138.82T KRW**
- Implied basic shares: 6.701B
- TTM owner cash flow/share: **20,716 KRW**

## Cash-flow DCF

- Bear: **165,725 KRW** (return -39.95%, p=25%)
- Base: **275,526 KRW** (return -0.17%, p=50%)
- Bull: **398,207 KRW** (return 44.28%, p=25%)

- DCF weighted fair value: **278,746 KRW**
- DCF expected return: **1.00%**

## Cross-method robustness

- QT-CASE-001 P/E weighted fair value: 362,640 KRW
- DCF weighted fair value: 278,746 KRW
- Classification: **CROSS_METHOD_MIXED**
- Lower-of-two weighted fair value: **278,746 KRW**
- Robust expected return: **1.00%**
- 15% hurdle: **NOT CLEARED**

## Deterministic Counter-Research

- Status: **MATERIAL_COUNTER_EVIDENCE**
- Flags: HIGH_MULTIPLE_REGIME_DISPERSION, NEGATIVE_OWNER_CASH_FLOW_YEAR, WEAK_MEDIAN_CASH_CONVERSION, CURRENT_PB_ABOVE_HISTORICAL_P75
- P/E max/min dispersion: 5.37x
- Median annual cash conversion: 36.89%
- TTM cash conversion: 92.75%
- Current P/B: 4.36x
- Historical P/B P75: 1.59x

## Portfolio/Risk sandbox

- Portfolio: **NOT_COMPETITIVE**
- Portfolio reasons: CASE_RETURN_HURDLE_NOT_MET, DOES_NOT_BEAT_BEST_CAPITAL_ALTERNATIVE
- Capital upper bound: 5.01% (not target weight)
- Risk: not invoked because Portfolio was not eligible.

## Boundaries

- Real Open DART data: yes
- Model calls: 0
- Sell-side target prices: none
- Private Client portfolio: no; sandbox only
- Founder/Committee Decision: none
- PAPER/live execution: none

QT-CASE-002 is a robustness challenge to a known QT-CASE-001 result. It is not independent proof of alpha.
