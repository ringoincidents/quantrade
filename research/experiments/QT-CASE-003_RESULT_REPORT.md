# QT-CASE-003 Result — Samsung SDI Holdout Transfer

Status: **OPERATIONAL FAIL / HOLDOUT PRESERVED / NO TRADE AUTHORITY**

## Frozen target

- Samsung SDI
- `KRX:006400`
- Case as-of: `2026-10-05T23:59:59+09:00`
- preregistration: `bf59d2b3b147d2a2864c151ba7751a3b136563ed`

The target was not replaced after failure.

## What happened

The live Open DART provider reached Samsung SDI financial statements after the
provider-level transport/schema fixes.

The frozen QT-CASE-003 P/E contract required:

`DART_ACCOUNT:ifrs-full_BasicEarningsLossPerShare:IS:CURRENT_PERIOD`

for FY2025.

Observed count under the exact frozen key:

**0**

The runner therefore stopped before:

- TTM EPS calculation;
- historical P/E valuation;
- owner-cash-flow DCF comparison;
- Cross-Method Valuation Gate;
- Portfolio review;
- Risk review.

Run:

`37866181333`

Source SHA:

`a02b6700dfa6461ea0d476d46ee7bb0fdcbea526`

## Why the experiment was not "fixed" to pass

The preregistration explicitly prohibited:

- account-name substitution;
- switching the target;
- relaxing the exact metric requirement after seeing the result.

Doing any of those inside QT-CASE-003 would destroy the holdout.

Therefore QT-CASE-003 is recorded as:

**PROCESS_PORTABILITY_FAILURE**

not as an economic rejection of Samsung SDI.

## What the failure teaches

The Investment Office logic transferred farther than a one-company prototype,
but the fundamental semantic layer did not.

A normalized metric contract currently assumes that the same IFRS semantic
account appears under the same DART statement division for every issuer.

The holdout shows that this assumption must be tested explicitly before a
valuation method is declared applicable.

The next development step is not to patch Samsung SDI.

It is to create a reusable **Valuation Method Applicability / Semantic Metric
Gate** that can distinguish:

1. metric truly absent;
2. same IFRS account under another valid statement division;
3. issuer extension / alternate taxonomy;
4. missing period;
5. invalid economic domain (for example non-positive P/E denominator).

That gate must run before valuation and must not fabricate a substitute metric.

## Authority

No valuation, allocation, Committee action, PAPER execution, or live order was
created.
