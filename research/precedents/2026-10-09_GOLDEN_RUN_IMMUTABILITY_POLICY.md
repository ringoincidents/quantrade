# Golden Run Immutability Policy

Status: **ADOPTED**  
Date: **2026-10-09**

## Problem

A Golden Run is a historical experiment, not a continuously recomputed
dashboard.

After QT-CASE-001/002 completed, a later shared-capability change matched the
old workflow path filters and automatically re-ran the completed experiments.

The rerun itself remained safe, but it demonstrated a provenance risk:

> later code could regenerate and attempt to overwrite a historical result.

In the observed QT-CASE-002 rerun, the workflow produced a small changed result
after Portfolio output gained new optional fields. The evidence push was
rejected as non-fast-forward because development had already advanced the
branch.

The historical result therefore remained unchanged, but relying on a race or
non-fast-forward rejection is not acceptable governance.

## Adopted lifecycle

### Before first successful result

A preregistered Golden Run may be automatically triggered by its experiment
implementation files.

### At first successful result

Record:

- preregistration commit;
- exact workflow run ID;
- exact source code SHA;
- immutable Actions artifact ID/hash;
- compact evidence commit.

### After evidence is recorded

The experiment is **CLOSED**.

Its workflow must be converted to:

- `workflow_dispatch` only;
- checkout of the exact successful source SHA;
- `contents: read`;
- no Git commit/push step;
- artifact upload only.

Shared capability changes must not automatically re-run a closed experiment.

## Replay semantics

A replay answers:

> "What does the frozen historical experiment code produce when explicitly
> re-run?"

It does not replace the canonical historical result.

If external providers can no longer reconstruct the old state, replay may fail
closed. The original immutable artifact remains the evidence of what ran at the
historical execution time.

## Corrections

If the original experiment result is later found to contain a methodology or
implementation defect:

Do **not** edit the old result in place.

Instead record:

- defect;
- affected experiment;
- whether interpretation changes;
- corrective code;
- a new experiment ID or explicit corrected-replay ID.

Example:

`QT-CASE-002-CORR-001`

The original remains auditable.

## Current application

QT-CASE-001 archived replay source:

`1419314da38f40c08c5c8dadbbdfa7af41694b33`

QT-CASE-002 archived replay source:

`be2d554c346c4806e1c54a38771c9b18ae483bdd`

Both workflows are now manual, read-only replay workflows.

## Authority

Golden Run workflows remain unable to:

- authorize PAPER capital;
- authorize live capital;
- create broker side effects;
- mutate Client portfolios;
- silently promote research into production policy.

Experiment evidence is organizational memory, not trading authority.
