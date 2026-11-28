# QT-CASE-002 Result Analysis — Why P/E Upside Did Not Survive Cash-Flow Review

Status: **RECORDED AFTER SUCCESSFUL GOLDEN RUN**  
Date: **2026-10-09**  
Golden Run: **37861826319**  
Evidence commit: **3762df30f6a399cf3c198076f7fd489b95bcfb2b**

## 1. Executive result

QT-CASE-001 and QT-CASE-002 evaluated the same Samsung Electronics Case price:

`276,000 KRW`

at the same frozen Case as-of.

The two valuation methods did not agree.

### QT-CASE-001 — P/E method

- weighted fair value: **362,640 KRW**
- expected return: **+31.39%**
- 15% hurdle: **CLEARED**

### QT-CASE-002 — cash-flow DCF

- weighted fair value: **278,746 KRW**
- expected return: **+0.995%**
- 15% hurdle: **NOT CLEARED**

Therefore:

`CROSS_METHOD_MIXED`

The preregistered lower-of-two rule bound every Bear/Base/Bull scenario to the
DCF value.

Robust result:

- weighted fair value: **278,746 KRW**
- robust expected return: **+0.995%**
- hurdle: **NOT CLEARED**
- Portfolio sandbox: **NOT_COMPETITIVE**
- Risk: **NOT INVOKED**

## 2. Cash-flow reconstruction

Reported Open DART cash-flow data produced:

### FY2025

- operating cash flow: **85.32T KRW**
- PP&E purchases: **47.52T KRW**
- intangible purchases: **4.63T KRW**
- owner-cash-flow proxy: **33.16T KRW**

### 2025-H1

- owner-cash-flow proxy: **6.74T KRW**

### 2026-H1

- owner-cash-flow proxy: **112.39T KRW**

### Reconstructed TTM

```text
33.16T + 112.39T - 6.74T
= 138.82T KRW
```

Accounting-derived implied basic shares:

**6.701B**

TTM owner-cash-flow proxy per share:

**20,716 KRW**

TTM cash conversion versus reconstructed parent profit:

**92.75%**

The current TTM cash-flow result is strong, but the historical evidence shows
that it is not stable enough to treat as a permanently distributable cash-flow
level without a cycle discount.

## 3. Five-year DCF

The preregistered scenarios produced:

### Bear

- fair value: **165,725 KRW**
- return: **-39.95%**

### Base

- fair value: **275,526 KRW**
- return: **-0.17%**

### Bull

- fair value: **398,207 KRW**
- return: **+44.28%**

Probability-weighted DCF fair value:

**278,746 KRW**

Probability-weighted expected return:

**+0.995%**

Probability of meeting the 15% hurdle:

**25%**

Probability of price loss:

**75%**

## 4. Why QT-CASE-001 looked much more attractive

The first Case relied on:

- current TTM EPS;
- four historical P/E values;
- P25/P50/P75 multiples.

Those historical P/E values were:

- 2022: **6.86x**
- 2023: **36.84x**
- 2024: **10.75x**
- 2025: **18.15x**

Max/min dispersion:

**5.37x**

The 2023 high multiple materially increases the upper part of the historical
multiple distribution and therefore the P/E Bull valuation.

QT-CASE-002 does not delete 2023 as an outlier because the methodology was
frozen before the result.

Instead it exposes the disagreement through an independent cash-flow method.

## 5. Deterministic Counter-Research

QT-CASE-002 produced:

`MATERIAL_COUNTER_EVIDENCE`

Flags:

- `HIGH_MULTIPLE_REGIME_DISPERSION`
- `NEGATIVE_OWNER_CASH_FLOW_YEAR`
- `WEAK_MEDIAN_CASH_CONVERSION`
- `CURRENT_PB_ABOVE_HISTORICAL_P75`

### Historical cash conversion

Owner-cash-flow proxy / profit attributable to owners:

- 2022: **16.54%**
- 2023: **-113.29%**
- 2024: **57.23%**
- 2025: **74.92%**

Median:

**36.89%**

2023 owner-cash-flow proxy was negative:

**-16.40T KRW**

This is direct evidence that accounting earnings and owner-cash-flow
availability can diverge sharply in a capital-intensive semiconductor cycle.

### P/B sanity check

Historical P/B:

- 2022: **1.07x**
- 2023: **1.49x**
- 2024: **0.91x**
- 2025: **1.89x**

Historical P75:

**1.59x**

Current Case P/B:

**4.36x**

This does not prove overvaluation, but it is a material historical-regime
warning and therefore remains Counter-Research rather than being hidden inside
a single valuation score.

## 6. Organizational consequence

QT-CASE-001 alone would have produced:

`ELIGIBLE_FOR_PORTFOLIO_REVIEW → Risk PASS`

QT-CASE-002 instead produces:

`NOT_COMPETITIVE`

Reasons:

- `CASE_RETURN_HURDLE_NOT_MET`
- `DOES_NOT_BEAT_BEST_CAPITAL_ALTERNATIVE`

The candidate robust expected return was **0.995%**, below both:

- required return hurdle: **15%**
- synthetic CORE alternative: **8%**

Therefore independent Risk was correctly not invoked.

This is an important distinction:

> a downstream department was not asked to justify a Case that failed the
> upstream economic competition test.

## 7. What this proves and what it does not

It proves:

- an independent valuation method can materially change routing;
- Counter-Research can be deterministic and evidence-backed;
- a prior attractive Case can be stopped without rewriting the first result;
- the organizational gate can reject rather than rationalize an earlier
  favorable narrative.

It does **not** prove:

- Samsung is overvalued;
- the DCF assumptions are objectively correct;
- the P/E method is useless;
- the DCF method is superior in all regimes;
- QuanTrade has alpha.

The correct conclusion is:

> the current Samsung Case is **valuation-method-sensitive** and therefore
> insufficiently robust for Portfolio review under the frozen 15% hurdle.

## 8. Product rule derived from the experiment

Future Investment Cases should not allow a single favorable valuation method to
silently become Portfolio eligibility.

A reusable Cross-Method Valuation Gate should require:

1. common Case price and hurdle;
2. aligned scenario IDs/probabilities;
3. explicit method-specific outputs;
4. visible method disagreement;
5. conservative robust aggregation;
6. no method automatically receiving investment authority.

This rule is implemented after QT-CASE-002 for future Cases. It does not alter
the historical QT-CASE-002 result.
