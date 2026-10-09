# QT-CASE-004 Result — Hyundai Motor Untouched Issuer Holdout

Status: **OPERATIONAL INFRASTRUCTURE FAIL / HOLDOUT PRESERVED / NO TRADE AUTHORITY**

## Frozen target

- Hyundai Motor Company
- `KRX:005380`
- Case as-of: `2026-10-05T23:59:59+09:00`
- preregistration: `5c7f5696479c3787843abca8799e937950f2daff`

The target was selected before live QT-CASE-004 economic values and was not
replaced after failure.

## What happened

QT-CASE-004 preregistered that the DART `corp_code` must first be resolved
from the official Open DART corporation-code source.

Attempt 1:

- run `37880525720`
- source `4105bb0e51161c131910aa2629f7dd24a23476d4`
- transport timed out before corporation-code resolution.

Transport retry was then hardened without changing any economic rule.

Attempt 2:

- run `37880626483`
- source `39b2de24df7373b3adac19c54eef3e6989b08900`
- five bounded corporation-code attempts completed;
- the service did not return a valid corporation-code archive.

No QT-CASE-004 economic fundamental values were retrieved before this failure.

## External service diagnosis

Open DART's official notice states a maintenance period:

`2026-10-08 20:00 ~ 2026-10-11 18:00 KST`

and explicitly lists the Open API **corporation code** service among suspended
services.

Official notice:

`https://engopendart.fss.or.kr/`

Therefore QT-CASE-004 is classified:

`EXTERNAL_IDENTIFIER_SERVICE_UNAVAILABLE`

This is not a valuation result.

## Why the holdout was not bypassed

The preregistration explicitly stated:

> if the official corporation-code resolver remains unavailable after bounded
> retry, the experiment fails operationally and is not retargeted.

Using a third-party corporation-code mapping after observing the failure would
change the preregistered source rule.

That was not done.

The result remains:

`OPERATIONAL_INFRASTRUCTURE_FAILURE`

## Product lesson

Issuer identity is infrastructure, not an economic signal.

Re-resolving a stable stock-code ↔ DART-corp-code mapping from a network
archive on every Case creates an avoidable single point of failure.

Future Cases should be allowed to use a **Verified Issuer Identity Registry**
when the mapping:

1. has provenance;
2. has previously been verified against an official DART filing;
3. matches the requested stock code;
4. is immutable/versioned;
5. fails closed if a live filing contradicts it.

This is different from guessing or silently substituting an identifier.

## Holdout integrity

QT-CASE-004 produced no:

- P/E valuation;
- DCF valuation;
- Cross-Method result;
- Portfolio assessment;
- Risk opinion;
- Committee/Founder Decision;
- PAPER/live authorization.

The economic question for Hyundai Motor remains unanswered by QT-CASE-004.
