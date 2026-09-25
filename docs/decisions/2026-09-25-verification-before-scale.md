# Decision: verification evidence before agent scale

Date: 2026-09-25. Status: scoped implementation for review; no merge or production promotion authorized.

## Source and interpretation

The user supplied a social-media summary attributed to Lauren Tan about pstack, Dune and high PR throughput. The primary Cursor pstack README states a preference for less, higher-quality code and trusting one verifiable agent before parallelizing: https://github.com/cursor/plugins/blob/main/pstack/README.md (accessed 2026-09-25).

The original video could not be retrieved in this session. Employment, 1,000 monthly merges and the exact Dune bans are not independently verified here. PR count is neither outcome quality nor a target for QuanTrade. No pstack plugin was installed or imported.

## Adopt, adapt, reject

| Idea | QuanTrade decision |
|---|---|
| Verification receipts | Adopt: evidence-bearing reports, source identity, test logs and explicit failures |
| Feature map | Adapt: map institutional behavior to real source/test files, not an invented UI |
| Prompt/skill evaluations | Keep packet-leakage, provenance and output-contract regressions; require new checks when contracts change |
| Architecture/CI constraints | Begin with one observed defect: failed experiments must not silently appear green |
| Large agent fleets | Defer until additional value beats single-agent cost and complexity |
| No comments / no useEffect | Do not copy unrelated Electron/React rules into financial Python logic |
| Automatic merge | Not enabled. CI checks do not authorize merge or trading |

## Observed defect

The existing E2-A runner catches per-trial exceptions, saves the report and exits successfully. Wave 2 was marked successful by Actions despite two ERROR rows. It also deletes an existing output DB at startup. Both weaken evidence preservation and make human verification unnecessarily expensive.

## Applied change

Add an offline, deterministic execution receipt (coverage, identity uniqueness, terminal status, grade/check consistency, report SHA-256). Wire it into the live runner, refuse existing output paths, preserve CI logs and known-failure regression evidence, and map the relevant code/tests. Scientific task failures remain valid experimental observations and do not make a correctly completed experiment operationally fail.

No grading thresholds, model prompts, historical reports, strategy/risk policies, broker permissions or model budgets were changed. No extra employees, provider calls, automated merges or repository protection changes were introduced.

## What this does not prove

It does not prove investment quality, financial model correctness, runtime invulnerability, semantic validity of all evidence, or an advantage over Direct. A self-generated receipt must still be checked against independently rerunnable CI evidence. A passing check is only as strong as its oracle and coverage. Required checks cannot be claimed as merge enforcement until repository rules explicitly require them.

## Next research step remains unchanged

Prepare the E2-WORK-01 real-company calibration packet and inspect runtime readiness. This work removes a verification defect; it is not a new product feature or a reason to postpone the real-work experiment indefinitely. Preserve separate claims for labor saved, investigation quality and organization value.
