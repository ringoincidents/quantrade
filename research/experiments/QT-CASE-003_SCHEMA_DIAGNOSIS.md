# QT-CASE-003 Schema Diagnosis — Same IFRS Account, Different DART Statement Division

Status: **DIAGNOSED / METHOD NOT RETROFITTED INTO QT-CASE-003**  
Date: **2026-10-09**  
Probe run: **37866367211**

## Finding

QT-CASE-003 failed because the preregistered key required:

`DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:IS:CURRENT_PERIOD`

for Samsung SDI FY2025.

The read-only schema probe showed that the IFRS account is present, but DART
places it under:

`CIS`

instead of:

`IS`.

Observed identity:

- account ID: `ifrs-full_BasicEarningsLossPerShare`
- account name: `보통주 기본주당손익`
- statement division: `CIS`
- statement: `포괄손익계산서`

The same pattern is present in:

- FY2025 annual;
- 2025 half-year;
- 2026 half-year.

The parent-profit account:

`ifrs-full_ProfitLossAttributableToOwnersOfParent`

is also under `CIS`.

By contrast:

- operating cash flow: `CF`
- PP&E purchases: `CF`
- intangible purchases: `CF`
- parent equity: `BS`

appear under the expected statement families.

The probe emitted **no financial amounts**.

## Meaning

QT-CASE-003 was not blocked because basic EPS was economically unavailable.

It was blocked because QuanTrade's first normalized contract confused:

> semantic accounting identity

with:

> one issuer-specific statement placement.

This is a portability defect in the semantic layer.

## Correct response

Do not change QT-CASE-003.

Its failure remains valid under its frozen contract.

Instead, future Cases must declare semantic requirements such as:

```text
account_id = ifrs-full_BasicEarningsLossPerShare
allowed statement divisions = IS | CIS
amount suffix = CURRENT_PERIOD
```

Then the system must:

1. query every predeclared normalized candidate;
2. accept exactly one matching observation;
3. preserve the actual statement division;
4. fail if zero matches;
5. fail if multiple allowed matches are simultaneously present;
6. never fall back to account-name guessing.

## Implementation

Added:

`quantrade/capabilities/fundamental_semantics.py`

Core concepts:

- `SemanticMetricRequirement`
- `SemanticMetricApplicabilityInput`
- `SemanticMetricApplicabilityArtifact`

Statuses:

- `READY`
- `MISSING`
- `AMBIGUOUS`

The gate explicitly records:

- account-name fallback used = false;
- issuer-specific alias inference used = false;
- allowed statement divisions must be declared before resolution.

## Governance consequence

A valuation method should not reach valuation arithmetic until its required
semantic metrics are `READY`.

The proper future chain is:

```text
PIT provider
→ Semantic Metric Applicability
→ Valuation Method Applicability
→ method-specific valuation
→ Cross-Method Valuation Gate
→ Portfolio
```

This prevents both false missing-data failures and ad-hoc post-result metric
substitution.
