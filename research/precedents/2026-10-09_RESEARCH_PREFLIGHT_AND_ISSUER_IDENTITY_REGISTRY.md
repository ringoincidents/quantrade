# Research Preflight + Verified Issuer Identity Registry

Status: **ADOPTED FOR FUTURE QUANTRADE RESEARCH RUNS**  
Date: **2026-10-09**  
Origin: **QT-CASE-004 infrastructure failure**

## 1. Problem

QT-CASE-004 was preregistered as an untouched Hyundai Motor holdout.

The Case did not reach economic data.

The official Open DART corporation-code dependency was unavailable during the
run. The first attempt timed out; a second attempt with bounded retry still did
not receive a valid corporation-code archive.

Open DART simultaneously published an official maintenance notice for:

`2026-10-08 20:00 ~ 2026-10-11 18:00 KST`

including suspension of the Open API corporation-code service.

Official notice:

`https://engopendart.fss.or.kr/`

The correct result was therefore not:

`RESEARCH_FAILED`

but:

`OPERATIONAL_INFRASTRUCTURE_FAILURE`

## 2. New operating rule

Before a material research Mission starts live retrieval, valuation, model work,
or Portfolio routing, it must explicitly check the dependencies required for
that Mission.

The preflight should answer:

```text
Do I have the material?
Is the identifier registered?
Is access allowed?
Did search fail?
Is the external service unavailable?
Is the service in maintenance?
Was a request rate-limited?
Did the provider return an invalid response?
```

These are not interchangeable states.

## 3. Failure taxonomy

Implemented:

`quantrade/capabilities/research_preflight.py`

Dependency statuses include:

- `AVAILABLE`
- `VERIFIED`
- `VERIFIED_CACHE`
- `MISSING`
- `UNREGISTERED`
- `ACCESS_DENIED`
- `SEARCH_FAILED`
- `NETWORK_UNAVAILABLE`
- `MAINTENANCE`
- `RATE_LIMITED`
- `INVALID_RESPONSE`
- `UNKNOWN`

Mapped failure classes preserve distinctions such as:

- `MATERIAL_ABSENT`
- `UNREGISTERED`
- `ACCESS_DENIED`
- `SEARCH_FAILED`
- `EXTERNAL_UNAVAILABLE`
- `UNKNOWN`

A required blocker produces:

`BLOCKED`

and:

`execute_allowed = false`

An optional failed dependency may produce:

`READY_WITH_WARNINGS`

## 4. Governance boundary

Preflight does not grant access.

In particular:

```text
Founder approval
!=
secret permission
!=
tool permission
!=
external service availability
```

The artifact therefore explicitly records:

- generic retry authorized = false;
- Founder approval interpreted as tool permission = false;
- tool permission granted = false;
- secret access granted = false.

A human approval can authorize a governed action, but cannot make unavailable
infrastructure exist.

## 5. Issuer identity is infrastructure

A KRX stock code ↔ Open DART `corp_code` mapping is a stable external
identifier.

It is not:

- valuation Evidence;
- a Thesis;
- a Portfolio signal;
- a trading authorization.

Re-downloading the full corporation-code archive for every Investment Case
creates an unnecessary single point of failure.

## 6. Verified Issuer Identity Registry

Implemented:

`quantrade/capabilities/issuer_identity.py`

Registry:

`quantrade/data/issuer_identity_registry_v1.json`

Core objects:

- `IssuerIdentityRecord`
- `IssuerIdentityRegistry`
- `IssuerIdentityResolution`
- `IssuerIdentityVerification`

Resolution states include:

- `VERIFIED_CACHED_IDENTITY`
- `NOT_REGISTERED`

A cached Open DART identity must contain:

- KRX asset ID;
- six-digit stock code;
- eight-digit DART corp code;
- provenance;
- verification source;
- verification timestamp/reference.

Duplicate asset IDs or duplicate provider external IDs fail closed.

## 7. Seeded verified records

The first registry version contains mappings already supported by prior
QuanTrade run evidence.

### Samsung Electronics

```text
KRX:005930
→ Open DART 00126380
```

Provenance:

- QT-CASE-001 result;
- verified live run `37769222168`.

### Samsung SDI

```text
KRX:006400
→ Open DART 00126362
```

Provenance:

- QT-CASE-003-CORR-001;
- live filing stock-code verification;
- run `37866735828`.

## 8. Cached identity still requires fail-closed checking

A registry mapping is not permission to ignore provider inconsistency.

If a live filing returns a different:

- stock code; or
- provider external ID,

the identity verification result is:

`MISMATCH`

and the mapping must not be used silently.

The existing Open DART provider also checks that filings retrieved through a
seeded corp code match the requested stock code.

## 9. Hyundai Motor identity remains pending

A public implementation reports:

```text
005380 → 00164742
```

from a prior real Open DART lookup.

QuanTrade treated this as **discovery-only**, not registry truth.

A separate diagnostic attempted to verify that candidate through official Open
DART filing metadata:

run `37880946691`

but the Open DART JSON transport was unavailable during the maintenance window.

Therefore the candidate remains:

`PENDING_OFFICIAL_VERIFICATION`

Record:

`research/diagnostics/ISSUER_ID_005380_PENDING.json`

It has **not** been promoted into the verified registry.

## 10. QT-CASE-004 remains closed

QT-CASE-004:

- target: Hyundai Motor `005380`;
- preregistration:
  `5c7f5696479c3787843abca8799e937950f2daff`;
- terminal infrastructure run:
  `37880626483`;
- source:
  `39b2de24df7373b3adac19c54eef3e6989b08900`;
- economic values retrieved: **false**;
- target replaced: **false**;
- methodology relaxed: **false**.

It is archived as an infrastructure failure, not retrospectively repaired.

## 11. Future Investment Case startup

Target operating sequence:

```text
Mission created
    ↓
Research Preflight
    ├─ required source available?
    ├─ API credential present?
    ├─ verified issuer identity cached?
    ├─ if not, official identity resolver available?
    └─ required tools reachable?
    ↓
READY
    ↓
PIT Evidence
    ↓
Semantic Metric Applicability
    ↓
Valuation Method Applicability
    ↓
Valuation / Counter-Research
    ↓
Cross-Method Gate
    ↓
Portfolio / Risk
```

If Preflight is `BLOCKED`, the Mission stops before expensive research.

## 12. Retry rule

Retry should be bounded and reason-aware.

Examples:

### Network transient

A small bounded retry is acceptable.

### Scheduled maintenance

Do not continuously retry.

Record the dependency as `MAINTENANCE` and resume only after the expected
availability window.

### Access denied

Do not reinterpret Founder approval as credentials.

### Unregistered identifier

Use the governed registration/verification process.

### Missing source material

Report `MATERIAL_ABSENT`; do not fabricate.

## 13. Authority invariant

Neither identity resolution nor preflight can:

- create canonical economic Evidence;
- create valuation;
- create a Portfolio Proposal;
- set target weight;
- create Committee/Founder Decision;
- authorize PAPER;
- authorize execution;
- place a live order.

They exist to make the organization more truthful about whether it can begin
work at all.
