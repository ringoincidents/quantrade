# QT-CASE-004 Pre-Registration — Hyundai Motor Untouched Issuer Holdout

Status: **FROZEN BEFORE QT-CASE-004 LIVE ECONOMIC VALUES**  
Date: **2026-10-09**  
Mode: **RESEARCH / UNTOUCHED ISSUER HOLDOUT / NO CAPITAL AUTHORITY**

## 1. Purpose

QT-CASE-004 is the first untouched issuer holdout that enters the complete
post-QT-CASE-003 process from the beginning:

```text
PIT Evidence
→ Semantic Metric Applicability
→ Valuation Method Applicability
→ P/E + Owner-Cash-Flow DCF
→ Cross-Method Valuation Gate
→ Portfolio Opportunity Cost
→ Independent Risk
```

The experiment tests **process portability**, not whether the security is a buy.

## 2. Frozen target

- company: Hyundai Motor Company
- KRX code: `005380`
- asset ID: `KRX:005380`
- Case as-of: `2026-10-05T23:59:59+09:00`
- valuation horizon: **365 days**
- currency: **KRW**

Selection was made before querying QT-CASE-004 Case-period economic values.

Selection rationale:

- ticker already existed in the pre-QT-CASE-004 QT-STRAT-005 transfer universe;
- different operating industry from Samsung Electronics and Samsung SDI;
- large KRX filer expected to exercise cross-issuer Open DART semantics;
- target was not discovered by screening current valuation output.

Target replacement after observing the result is prohibited.

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

## 4. Corporate identifier rule

The DART `corp_code` is an infrastructure identifier, not an economic input.

QT-CASE-004 must resolve it from the official Open DART corporation-code source
after this preregistration.

If the resolver is unavailable after bounded retry, the experiment fails
operationally and is not retargeted.

Any resolved `corp_code` must be verified against returned live filing
`stock_code = 005380`.

## 5. Semantic Metric Applicability

No issuer-specific statement placement is assumed.

### EPS

Exact IFRS account:

`ifrs-full_BasicEarningsLossPerShare`

Allowed statement divisions:

`IS | CIS`

Required:

- FY2022-FY2025 `CURRENT_PERIOD`
- 2025-H1 and 2026-H1 `CURRENT_YTD`

### Profit attributable to owners

Exact IFRS account:

`ifrs-full_ProfitLossAttributableToOwnersOfParent`

Allowed statement divisions:

`IS | CIS`

Required:

- FY2022-FY2025 `CURRENT_PERIOD`
- 2025-H1 and 2026-H1 `CURRENT_YTD`

### Operating cash flow

Exact IFRS account:

`ifrs-full_CashFlowsFromUsedInOperatingActivities`

Allowed statement division:

`CF`

### PP&E purchases

Exact IFRS account:

`ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities`

Allowed statement division:

`CF`

### Intangible purchases

Exact IFRS account:

`ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities`

Allowed statement division:

`CF`

### Parent equity

Exact IFRS account:

`ifrs-full_EquityAttributableToOwnersOfParent`

Allowed statement division:

`BS`

Semantic statuses:

- `READY`
- `MISSING`
- `AMBIGUOUS`

No account-name fallback, issuer-specific alias guessing, or post-result
statement substitution is allowed.

## 6. Valuation Method Applicability

### P/E method

Required:

- semantic status `READY`;
- FY2022-FY2025 annual basic EPS > 0;
- FY2025 annual basic EPS > 0;
- reconstructed TTM EPS > 0.

TTM EPS:

```text
FY2025 basic EPS
+ 2026-H1 YTD basic EPS
- 2025-H1 YTD basic EPS
```

If any required domain condition fails:

`PE = NOT_APPLICABLE`

No substitute valuation method is selected.

### Owner-cash-flow DCF

Required:

- semantic status `READY`;
- FY2025 parent profit > 0;
- FY2025 basic EPS > 0;
- implied basic shares > 0;
- reconstructed TTM owner-cash-flow proxy > 0.

Implied basic shares:

```text
FY2025 profit attributable to owners
/
FY2025 basic EPS
```

Owner-cash-flow proxy:

```text
Operating Cash Flow
- PP&E Purchases
- Intangible Purchases
```

TTM:

```text
FY2025 proxy
+ 2026-H1 proxy
- 2025-H1 proxy
```

If a domain condition fails:

`OWNER_CASH_FLOW_DCF = NOT_APPLICABLE`

No substitute method is selected.

## 7. Frozen P/E valuation

Only if P/E applicability is `READY`.

For each FY2022-FY2025:

```text
Historical P/E = year-end close / annual basic EPS
```

No year may be deleted as an outlier.

Percentiles:

- P25
- P50
- P75

Scenario probabilities:

- Bear 25%
- Base 50%
- Bull 25%

Bear:
- TTM EPS factor: 80%
- multiple: P25

Base:
- TTM EPS factor: 100%
- multiple: P50

Bull:
- TTM EPS factor: 120%
- multiple: P75

Required return:

**15%**

## 8. Frozen Owner-Cash-Flow DCF

Only if DCF applicability is `READY`.

Explicit horizon:

**5 years**

Bear — 25%:
- starting factor: 0.80
- annual growth: 0%
- terminal growth: 0%
- discount rate: 10%

Base — 50%:
- starting factor: 1.00
- annual growth: 3%
- terminal growth: 2%
- discount rate: 10%

Bull — 25%:
- starting factor: 1.20
- annual growth: 5%
- terminal growth: 3%
- discount rate: 10%

No parameter may change after observing QT-CASE-004.

## 9. Cross-Method rule

Cross-Method Valuation Gate runs only if:

- P/E = `READY`
- Owner-Cash-Flow DCF = `READY`

Otherwise:

`INCOMPLETE_REQUIRED_METHODS`

and Portfolio/Risk are not invoked.

If both are READY, the existing reusable gate applies.

Classification:

- `CROSS_METHOD_CONFIRMED`
- `CROSS_METHOD_MIXED`
- `CROSS_METHOD_REJECTED`

Robust scenario value:

```text
min(P/E fair value, DCF fair value)
```

Portfolio review requires:

`valuation_gate_passed = true`

## 10. Frozen Counter-Research

Run only when both valuation methods are applicable.

Same rules as QT-CASE-002:

- P/E max/min dispersion > 4.0
  → `HIGH_MULTIPLE_REGIME_DISPERSION`
- any annual owner-cash-flow proxy <= 0
  → `NEGATIVE_OWNER_CASH_FLOW_YEAR`
- FY2022-FY2025 median cash conversion < 0.75
  → `WEAK_MEDIAN_CASH_CONVERSION`
- TTM cash conversion < 0.75
  → `WEAK_TTM_CASH_CONVERSION`
- current P/B > historical P75
  → `CURRENT_PB_ABOVE_HISTORICAL_P75`

P/B remains Counter-Research only.

## 11. Frozen synthetic Portfolio/Risk context

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

This is synthetic research context, not the Founder's private portfolio.

## 12. Routing

```text
PIT Evidence
→ Semantic Gate
→ Method Applicability Gate
→ if both READY:
    P/E + DCF
    → Counter-Research
    → Cross-Method Gate
    → if valuation gate passes:
        Portfolio
        → if Portfolio eligible:
            Risk
```

No downstream department may be invoked merely to rationalize a failed
upstream gate.

## 13. Valid outcomes

All of the following are legitimate holdout outcomes:

- semantic `MISSING`;
- semantic `AMBIGUOUS`;
- valuation method `NOT_APPLICABLE`;
- `INCOMPLETE_REQUIRED_METHODS`;
- `CROSS_METHOD_REJECTED`;
- `CROSS_METHOD_MIXED`;
- `CROSS_METHOD_CONFIRMED`;
- Portfolio rejection;
- Risk rejection/pass.

The target and methodology must not be changed because of an inconvenient
result.

## 14. AI / consensus / authority

QT-CASE-004:

- model calls: 0
- analyst consensus: not used
- sell-side target prices: not used
- automatic scenario tuning: not used
- private Client context: not used
- target weight: not created
- real Client Portfolio Proposal: not created
- Committee Decision: not created
- Founder Decision: not created
- DecisionPlan: not created
- PAPER authorization: false
- live execution: false

## 15. Evidence lifecycle

At the first terminal result:

- save compact JSON/report;
- upload full artifact;
- record exact source SHA/run/artifact;
- convert the workflow to a manual frozen replay;
- never overwrite the historical result in place.
