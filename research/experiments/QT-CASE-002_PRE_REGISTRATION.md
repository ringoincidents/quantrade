# QT-CASE-002 Pre-Registration — Samsung Cash-Flow & Cross-Method Robustness Case

Status: **FROZEN BEFORE QT-CASE-002 CASH-FLOW RESULT**  
Date: **2026-10-09**  
Mode: **RESEARCH / PAPER-ONLY / NO CAPITAL AUTHORITY**

## 1. Purpose

QT-CASE-001 produced a hurdle-cleared Samsung Electronics P/E-based result, but
also exposed large historical multiple dispersion.

QT-CASE-002 is a **known-case robustness challenge**, not an untouched
independent validation.

Known before this preregistration:

- QT-CASE-001 price/economics/result;
- 2022-2025 annual EPS and historical P/E values;
- the successful 2025 Open DART provider artifact;
- the fact that Samsung Open DART statements contain standard operating cash
  flow and capital-expenditure XBRL tags.

Not yet used to choose QT-CASE-002 methodology:

- 2026-H1 operating cash flow;
- 2026-H1 PP&E purchases;
- 2026-H1 intangible purchases;
- the resulting TTM owner-cash-flow proxy;
- the resulting DCF valuation;
- the resulting cross-method robust valuation.

No method parameter may change after those results are observed.

## 2. Frozen security and Case time

Same comparison Case as QT-CASE-001:

- Samsung Electronics common stock
- KRX code: `005930`
- asset ID: `KRX:005930`
- Case as-of: `2026-10-05T23:59:59+09:00`
- Case price: the final KRX trading close on or before the Case date
- valuation horizon: 365 days
- currency: KRW

QT-CASE-001 remains immutable.

## 3. Frozen point-in-time data source

Fundamentals:

**Financial Supervisory Service Open DART**

Required report families:

- annual report `11011`
- half-year report `11012`

Required fiscal window:

`2022-01-01 .. 2026-06-30`

The verified Samsung identifier cache:

`005930 → 00126380`

may be reused. It is a static provider identifier, not an economic input.

A later correction that prevents exact historical reconstruction remains a
fail-closed condition.

## 4. Frozen cash-flow account identities

Accepted exact Open DART metric keys:

### Operating cash flow

`DART_ACCOUNT:ifrs-full_CashFlowsFromUsedInOperatingActivities:CF:CURRENT_PERIOD`

### PP&E capital expenditure

`DART_ACCOUNT:ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities:CF:CURRENT_PERIOD`

### Intangible capital expenditure

`DART_ACCOUNT:ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities:CF:CURRENT_PERIOD`

### Profit attributable to owners

Annual:

`DART_ACCOUNT:ifrs-full_ProfitLossAttributableToOwnersOfParent:IS:CURRENT_PERIOD`

Half-year YTD:

`DART_ACCOUNT:ifrs-full_ProfitLossAttributableToOwnersOfParent:IS:CURRENT_YTD`

### Basic EPS

Annual:

`DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:IS:CURRENT_PERIOD`

### Parent equity

`DART_ACCOUNT:ifrs-full_EquityAttributableToOwnersOfParent:BS:CURRENT_PERIOD`

No account-name substitution is allowed inside QT-CASE-002.

## 5. Frozen owner-cash-flow proxy

This is deliberately named a **proxy**, not canonical FCFE.

For any annual or half-year cumulative period:

```text
Owner Cash Flow Proxy
=
Operating Cash Flow
- PP&E Purchases
- Intangible Purchases
```

All three inputs are treated as positive expenditure magnitudes where DART
reports the purchase lines as positive numbers.

The proxy does not add financing flows, acquisition spending, asset-sale
proceeds, or working-capital normalization beyond what is already embedded in
reported operating cash flow.

## 6. Frozen TTM cash-flow bridge

```text
TTM Owner Cash Flow Proxy
=
FY2025 Owner Cash Flow Proxy
+ 2026-H1 Owner Cash Flow Proxy
- 2025-H1 Owner Cash Flow Proxy
```

All three components are required.

If the TTM proxy is non-positive, DCF valuation fails closed with
`NON_POSITIVE_TTM_OWNER_CASH_FLOW`.

## 7. Frozen implied basic-share denominator

To translate aggregate cash flow to a per-share basis:

```text
Implied Basic Shares
=
FY2025 Profit Attributable to Owners
/
FY2025 Basic EPS
```

Both inputs must be positive and unique.

This denominator is an accounting-derived approximation and must be labeled as
such. It is not a share-registry count.

```text
TTM Owner Cash Flow Per Share
=
TTM Owner Cash Flow Proxy
/
Implied Basic Shares
```

## 8. Frozen 5-year cash-flow DCF scenarios

Discounting is deterministic and uses year-end cash flows.

For each scenario:

```text
FCF_1 = starting cash-flow-per-share * (1 + explicit growth)
FCF_t = FCF_(t-1) * (1 + explicit growth)
Terminal Value at year 5
= FCF_5 * (1 + terminal growth)
  / (discount rate - terminal growth)

DCF Fair Value
= sum(FCF_t / (1+r)^t)
  + Terminal Value / (1+r)^5
```

Explicit horizon: **5 years**

### Bear — probability 25%

- starting cash-flow factor: **0.80**
- explicit annual growth: **0.0%**
- terminal growth: **0.0%**
- discount rate: **10.0%**

### Base — probability 50%

- starting cash-flow factor: **1.00**
- explicit annual growth: **3.0%**
- terminal growth: **2.0%**
- discount rate: **10.0%**

### Bull — probability 25%

- starting cash-flow factor: **1.20**
- explicit annual growth: **5.0%**
- terminal growth: **3.0%**
- discount rate: **10.0%**

The discount rate and growth rates cannot be changed after the result.

## 9. Frozen P/E method

QT-CASE-002 reuses the immutable QT-CASE-001 Bear/Base/Bull P/E fair values.

It does not recompute the P/E methodology with new parameters.

This allows a direct cross-method comparison.

## 10. Frozen cross-method robust valuation

For each corresponding Bear/Base/Bull scenario:

```text
Robust Scenario Fair Value
=
min(
  QT-CASE-001 P/E scenario fair value,
  QT-CASE-002 cash-flow DCF scenario fair value
)
```

Probabilities remain:

- Bear 25%
- Base 50%
- Bull 25%

The robust probability-weighted fair value is then evaluated by the existing
Investment Case Economics module with the same **15% required-return hurdle**.

This lower-of-two rule is intentionally conservative.

No averaging is allowed after seeing method disagreement.

## 11. Frozen cross-method classification

- both P/E and DCF weighted expected returns >= 15%:
  `CROSS_METHOD_CONFIRMED`
- exactly one method >= 15%:
  `CROSS_METHOD_MIXED`
- neither method >= 15%:
  `CROSS_METHOD_REJECTED`

Portfolio review eligibility in QT-CASE-002 additionally requires the **robust
lower-of-two valuation** to clear the existing 15% hurdle.

## 12. Frozen deterministic Counter-Research

QT-CASE-002 must generate counter-evidence rather than only a supporting
valuation narrative.

### A. Historical multiple regime dispersion

Using immutable QT-CASE-001 annual P/E values:

```text
max P/E / min P/E
```

Flag:

`HIGH_MULTIPLE_REGIME_DISPERSION`

if ratio > **4.0**.

This threshold is knowingly motivated by the weakness observed in QT-CASE-001;
therefore it is a follow-up robustness test, not an independent discovery.

### B. Annual cash-conversion history

For each FY2022-FY2025:

```text
Cash Conversion
=
Owner Cash Flow Proxy
/
Profit Attributable to Owners
```

Required years: all four.

Flag:

`NEGATIVE_OWNER_CASH_FLOW_YEAR`

if any annual owner-cash-flow proxy <= 0.

Flag:

`WEAK_MEDIAN_CASH_CONVERSION`

if the median of the four annual cash-conversion ratios < **0.75**.

### C. Current TTM cash conversion

Reconstruct TTM parent profit with the same bridge shape:

```text
TTM Parent Profit
=
FY2025 Parent Profit
+ 2026-H1 Parent Profit YTD
- 2025-H1 Parent Profit YTD
```

Then:

```text
TTM Cash Conversion
=
TTM Owner Cash Flow Proxy / TTM Parent Profit
```

Flag:

`WEAK_TTM_CASH_CONVERSION`

if ratio < **0.75**.

### D. Balance-sheet valuation sanity

For FY2022-FY2025:

```text
BVPS = Parent Equity / Implied Basic Shares
Historical P/B = year-end close / BVPS
```

Current P/B uses the frozen Case price and FY2025 parent equity.

Flag:

`CURRENT_PB_ABOVE_HISTORICAL_P75`

if current P/B > deterministic linear-interpolated historical P75.

P/B is a sanity check only. It does not directly set fair value in QT-CASE-002.

## 13. CounterClaim

The Thesis Contract must contain this adversarial proposition:

> The P/E-based upside from QT-CASE-001 may not survive a cash-flow valuation
> because semiconductor earnings, capital intensity, cash conversion, and
> valuation regimes are cyclical; a high accounting EPS level can coexist with
> weaker distributable owner cash flow.

The CounterClaim must cite the actual frozen counter-research metrics.

No model-generated debate is required.

## 14. Falsification conditions

QT-CASE-002 must contain at least:

### FCF falsifier

At a later review:

```text
reconstructed TTM Owner Cash Flow Proxy
<
80% of frozen QT-CASE-002 TTM Owner Cash Flow Proxy
```

### Cross-method falsifier

At a later review, the robust lower-of-two fair value falls below the frozen
Case price under the same methodology.

Future conditions are defined now and are not evaluated in this run.

## 15. Portfolio/Risk sandbox

Use exactly the same synthetic Portfolio/Risk context as QT-CASE-001 so the
change in routing is attributable to valuation evidence, not changed client
constraints.

- CASH expected return: 3%
- CORE benchmark expected return: 8%
- current candidate weight: 0%
- max candidate weight: 10%
- liquidity: 20%
- minimum reserve: 10%
- incremental downside budget: 2%
- Risk max drawdown: -20%
- current portfolio drawdown: -5%
- leverage: forbidden
- correlation/liquidity data: not required for this sandbox

The sandbox is not the Founder's private portfolio.

## 16. AI / analyst policy

QT-CASE-002:

- model calls: **0**
- analyst target prices: **not used**
- sell-side consensus: **not used**
- automatic scenario generation: **not used**

This experiment tests whether a stronger deterministic buy-side substrate can
challenge its own first valuation.

## 17. Operational success

Operational PASS requires:

- all required live PIT fundamentals resolve;
- FY2022-FY2025 annual cash-flow history exists;
- 2025-H1 / 2026-H1 cash-flow bridges exist;
- implied basic shares calculate;
- 5-year DCF scenarios calculate;
- immutable QT-CASE-001 P/E scenarios load;
- robust lower-of-two valuation calculates;
- deterministic Counter-Research compiles;
- Thesis/CounterClaim/Falsification compile;
- Portfolio/Risk routing follows frozen rules;
- no capital authority is created.

An economically unattractive or mixed result is a valid successful experiment.

## 18. Evidence storage

Repository stores:

- this preregistration;
- compact result JSON;
- result report;
- postmortem if needed.

Full raw live provider data must remain an immutable Actions artifact rather
than another large repository commit.
