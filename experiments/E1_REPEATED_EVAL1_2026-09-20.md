# E1 Repeated Evaluation 1 — 2026-09-20

Status: calibration evidence only; EXCLUDED from architecture benchmark claims.

## Run identity
- Workflow run: 35483224533
- Job: 106004679956
- PR: #78
- Branch head used: 8e1417aab014c9994ac8bf1ad94bf46047de14e6
- Checkout merge ref: 340cce22430e025f0063d0a08bc506ec5a3f9ee3
- Model: gemini-3.5-flash-lite
- 6 tasks x 2 treatments x 3 repeats = 36 trials
- Artifact: 10596297498
- Digest: sha256:c9025c49fe08f3abdf3ae4fe68bd9a4192ca6d59b6ad8d9fe3a80dbe3c3b538a
- Workflow conclusion: success
- Provider/infrastructure trial ERRORs: 0

## Headline output — DO NOT USE AS ARCHITECTURE SCORE
Strict grader:
- DIRECT_SINGLE_AGENT: 12/18
- QUANTRADE_INSTITUTIONAL: 17/18
- total: 29/36

These numbers are contaminated by a calibration mistake and must not be interpreted as evidence that QuanTrade outperforms Direct.

## Critical contamination discovered

The quantitative-format correction made after Wave 2 accidentally put the exact expected answer into the model-visible objective for four tasks:

- E1-01: "(for this task, 8.2)"
- E1-03: "(for this task, 25.0)"
- E1-05: "(for this task, 18.0)"
- E1-06: "(for this task, 9.1)"

This is target leakage.

The leakage had observable behavioral consequences:
- E1-01 Direct repeat 1 finished after one model call with answer 8.2 and no tool retrieval, citing a non-document identifier instead of CURRENT-FILING.
- E1-06 Direct repeats 1 and 2 finished after one model call with answer 9.1 and no evidence retrieval.
- E1-05 Direct repeat 3 finished after one model call with answer 18.0 and no tool call.

Therefore E1-01/E1-03/E1-05/E1-06 cannot support clean treatment-performance conclusions from this run.

E1-03 still demonstrates process compliance with the required deterministic finance.growth_pct tool in all six trials, but its answer-correctness check is contaminated.

## Uncontaminated repeated tasks

E1-02 contradictory evidence:
- Direct: 3/3
- Institutional: 3/3
- Both consistently retrieved IR-DECK and FILING-NOTE and preserved CONFLICT.

E1-04 missing-data refusal:
- Direct: 3/3
- Institutional: 3/3
- Both consistently refused to invent the unavailable 2027 maturity.

On these two uncontaminated bounded task families there is no observed quality advantage for the institutional harness.

## Tool-failure behavior — calibration finding only

E1-05 remains useful as a runtime observation, not a treatment score.

When the required failing lookup was actually attempted, both runtimes demonstrated live recovery paths using catalog/document fallback.

Observed schema-adherence failures also occurred:
- Direct r1/r2 placed answer/status/evidence fields at FINISH payload top level while summary was prose, violating the public summary contract.
- Institutional r2 made the same shape error.
- Institutional r1/r3 used the required summary JSON shape.

Because the exact answer was leaked, do not interpret the pass-rate difference causally.

## Measured institutional context overhead

The run provides useful cost diagnostics independent of the contaminated correctness score.

All 36 trials:
- Direct: 46 model calls, 83,969 serialized input-context characters.
- Institutional: 57 model calls, 236,391 serialized input-context characters.
- Raw total context-character ratio: 2.82x, but this is inflated by Direct shortcutting leaked-answer tasks.

Restricting to uncontaminated E1-02 and E1-04:
- Direct: 20 model calls, 36,577 input-context chars.
- Institutional: 21 model calls, 86,458 input-context chars.
- Institutional context volume: 2.36x Direct.

Elapsed time on E1-02 + E1-04:
- Direct mean: 2.369s/trial.
- Institutional mean: 2.605s/trial.
This sample is too small for a latency conclusion.

A first-turn Wave 2 decomposition showed the institutional overhead is dominated by WorkOrder + Task + Employee metadata in addition to the shared tool catalog. e1_runner also duplicates the task objective inside the Institutional WorkOrder because public_packet already contains objective.

Issues opened:
- #80 persist provider token usage before E2.
- #81 remove redundant institutional model context via explicit ablation.

Do not silently optimize institutional-v0 and compare the result as if it were the same treatment. Any compressed context must receive a new harness/version.

## What this run actually teaches

1. The experiment harness is capable of exposing our own evaluation mistakes. This run caught target leakage rather than producing a flattering false result.
2. On clean short evidence/refusal tasks, the institutional shell has not demonstrated additional task quality.
3. Institutional-v0 has a measurable context-cost penalty.
4. The institutional prompt/context may encourage provenance/tool use more strongly, but the contaminated tasks do not establish that causally.
5. Output-schema adherence remains a real capability dimension and should be measured separately from substantive correctness.
6. Provider-reported token usage must be captured before architecture cost claims.
7. E1 remains calibration. No claim that QuanTrade is a superior investment-research architecture is authorized.

## Correction rule

Replace exact-answer examples with a non-answer-bearing type contract, e.g.:

"answer must be a JSON number in percentage points; if evidence said 7.5%, encode 7.5 rather than '7.5%'."

Never include the actual hidden expected value in the public packet.

Do not spend another full 36-trial run merely to manufacture a clean win/loss. E1's purpose was interface/runtime calibration. Correct the suite, add usage telemetry, then freeze the next benchmark protocol before further repeated evidence.

## Classification

Finding:
The first repeated E1 run is contaminated by target leakage in four public task objectives and is excluded from architecture benchmark claims.

Finding:
On the two uncontaminated repeated task families, Direct and Institutional both passed 6/6 trials.

Finding:
Institutional-v0 used ~2.36x serialized model-context volume on the uncontaminated tasks.

Open Question:
Does institutional context/authority/provenance structure improve harder failure modes enough to justify its inference overhead?

Project Update:
E1 calibration has now exposed task leakage, context overhead, schema-adherence variance, and the need for provider token telemetry. E2 must not begin until those measurement defects are corrected.
