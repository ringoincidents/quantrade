# QT-CASE-001 Pre-Registration — Samsung Electronics Real Investment Case Golden Run

Status: **FROZEN BEFORE FIRST CASE RESULT**  
Date: **2026-10-08**  
Mode: **RESEARCH / PAPER-ONLY / NO CAPITAL AUTHORITY**

## 1. Question

Can QuanTrade execute a real, point-in-time, auditable buy-side-style Investment
Case for Samsung Electronics using live public company data and a deterministic
valuation framework, without collapsing research attractiveness into a trade
decision?

This is the first real-company Golden Run of the Investment Office capability
line.

The experiment succeeds operationally if the frozen process runs correctly and
preserves provenance / authority boundaries.

**Finding an attractive investment is not required for experiment success.**

## 2. Frozen security and Case time

- security: Samsung Electronics common stock
- KRX code: `005930`
- asset ID: `KRX:005930`
- Case as-of: `2026-10-05T23:59:59+09:00`
- valuation horizon: **365 days**
- currency: **KRW**

The target security will not be changed after observing the result.

## 3. Frozen external sources

### Fundamentals

Provider:

**Financial Supervisory Service Open DART**

QuanTrade provider:

`DartFundamentalObservationProvider`

Required fiscal-period window:

`2022-01-01 .. 2026-06-30`

Only observations whose publication timestamp is available by the frozen Case
as-of may be selected.

If exact historical reconstruction is blocked by a later correction and the
provider raises `DartPointInTimeUnavailable`, the experiment stops. It will
not substitute a present-day value.

### Price

Provider:

Naver Finance historical daily endpoint already used by the Strategy Research
Golden Runs.

Required price observations:

- final KRX trading close on or before each calendar year-end for
  2022, 2023, 2024, 2025;
- final trading close on or before the Case date 2026-10-05.

Price data after the Case date is forbidden.

## 4. Frozen accounting metric

Primary earnings metric:

`ifrs-full_BasicEarningsLossPerShare`

normalized by the current DART adapter as:

`DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:IS:CURRENT_PERIOD`

and, where required:

`DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:IS:CURRENT_YTD`

### Current TTM EPS

Frozen formula:

```text
TTM EPS at 2026-H1
=
FY2025 EPS
+ 2026-H1 YTD EPS
- 2025-H1 YTD EPS
```

Required inputs:

- FY2025 CURRENT_PERIOD EPS;
- 2026-06-30 CURRENT_YTD EPS;
- 2025-06-30 CURRENT_YTD EPS.

If any required EPS observation is absent, non-positive, ambiguous, or not
available by Case as-of, valuation stops with missing-data status.

No substitute analyst EPS estimate is allowed.

## 5. Frozen historical valuation anchor

For fiscal years:

- 2022
- 2023
- 2024
- 2025

calculate:

```text
historical P/E
=
last trading close on/before fiscal year-end
/
reported full-year basic EPS
```

This is an **ex-post historical valuation anchor calculated at the 2026 Case
date**, not a claim that each final annual EPS value was known on the historical
year-end date.

Only positive annual EPS values are eligible.

All four years are required. No year may be removed because its multiple looks
unusual.

### Percentiles

Sort the four historical P/E values.

Use deterministic linear interpolation at:

- P25
- P50
- P75

with index:

```text
(n - 1) * percentile
```

and linear interpolation between adjacent observations.

No post-result winsorization or outlier removal is allowed.

## 6. Frozen valuation scenarios

The first Golden Run intentionally uses a simple transparent P/E framework
rather than DCF.

Current TTM EPS is the earnings anchor.

### Bear

- probability: **25%**
- EPS: **80% of frozen TTM EPS**
- valuation multiple: **historical P25 P/E**

### Base

- probability: **50%**
- EPS: **100% of frozen TTM EPS**
- valuation multiple: **historical P50 P/E**

### Bull

- probability: **25%**
- EPS: **120% of frozen TTM EPS**
- valuation multiple: **historical P75 P/E**

Scenario fair value:

```text
scenario EPS * scenario P/E
```

No scenario parameter may change after the first result is observed.

## 7. Frozen economic hurdle

Required return:

**15.0%**

The existing Investment Case Economics capability will calculate:

- probability-weighted fair value;
- expected return;
- expected excess over hurdle;
- downside/upside;
- probability of loss;
- probability of meeting the hurdle;
- scenario dispersion.

Passing the hurdle does **not** authorize a purchase.

## 8. Frozen Thesis Contract

The Golden Run creates a deterministic Thesis Contract.

### Observation set

At minimum:

- FY2025 basic EPS;
- 2025-H1 YTD basic EPS;
- 2026-H1 YTD basic EPS;
- frozen TTM EPS calculation;
- 2022-2025 historical P/E values;
- Case-date market close.

### Explicit assumption

```text
The frozen TTM EPS is a reasonable central one-year earnings anchor.
```

This is an Assumption, not Evidence.

### Thesis Claim

```text
At the frozen Case price, the probability-weighted value produced by the
pre-registered earnings/multiple scenarios either does or does not provide
sufficient expected return versus the 15% hurdle.
```

The result direction is determined by arithmetic; no wording change after the
result is allowed to turn a failed hurdle into a positive Thesis.

### CounterClaim

```text
Samsung's earnings and market valuation multiple are cyclical/regime-sensitive;
historical P/E dispersion and recent EPS changes may make the TTM/multiple
anchor unstable.
```

CounterClaim basis must point to the same frozen observed EPS/P-E history.

### Falsification condition

Primary condition:

```text
At a later review, reconstructed TTM basic EPS falls below 80% of the frozen
QT-CASE-001 TTM EPS.
```

Evaluation horizon:

**next two reported quarters / until the 365-day valuation horizon, whichever
comes first.**

This run defines the condition but does not evaluate future outcome.

## 9. Frozen Portfolio sandbox context

This Golden Run does **not** use the Founder's private holdings or personal
financial values.

It uses an explicitly synthetic Portfolio context solely to exercise the
program path.

Capital alternatives:

- CASH expected return: **3.0%**
- CORE_BENCHMARK expected return: **8.0%**

Constraint snapshot:

- mandate allows new exposure: true
- current candidate weight: **0%**
- maximum candidate weight: **10%**
- current liquidity: **20%**
- minimum liquidity reserve: **10%**
- available incremental downside budget: **2%**

These values are experiment fixtures, not Client recommendations.

## 10. Frozen Risk sandbox context

Risk policy:

- max single-asset weight: **10%**
- max incremental downside budget: **2%**
- max portfolio drawdown: **-20%**
- leverage allowed: **false**
- correlation data required: **false**
- liquidity/exit-days data required: **false**

Risk state:

- current candidate weight: **0%**
- current portfolio drawdown: **-5%**

Candidate risk profile:

- worst-case return = Investment Case Bear scenario return
- leverage = false
- correlation = unavailable
- estimated exit days = unavailable

Because correlation/liquidity are explicitly not required by this frozen sandbox
policy, their absence cannot be interpreted as evidence of low risk.

## 11. Frozen Portfolio/Risk routing

If Investment Case expected-return hurdle fails:

- continue producing the Case artifact;
- Portfolio may return NOT_COMPETITIVE;
- do not manufacture a positive downstream outcome.

If the Case does not beat the best explicit capital alternative:

- Portfolio result = NOT_COMPETITIVE.

If deterministic capital headroom is zero:

- Portfolio result = NOT_COMPETITIVE.

Risk runs only if Portfolio status is:

`ELIGIBLE_FOR_PORTFOLIO_REVIEW`.

If Portfolio is not eligible, Risk result remains null/not invoked.

## 12. AI / analyst / consensus policy

For QT-CASE-001:

- model calls: **0**
- analyst target-price provider: **not used**
- external sell-side consensus: **not used**
- automatic scenario probability generation: **not used**

The purpose is to validate the deterministic organizational substrate before
adding expensive or subjective research.

## 13. No authority

This experiment may not:

- create a target weight;
- create a real Client Portfolio Proposal;
- alter a Risk policy;
- create a Founder Decision;
- create a DecisionPlan;
- authorize PAPER execution;
- authorize live execution;
- call a broker.

All outputs are research artifacts.

## 14. Frozen success/failure interpretation

### Operational PASS

All of the following:

- DART live provider authenticates;
- PIT evidence selection succeeds;
- required EPS observations exist;
- price observations exist;
- four historical P/E anchors are calculated;
- scenario economics run;
- Thesis Contract compiles;
- Portfolio routing follows frozen rules;
- Risk runs only when eligible;
- authority flags remain false;
- immutable result artifact is produced.

### Operational FAIL

Any required item above cannot be satisfied.

### Investment interpretation

Possible economic outcomes are all valid experiment results:

- HURDLE_CLEARED
- HURDLE_NOT_CLEARED
- MISSING_DATA

No outcome may cause the methodology to be changed inside QT-CASE-001.

## 15. Evidence storage policy

To avoid repeating the oversized raw-data commits seen in QT-STRAT-004/005:

Repository stores only:

- preregistration;
- compact result JSON;
- compact Markdown result report;
- source hashes / receipt IDs / selected Evidence references.

The full live provider payload is uploaded as an immutable GitHub Actions
artifact and is not committed wholesale to the repository.
