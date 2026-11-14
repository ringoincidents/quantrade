# QT-CASE-003 Pre-Registration — Samsung SDI Holdout Transfer Case

Status: **FROZEN BEFORE ANY QT-CASE-003 LIVE ECONOMIC RESULT**  
Date: **2026-10-09**  
Mode: **RESEARCH / HOLDOUT / PAPER-ONLY / NO CAPITAL AUTHORITY**

## 1. Purpose

QT-CASE-003 tests whether the Investment Office process learned from
QT-CASE-001/002 can transfer to a second real issuer without tuning the
valuation thresholds after seeing the result.

This is a **company holdout**, not a time-series holdout.

The target is selected before querying QT-CASE-003 Case-period fundamentals or
price.

## 2. Frozen target

- company: Samsung SDI
- KRX code: `006400`
- asset ID: `KRX:006400`
- Case as-of: `2026-10-05T23:59:59+09:00`
- valuation horizon: **365 days**
- currency: **KRW**

Selection rationale:

- independent issuer from Samsung Electronics;
- large KRX operating company with Open DART reporting;
- capital-intensive manufacturing business;
- outside the memory-semiconductor issuer used in QT-CASE-001/002;
- ticker was already present in the pre-existing QT-STRAT-005 transfer universe,
  so it was not discovered by screening current valuation output.

The earlier technical-strategy experiment did not reveal the fundamental
valuation result used here.

The target may not be replaced if the holdout result is inconvenient.

## 3. Frozen source rules

Fundamentals:

**Financial Supervisory Service Open DART**

Report families:

- annual `11011`
- half-year `11012`

Fiscal window:

`2022-01-01 .. 2026-06-30`

Price:

Naver Finance daily history, bounded at the Case date.

Use:

- final trading close on/before each 2022-2025 fiscal year-end;
- final trading close on/before 2026-10-05.

No post-Case price may enter the result.

## 4. Frozen valuation architecture

QT-CASE-003 must run two independent methods:

1. historical P/E scenario valuation;
2. owner-cash-flow DCF.

Then it must pass them through the reusable:

`ValuationCrossCheckArtifact`

before Portfolio Opportunity Cost.

No method may independently bypass the cross-method gate.

## 5. Frozen P/E method

Use the same method family as QT-CASE-001.

### TTM EPS

```text
TTM EPS
=
FY2025 basic EPS
+ 2026-H1 YTD basic EPS
- 2025-H1 YTD basic EPS
```

Required exact metric keys:

- annual:
  `DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:IS:CURRENT_PERIOD`
- half-year YTD:
  `DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:IS:CURRENT_YTD`

All three TTM inputs must be positive.

### Historical P/E

For each FY2022-FY2025:

```text
P/E = year-end close / full-year basic EPS
```

All four annual EPS values are required and must be positive.

No year may be deleted as an outlier.

Percentiles use the same deterministic linear interpolation:

- P25
- P50
- P75

### P/E scenarios

Probabilities remain:

- Bear 25%
- Base 50%
- Bull 25%

Bear:
- EPS = 80% of TTM EPS
- P/E = historical P25

Base:
- EPS = 100% of TTM EPS
- P/E = historical P50

Bull:
- EPS = 120% of TTM EPS
- P/E = historical P75

Required-return hurdle:

**15%**

## 6. Frozen owner-cash-flow proxy

Use the same QT-CASE-002 exact-account method:

```text
Owner Cash Flow Proxy
=
Operating Cash Flow
- PP&E Purchases
- Intangible Purchases
```

Exact metric keys:

### Operating cash flow

`DART_ACCOUNT:ifrs-full_CashFlowsFromUsedInOperatingActivities:CF:CURRENT_PERIOD`

### PP&E purchases

`DART_ACCOUNT:ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities:CF:CURRENT_PERIOD`

### Intangible purchases

`DART_ACCOUNT:ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities:CF:CURRENT_PERIOD`

No account-name substitution is allowed.

## 7. Frozen TTM owner-cash-flow bridge

```text
TTM Owner Cash Flow Proxy
=
FY2025 Owner Cash Flow Proxy
+ 2026-H1 Owner Cash Flow Proxy
- 2025-H1 Owner Cash Flow Proxy
```

If the result is non-positive:

`NON_POSITIVE_TTM_OWNER_CASH_FLOW`

and the DCF method fails closed.

The security is not replaced.

## 8. Frozen implied-share denominator

```text
Implied Basic Shares
=
FY2025 Profit Attributable to Owners
/
FY2025 Basic EPS
```

Required exact parent-profit key:

`DART_ACCOUNT:ifrs-full_ProfitLossAttributableToOwnersOfParent:IS:CURRENT_PERIOD`

Both values must be positive.

This is explicitly an accounting-derived approximation.

## 9. Frozen cash-flow DCF

Use exactly the same scenario assumptions as QT-CASE-002.

Explicit horizon:

**5 years**

### Bear — 25%

- starting cash-flow factor: 0.80
- explicit annual growth: 0%
- terminal growth: 0%
- discount rate: 10%

### Base — 50%

- starting cash-flow factor: 1.00
- explicit annual growth: 3%
- terminal growth: 2%
- discount rate: 10%

### Bull — 25%

- starting cash-flow factor: 1.20
- explicit annual growth: 5%
- terminal growth: 3%
- discount rate: 10%

No parameter may change after observing QT-CASE-003.

## 10. Frozen Cross-Method Valuation Gate

The existing reusable gate is mandatory.

Methods:

- `PE`
- `OWNER_CASH_FLOW_DCF`

They must share:

- current price;
- 15% hurdle;
- Bear/Base/Bull IDs;
- 25/50/25 probabilities.

Classification:

- every method clears 15%:
  `CROSS_METHOD_CONFIRMED`
- some but not all clear:
  `CROSS_METHOD_MIXED`
- none clear:
  `CROSS_METHOD_REJECTED`

Robust scenario value:

```text
minimum(PE fair value, DCF fair value)
```

Portfolio review requires:

`valuation_gate_passed = true`

A MIXED result cannot enter Portfolio review in QT-CASE-003.

## 11. Frozen Counter-Research

Use the same deterministic checks as QT-CASE-002.

### Multiple regime dispersion

```text
max historical P/E / min historical P/E
```

Flag if > 4.0:

`HIGH_MULTIPLE_REGIME_DISPERSION`

### Annual cash conversion

For FY2022-FY2025:

```text
Owner Cash Flow Proxy
/
Profit Attributable to Owners
```

Flag if any owner-cash-flow year <= 0:

`NEGATIVE_OWNER_CASH_FLOW_YEAR`

Flag if four-year median < 0.75:

`WEAK_MEDIAN_CASH_CONVERSION`

### TTM cash conversion

```text
TTM Parent Profit
=
FY2025 parent profit
+ 2026-H1 parent profit YTD
- 2025-H1 parent profit YTD

TTM Cash Conversion
=
TTM Owner Cash Flow Proxy / TTM Parent Profit
```

Flag if < 0.75:

`WEAK_TTM_CASH_CONVERSION`

### P/B sanity check

Parent equity exact key:

`DART_ACCOUNT:ifrs-full_EquityAttributableToOwnersOfParent:BS:CURRENT_PERIOD`

Use the same frozen implied-share denominator for 2022-2025 BVPS.

Flag if current P/B > historical P75:

`CURRENT_PB_ABOVE_HISTORICAL_P75`

P/B is Counter-Research only and does not set fair value.

## 12. Thesis / CounterClaim / falsification

Thesis must be the arithmetic conclusion of the cross-method gate.

CounterClaim:

> A favorable accounting-earnings valuation may not survive owner-cash-flow
> valuation in a capital-intensive battery manufacturer because capex,
> cash-conversion, and valuation regimes can diverge from current EPS.

Falsifiers:

1. later reconstructed TTM owner-cash-flow proxy falls below 80% of the frozen
   QT-CASE-003 level;
2. later robust lower-of-methods fair value falls below the frozen Case price.

No LLM is needed to create these.

## 13. Frozen synthetic Portfolio/Risk context

Use the exact QT-CASE-001/002 sandbox:

Capital alternatives:
- CASH: 3%
- CORE_BENCHMARK: 8%

Portfolio:
- new exposure allowed: true
- current candidate weight: 0%
- max candidate weight: 10%
- liquidity: 20%
- reserve: 10%
- incremental downside budget: 2%

Risk:
- max single-asset weight: 10%
- max incremental downside budget: 2%
- max portfolio drawdown: -20%
- current drawdown: -5%
- leverage forbidden
- correlation data not required
- exit-liquidity data not required

This is not the Founder's private portfolio.

## 14. Routing

```text
PIT Evidence
→ P/E valuation
→ owner-cash-flow DCF
→ deterministic Counter-Research
→ Cross-Method Valuation Gate
→ only if gate passes: Portfolio Opportunity Cost
→ only if Portfolio eligible: Independent Risk
```

If the cross-method gate does not pass, Portfolio must return
`NOT_COMPETITIVE` with:

`CROSS_METHOD_VALUATION_GATE_NOT_PASSED`

If required fundamental inputs are missing/negative under the frozen contract,
the experiment may operationally fail. The target may not be swapped.

## 15. AI / consensus / authority

QT-CASE-003:

- model calls: 0
- sell-side target prices: not used
- analyst consensus: not used
- automatic scenario tuning: not used
- private Client context: not used
- target weight: not created
- Committee Decision: not created
- Founder Decision: not created
- DecisionPlan: not created
- PAPER authorization: false
- live execution: false

## 16. Success criteria

### Operational PASS

- live PIT evidence resolves;
- frozen P/E method runs;
- frozen cash-flow DCF runs;
- Counter-Research runs;
- Cross-Method Gate runs;
- Portfolio obeys gate;
- Risk only runs if Portfolio eligible;
- all authority remains false;
- immutable result artifact is produced.

### Operational FAIL

Any required frozen input cannot be satisfied or a contract is violated.

An unattractive, MIXED, REJECTED, or missing-data result is still a legitimate
holdout result and must not cause the target or methodology to be changed.

## 17. Evidence lifecycle

At first successful result:

- save compact JSON/report;
- upload full artifact;
- record exact source SHA/run/artifact;
- convert workflow to frozen manual replay;
- never overwrite the historical result in place.
