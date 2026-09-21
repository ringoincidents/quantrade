# E2-A calibration restart — 2026-09-21

Status: grading repairs verified locally; live calibration pending.
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
