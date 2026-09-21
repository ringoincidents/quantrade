# E2-A calibration restart — 2026-09-21

Status: COMPLETE — calibration exposed remaining measurement/runtime defects; no capability promotion.
Base: PR #83, commit 1de23e4695afd5b375c764f86e8d4e860f941f03.
Original run: https://github.com/ringoincidents/quantrade/actions/runs/35485062410

## Question and frozen conditions
Does read-only portfolio diagnostics and then investment memory improve discovery of material portfolio issues? Same six synthetic cases, Gemini model gemini-3.5-flash-lite, three treatments, one repeat (18 trials), existing tool/iteration limits and 20-second pacing. This is calibration, not a powered benchmark or production promotion.

## Original run (old grader; provisional)
All three treatments completed 6/6, passed 4/6, macro recall 0.75, precision 1.0. Total tokens: snapshot 5,987; diagnostics 9,567; diagnostics plus memory 13,783. These are tokens, not monetary cost.
Memory retrieved prior falsification conditions and identified PD-02, but missed PD-05 concentration. Snapshot and diagnostics missed PD-02. Thus equal aggregate pass rates conceal different behavior. One sample cannot establish equivalence or superiority.

## Repairs before rerun
- Remove case titles from public packets: titles such as `Thesis break requires memory` disclose the intended task answer. All treatments now see the neutral title `Portfolio review`. This means wave 2 is a calibration correction, not a clean model-to-model replication of wave 1.
- Validate all required output fields, enums and types before scoring; malformed output earns no recall/precision credit.
- Require successful retrieval on the current work order and a cited returned memory reference for PD-02 thesis-break credit. Unknown or unretrieved references cannot earn credit. Public snapshot paths and public observation refs remain legitimate provenance.
- Inspect all escalated issues, including duplicate issue types, for decoy citations.
- A zero-research answer requires explicit no_other_material_issues=true.
- Verify actual serialized first-turn packets for all 18 case/treatment combinations, with exact granted tool sets and no diagnostic/memory payload or hidden labels.
- Run the full institutional test suite before any live provider call.

Public PD-04 macro evidence can legitimately motivate investigation without a diagnostic call; it is deliberately not relabeled as hidden-only to favor treatment B/C.

## Known limitations kept visible
PD-03 expects both LIQUIDITY_MISMATCH and CLIENT_CONSTRAINT, which may double-count one underlying problem. Its diagnostic shortfall of 12 percentage points excludes the external 2-point cash buffer; the public packet permits a net 10-point interpretation. Some model explanations also misread the amounts. This rerun freezes that fixture and does not silently rewrite historical answers or claim numeric-reasoning accuracy. A future version should predefine one issue group and gross/net liquidity quantities before collecting fresh results.

The grader verifies reference availability and required retrieval, not semantic entailment of arbitrary prose. Synthetic diagnostics are frozen fixtures, not a validation of production financial calculations. One model, six cases, one repeat; no live trading, organizational-topology promotion, or claim of outperformance.

## Next gate
Inspect wave 2 raw outputs, errors, retrieval and grading. Address remaining case/measurement ambiguity in a versioned protocol before repeated E2-A evaluation or E2-B architecture comparison. Preserve original artifacts and append results rather than replacing earlier conclusions.

## Validation and original-response audit
- Local targeted suite: 13 tests passed, including full serialized packet checks over 18 case/treatment combinations.
- GitHub full suite: 121 tests passed; no-broker demo passed.
- Regraded a copy of the original SQLite artifact with the repaired grader: all original treatment scores remained 4/6 with mean recall 0.75. The original DB and model outputs were preserved. This checks the impact of grading repairs only; it cannot remove the answer hints the original models already saw.
- CI: https://github.com/ringoincidents/quantrade/actions/runs/35593639791
- Wave 2: https://github.com/ringoincidents/quantrade/actions/runs/35593639808

## Wave 2 outcome (frozen grader; all attempts retained)

| Treatment | Attempted | Completed | Strict passes | Completed-only mean recall | Completed-only tokens |
|---|---:|---:|---:|---:|---:|
| Snapshot | 6 | 5 | 1 | 0.20 | 4,771 |
| + diagnostics | 6 | 6 | 4 | 0.75 | 12,936 |
| + diagnostics + memory | 6 | 5 | 3 | 0.60 | 10,317 |

The denominators differ. These are descriptive calibration outputs, not a valid superiority estimate. Token aggregates exclude errored trials and must not be labeled full experiment cost. The pipeline's success status does not mean all model trials succeeded.

- PD-05 snapshot and memory treatments failed parsing invalid JSON escape sequences. Both failures remain ERROR; neither was silently retried or converted into a reasoning score.
- PD-03 snapshot and memory treatments used real public field/asset names as references, but omitted the `portfolio_snapshot.` prefix. The provenance whitelist rejected them even though the prompt never specified that exact citation syntax. Their unsupported/false-research flags are therefore partly a measurement artifact, not demonstrated hallucination. Preserve the raw grade; define accepted public references before fresh trials.
- PD-03 diagnostics still names a 12-point shortfall without correctly accounting for the 2-point external buffer, and the hidden grader requires two labels for one cash-need problem. Numeric correctness and issue-group semantics remain unvalidated.
- PD-02 memory treatment called only portfolio diagnostics, never investment memory, and missed the thesis break. Having a memory tool available does not establish that the runtime will use it when needed. This contrasts with wave 1, which exposed a memory-specific title hint; one observation does not establish causation.
- PD-06 all three treatments correctly chose no further research.

## Decision / next experiment
Do not promote diagnostics/memory, start E2-B, or infer that more departments will solve these defects. Next is **E2-A v1 measurement calibration**:
1. Publish a shared, explicit public citation scheme (including snapshot fields) to every treatment and test equivalent valid references.
2. Define gross shortfall=12 and net shortfall=10 on the common portfolio denominator; score the cash requirement as one issue group and add a deterministic numeric check.
3. Fix the nested JSON output contract consistently across treatments; retain format failures and charge any repair calls explicitly.
4. Measure memory/diagnostic retrieval separately from discovery success; later compare optional retrieval with a preregistered retrieval policy rather than forcing retrieval only after observing misses.
5. Freeze the revised protocol before a balanced repeated run. No additional live calls were made after this wave.

The workflow is restricted to the original restart transition so subsequent report updates cannot silently launch another paid/quota-consuming run.
