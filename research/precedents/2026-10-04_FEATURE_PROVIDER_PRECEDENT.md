# FeatureProvider Precedent — Native Reference

Status: **SANDBOX / PRECEDENT IMPLEMENTED**  
Date: **2026-10-04**  
Related: #111, PR #110  
Disposition: **LEARN_AND_BUILD (interface + reference implementation)**

## Why this precedent exists

The first implementation deliberately does not select a large external framework before the active OSS research finishes.

Instead it implements the smallest durable part of the adoption architecture: a QuanTrade-owned `FeatureProvider` contract, a dependency-free native reference, a provider comparison harness, provenance, and authority-boundary tests.

This proves that future OSS integrations can be evaluated without giving the external framework ownership of QuanTrade semantics.

## Implemented

- `FeatureProvider` protocol
- immutable `ProviderMetadata`
- `FeatureObservation` schema
- deterministic `NativeFeatureProvider`
- identical-input `compare_providers` benchmark seam
- fail-closed input validation
- explicit non-authority flags
- tests for determinism, provenance, replaceability and authority boundaries

## Measurements in the reference provider

The reference intentionally stays small:
- 1-period return
- total return
- SMA(5)
- SMA(20)
- realized volatility

These are not alpha claims and do not create canonical Evidence.

## What this teaches future OSS adoption

An external library should implement the same QuanTrade-facing behavior and emit its own provider/version/license metadata.

A future adapter might use vectorbt, TA-Lib, pandas-ta or another project selected by the research wave. The comparison harness can run the same fixture through native and external providers and expose numerical/semantic differences before promotion.

## Promotion state

```text
DISCOVERED      complete (capability need)
REVIEWED        complete (boundary design)
LICENSE_CLEARED n/a for native reference
SANDBOXED       complete
BENCHMARKED     pending external candidate
SHADOW/PAPER    pending
APPROVED        no
PRODUCTION      no
```

## Authority result

This implementation cannot:
- create canonical Evidence;
- alter RiskPolicy;
- create an investment decision;
- authorize execution.

That is intentional and is part of the precedent.

## Next binding

After the active OSS research selects a suitable feature/indicator candidate:
1. pin its version/revision and license;
2. implement one adapter;
3. run identical fixtures against this reference;
4. record discrepancies;
5. decide ADAPT / DEPEND / REJECT;
6. only then consider PAPER promotion.
