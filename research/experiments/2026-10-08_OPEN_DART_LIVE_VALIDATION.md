# Open DART Live Validation — 2026-10-08

Status: **LIVE NETWORK VERIFIED / READ-ONLY / NO CAPITAL AUTHORITY**

## 1. Trigger

Repository secret:

`OPEN_DART_API_KEY`

was configured by the Founder and the existing read-only GitHub Actions probe
was re-run against Open DART.

No API key value is persisted in source, artifacts, provider metadata, or logs.
GitHub Actions masks the secret.

## 2. First live run — useful failure

Workflow:

`Open DART Fundamental Probe`

Run:

`37768749685`

The run confirmed all of the following before failing:

- `OPEN_DART_API_KEY` was configured;
- the API key was accepted by Open DART;
- the standard GitHub-hosted runner reached Open DART successfully;
- real Samsung Electronics (`KRX:005930`) financial-statement data was returned.

The failure was **not** authentication, IP allowlisting, or DART status `012`.

It exposed a real normalization defect:

```text
DartProviderError:
ambiguous duplicate financial metric:
DART:20250515001922:CFS:SCE:
DART_ACCOUNT:dart_ChangesInConsolidatedCompanies:CURRENT_PERIOD
```

Cause:

Open DART may return multiple XBRL dimensional/member rows sharing the same
account ID, statement division, and amount field while differing in
`account_detail`.

The first adapter version intentionally failed closed rather than selecting or
summing them.

## 3. Sustainable fix

The provider contract was extended to preserve:

`dimension_detail`

For dimensional rows, the normalized metric identity now includes a
deterministic SHA-256-derived dimension discriminator:

```text
...:DIM:<12-hex>
```

The raw DART `account_detail` remains preserved separately.

This means:

- distinct XBRL dimensions remain distinct observations;
- no arbitrary row selection occurs;
- no silent summation occurs;
- exact duplicate identities still fail closed.

A regression test now creates two rows with the same account ID but different
`account_detail` values and verifies both survive with separate metric keys.

The full Investment Office capability regression remained green after the fix.

## 4. Live success

Latest live run:

`37769222168`

Result:

**SUCCESS**

Target:

- asset: `KRX:005930`
- fiscal period range: `2025-01-01 .. 2025-12-31`
- Case as-of: `2026-10-05T23:59:59+09:00`

Provider:

`OPEN_DART`

Live result:

- **983 point-in-time-selected observations**
- **0 excluded future observations**
- artifact uploaded successfully
- API key persisted: **false**
- model called: **false**
- canonical Evidence created: **false**
- Portfolio Proposal created: **false**
- Committee Decision created: **false**
- execution authorized: **false**
- live order possible: **false**

Actions artifact:

- name: `open-dart-fundamental-probe`
- artifact ID: `11547247557`

## 5. Confirmed filing coverage

The live artifact contains four 2025 fiscal-period filings:

- 2025-03-31 — receipt `20250515001922`
- 2025-06-30 — receipt `20250814003156`
- 2025-09-30 — receipt `20251114002447`
- 2025-12-31 — receipt `20260310002820`

Publication timestamps are stored conservatively as end-of-day Korea time
because the disclosure-search API exposes filing date precision.

No selected row in this probe was marked as a restatement.

## 6. Sample live observations

Examples from the artifact include:

### 2025-12-31

- total assets:
  `566,942,110,000,000 KRW`
- total liabilities:
  `130,621,773,000,000 KRW`
- revenue:
  `333,605,938,000,000 KRW`
- operating income:
  `43,601,051,000,000 KRW`

These are provider observations, not an Investment Thesis or valuation.

## 7. Dimensional evidence observed in production data

The live artifact contains **413 observations with non-empty dimensional
detail**.

Example categories include Statement of Changes in Equity rows where the same
account ID appears under different equity/member dimensions.

This validates that preserving `account_detail` was necessary rather than a
synthetic edge case.

## 8. Fixed-IP conclusion

For the current personal Open DART key and current read-only request path:

> **A fixed outbound IP is not required in the observed live configuration.**

A standard GitHub-hosted Actions runner successfully authenticated and
retrieved real Open DART data.

This does not claim Open DART can never apply IP restrictions to another
account/configuration, but QuanTrade has no current need to purchase or operate
a static outbound-IP gateway for this integration.

## 9. Workflow concurrency hardening

Multiple code pushes briefly created overlapping live probes while the provider
was being fixed.

The workflow now includes a concurrency group with:

`cancel-in-progress: true`

so future probes on the same branch are serialized/cancel superseded runs
rather than generating unnecessary duplicate external requests.

## 10. Next step

The external data blocker for the first real Investment Case Golden Run is now
cleared.

Before any real Case is run, freeze/preregister:

- target security;
- Case as-of;
- evidence cutoff;
- valuation method;
- Scenario assumptions/probabilities;
- benchmark/capital alternatives;
- Client/Portfolio/Risk context;
- falsification conditions;
- success/failure interpretation.

The Golden Run must remain research/PAPER-only and must not create a live order.
