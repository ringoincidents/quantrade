# E1 Live Smoke Record — 2026-09-20

Status: completed calibration smoke; **not a benchmark result**

## Purpose

Prove that a real external LLM can execute both controlled treatments through
GitHub Actions using the same sealed task, frozen fixture, deterministic tools,
tool budget and hidden grader.

## Calibration incidents excluded from benchmark evidence

The smoke intentionally exposed experiment-infrastructure defects. These runs
must not be counted as model/architecture performance:

1. Initial workflow could not import the repository package (PYTHONPATH bug).
2. Gemini 3.8 Flash returned HTTP 503 twice on the free-tier smoke.
3. The first successful Gemini 3.5 Flash-Lite run exposed an underspecified
   public status vocabulary and a malformed multi-object action on one
   institutional turn.
4. A structured-output migration attempt returned HTTP 400 with the current
   Flash-Lite generateContent path and was reverted.
5. The transport parser was made tolerant of trailing model output while still
   consuming only the first action. The public task contract now explicitly
   states the allowed status vocabulary.

These are calibration findings, not post-hoc edits to a holdout benchmark.

## Final valid smoke

Workflow run: 35480546377
Head: 58ad257885dd0c1e7c61939ae0b411d60135f563
Model: gemini-3.5-flash-lite
Task: E1-01 — stale evidence trap
Repeats: 1 per treatment

### DIRECT_SINGLE_AGENT

- runtime: COMPLETED
- model calls: 3
- tool calls: 2
- tool errors: 0
- deterministic assertions: 8/9
- answer: 8.2
- evidence: CURRENT-FILING
- stale OLD-GUIDANCE used as evidence: no
- failed assertion: output-contract status vocabulary

Action trace:
1. eval.catalog
2. eval.document(CURRENT-FILING)
3. FINISH

Final summary used status="actual" instead of the required
status="SUPPORTED".

### QUANTRADE_INSTITUTIONAL

- runtime: COMPLETED
- model calls: 3
- tool calls: 2
- tool errors: 0
- deterministic assertions: 8/9
- answer: 8.2
- evidence: CURRENT-FILING
- stale OLD-GUIDANCE used as evidence: no
- failed assertion: output-contract status vocabulary

Action trace:
1. eval.catalog
2. eval.document(CURRENT-FILING)
3. FINISH

Final summary also used status="actual" instead of status="SUPPORTED".

## Finding

The live path is now real: a secret-backed external Gemini model successfully
drove both Direct and QuanTrade runtimes, invoked deterministic tools, and
produced durable trial records.

This smoke does **not** show a QuanTrade advantage. On E1-01 the two treatments
were behaviorally equivalent: same three-step pattern, same correct numerical
answer, same correct evidence selection, and the same output-contract failure.

That equivalence is useful. It demonstrates that the evaluation harness is
capable of returning "no observed architectural benefit" rather than being
constructed to make QuanTrade win.

## Next experiment

Do not tune E1-01 further merely to obtain PASS.

Next controlled run should expand across the six calibration task families and
report assertion vectors, not only all-or-nothing task pass. In particular:
- E1-02 tests uncertainty under contradictory evidence;
- E1-03 tests deterministic calculation discipline;
- E1-04 tests unsupported-data refusal;
- E1-05 tests recovery from an injected tool failure;
- E1-06 tests actual-vs-forecast discrimination.

The first architecture-specific advantage should be sought only in tasks where
institutional mechanisms are causally relevant. Cross-office delegation remains
reserved for later capability/ablation experiments rather than contaminating the
same-tools baseline.
