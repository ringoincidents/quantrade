# Phase IO-3A Result — Point-in-Time Fundamental Evidence Provider Contract

Status: **IMPLEMENTED IN SANDBOX / VERIFIED / PROVIDER-NOT-YET-BOUND**  
Date: **2026-10-05**

## 1. Purpose

The next Investment Office layer needs real fundamental information, but
hard-wiring DART or any single vendor directly into Thesis logic would recreate
the same architectural problem QuanTrade has tried to avoid elsewhere.

IO-3A therefore implements the **provider boundary first**.

The core requirement is point-in-time integrity:

> A historical Case may use only fundamental information that had actually
> been published by that Case's as-of timestamp.

A later restatement/revision must never silently leak into an earlier Case.

## 2. Implemented module

`quantrade/capabilities/fundamental_evidence.py`

The module is:

- deterministic;
- dependency-free;
- model-free;
- read-only;
- non-authoritative.

## 3. Provider contract

New contract:

`FundamentalObservationProvider`

Provider metadata preserves:

- provider ID;
- provider version;
- source/license;
- whether network access is required;
- whether point-in-time data is supported;
- model requirement;
- capital authority.

The contract rejects any provider declaring:

- `model_required = true`
- `capital_authority = true`

Fundamental data acquisition is an information capability, not a capital
decision capability.

## 4. Fundamental Observation schema

Each external value carries:

- observation ID;
- asset ID;
- metric key;
- numeric value;
- unit;
- optional currency;
- fiscal period end;
- published timestamp;
- retrieval timestamp;
- source provider;
- source document ID;
- source reference;
- Evidence reference;
- optional revision ID;
- optional `revision_of`;
- restatement flag;
- normalization method.

This directly addresses the point-in-time blocker already documented in
`Phase3_펀더멘털신호_스펙.md`.

## 5. Point-in-time revision behavior

The deterministic replay provider groups revisions by:

```text
(asset_id, metric_key, fiscal_period_end)
```

For a query at time T:

1. observations published after T are excluded;
2. among versions published by T, the latest available version is selected;
3. excluded future revision IDs are explicitly recorded;
4. revision-resolution history is returned in the artifact.

Example:

```text
2026-02-01 original operating profit = 100
2026-04-01 restated operating profit = 80
```

Historical query:

```text
as_of = 2026-03-01
→ selects 100
→ explicitly excludes future revision 80
```

Later query:

```text
as_of = 2026-05-01
→ selects restated value 80
```

This prevents present-day restatements from contaminating past Investment
Cases.

## 6. Thesis integration

`to_thesis_observation()` converts one selected fundamental observation into
a Thesis Contract Observation.

The adapter preserves:

- observation ID;
- publication timestamp;
- Evidence reference;
- external-evidence source kind.

It does not create canonical Evidence.

The chain is now executable as:

```text
FundamentalObservationProvider
→ PIT-selected Observation
→ Thesis Contract
→ Investment Thesis / Counter-Thesis / Falsification
→ Scenario Economics
```

The Portfolio/Risk/Committee layers remain separate.

## 7. Fail-closed rules

The provider contract rejects:

- missing IDs/source fields;
- non-numeric/non-finite values;
- malformed fiscal dates;
- timezone-naive timestamps;
- publication timestamps after retrieval timestamps;
- self-referential revision links;
- duplicate observation IDs;
- source-provider mismatch;
- duplicate metric keys in a query;
- reversed fiscal-period filters;
- model-dependent provider metadata;
- capital-authority provider metadata.

## 8. Verification

Latest GitHub Actions run:

`37265552770`

Result: **SUCCESS**

Observed test runs:

- Investment Case Economics: **10 passed**
- Thesis Contract: **12 passed**
- Point-in-Time Fundamental Evidence: **11 passed**
- full capability regression suite: **60 passed**
- reference harnesses: success

## 9. What is implemented versus not implemented

### Implemented

- stable provider interface;
- explicit provenance schema;
- point-in-time publication gate;
- deterministic revision selection;
- future-restatement exclusion;
- fiscal-period filtering;
- Thesis Observation adapter;
- authority boundaries;
- static/replay provider for tests and historical fixtures.

### Not yet implemented

- real DART network adapter;
- DART API authentication/secret handling;
- XBRL/account-name normalization;
- company-code/ticker mapping;
- consolidated-vs-separate statement policy;
- unit normalization across filings;
- sell-side consensus provider;
- historical market-universe provider.

## 10. Next bounded step

**IO-3B — DART Fundamental Provider Adapter** is now technically well-defined.

A DART adapter should live behind the existing
`FundamentalObservationProvider` contract and must prove:

1. publication timestamp preservation;
2. source document/report identifiers;
3. revision/restatement handling;
4. metric normalization;
5. no future information leakage;
6. no Client/private data committed to the public repository.

If credentials are required, only the secret name/configuration belongs in the
repository. The actual key must remain outside source control.

After IO-3B, the first real Investment Case Golden Run can be designed without
changing the domain contract.
