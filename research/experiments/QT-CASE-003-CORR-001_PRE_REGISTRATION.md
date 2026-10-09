# QT-CASE-003-CORR-001 Pre-Registration — Semantic Portability Correction

Status: **FROZEN BEFORE CORRECTIVE ECONOMIC VALUES ARE USED**  
Date: **2026-10-09**  
Mode: **CORRECTIVE RESEARCH / NOT A HOLDOUT / NO CAPITAL AUTHORITY**

## Purpose

QT-CASE-003 remains an immutable failed holdout.

This corrective experiment tests the semantic-layer fix discovered after that
failure.

It does **not** replace QT-CASE-003 and must not be described as independent
holdout evidence.

## Known before correction

Known:

- Samsung SDI is the target;
- the exact IFRS basic-EPS account exists under DART `CIS`, not `IS`;
- parent-profit also uses `CIS`;
- the schema probe emitted no financial amounts.

The correction changes only semantic statement-placement handling.

It does not change:

- target;
- Case date;
- valuation scenario probabilities;
- P/E percentile method;
- DCF growth/discount assumptions;
- 15% hurdle;
- Counter-Research thresholds;
- Portfolio/Risk sandbox.

## Semantic rules

For:

- `ifrs-full_BasicEarningsLossPerShare`
- `ifrs-full_ProfitLossAttributableToOwnersOfParent`

allowed statement divisions are preregistered as:

`IS | CIS`

For cash-flow accounts:

`CF`

For parent equity:

`BS`

Selection requires exactly one match per semantic requirement/period.

Zero matches:

`MISSING`

Multiple allowed matches:

`AMBIGUOUS`

No account-name fallback or issuer-specific alias inference is allowed.

## Method applicability

Before any valuation arithmetic:

### P/E method

Must have semantic status `READY`.

All required FY2022-FY2025 annual EPS, FY2025 EPS, 2025-H1 YTD EPS, and
2026-H1 YTD EPS used by the frozen formulas must be positive.

If not:

`PE = NOT_APPLICABLE / NON_POSITIVE_EPS`

No substitute P/B, EV/EBITDA, or analyst multiple is selected.

### Owner-cash-flow DCF

Must have semantic status `READY`.

Required domain conditions:

- FY2025 parent profit > 0;
- FY2025 basic EPS > 0;
- implied basic shares > 0;
- reconstructed TTM owner-cash-flow proxy > 0.

If not:

`OWNER_CASH_FLOW_DCF = NOT_APPLICABLE`

No substitute method is selected.

## Cross-method rule

Cross-Method Valuation Gate is invoked only if both required methods are
`READY`.

If either method is not applicable:

`CROSS_METHOD_STATUS = INCOMPLETE_REQUIRED_METHODS`

and Portfolio/Risk are not invoked.

This is an applicability result, not an economic BUY/SELL conclusion.

## If both methods are READY

Use exactly the QT-CASE-003 frozen economic methodology:

- P/E Bear/Base/Bull = 25/50/25;
- EPS factors = 80/100/120%;
- historical P25/P50/P75;
- DCF 5 years;
- DCF Bear = 0%/0%/10%;
- DCF Base = 3%/2%/10%;
- DCF Bull = 5%/3%/10%;
- 15% hurdle;
- lower-of-methods cross-check;
- same Counter-Research;
- same synthetic Portfolio/Risk context.

## Success

Operational PASS means the system classifies semantic and method applicability
without ad-hoc substitution or crashing.

A result in which one or both valuation methods are NOT_APPLICABLE is a valid
corrective result.

## Authority

Always false:

- target weight;
- real Client Portfolio Proposal;
- Committee Decision;
- Founder Decision;
- DecisionPlan;
- PAPER authorization;
- execution authorization;
- live order.
