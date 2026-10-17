# QT-CASE-001 Operational Postmortem

Status: **RECORDED AFTER SUCCESSFUL GOLDEN RUN**  
Final successful run: **37773930067**  
Evidence commit: **cb6be9108f6b3bf96ac321de1c2cd2fb51e8d023**

## What failed before the successful run

The first real Investment Case exposed provider/runtime issues that synthetic
tests did not reveal.

### 1. Open DART dimensional rows

The initial live provider probe found multiple XBRL rows with the same account
ID but distinct `account_detail` dimensions.

Resolution:

- preserve raw `dimension_detail`;
- derive a deterministic dimension identifier;
- never select or sum dimensional rows silently.

### 2. Truncated Open DART JSON

A Golden Run received an incomplete `fnlttSinglAcntAll.json` body and failed
JSON decoding.

Resolution:

- bounded transport retry;
- bounded backoff;
- fail closed after the retry limit;
- no malformed partial response is accepted.

### 3. Repeated corpCode archive lookup

Repeated/concurrent live workflows caused `corpCode.xml` responses that were
not valid ZIP archives.

A previous successful live probe had already verified:

```text
005930 → DART corp_code 00126380
```

Resolution:

- provider now supports a validated corp-code seed cache;
- QT-CASE-001 uses the previously verified mapping;
- the mapping is an identifier only, not an economic input;
- financial/disclosure data are still retrieved live from Open DART.

### 4. Duplicate external live workflows

Provider code changes were automatically triggering the diagnostic Open DART
probe while Golden Runs were also running.

Resolution:

- diagnostic probe is manual-only;
- Open DART live workflows share one repository-level concurrency group;
- live requests are serialized;
- superseded development pushes no longer create unnecessary diagnostic calls.

### 5. Over-broad report queries

The general provider defaults to all supported periodic report codes.

QT-CASE-001 needs only:

- annual report `11011`;
- half-year report `11012`.

Resolution:

- provider supports explicit bounded report-code sets;
- Golden Run requests only the report families required by its preregistered
  EPS formula.

## Final result

After these fixes, run `37773930067` completed successfully.

Operational conclusion:

> The live-data Investment Case pipeline now survives real Open DART response
> shapes, transient transport defects, static identifier reuse, and external
> request concurrency without weakening point-in-time or authority boundaries.

These fixes are provider/runtime improvements only. They do not alter the
pre-registered QT-CASE-001 valuation methodology or its economic result.
