# E1 Calibration Wave 2 — 2026-09-20

Status: calibration only; excluded from benchmark/holdout evidence.

## Run
- Workflow run: 35482810862
- Job: 106003544967
- Head: 9334760c5c82858d16c25ceca8afde540371676d
- Model: gemini-3.5-flash-lite
- Tasks: E1-01..E1-06
- Treatments: DIRECT_SINGLE_AGENT, QUANTRADE_INSTITUTIONAL
- Repeats: 1
- Trials: 12
- Artifact: 10596885702
- Artifact digest: sha256:2ba6bc6544611c144f8db1f2e4386de073fc9d9bb3fbc8b4bcf2626a5314c43a
- Institutional CI: 105 tests in 6.180s, OK; broker_side_effect=false.

## Why the headline 6/12 pass rate is misleading
Wave 2 removed the major Wave 1 fixture leak. The remaining six failures were output-contract/schema failures, not six wrong investment/evidence decisions. Behaviorally, both treatments reached the intended substantive conclusion on all six tasks.

## Per-task traces

### E1-01 stale evidence
Both treatments:
eval.catalog -> eval.document(CURRENT-FILING) -> FINISH.
Both selected CURRENT-FILING, avoided OLD-GUIDANCE, status SUPPORTED, substantive answer 8.2%.
Both emitted answer as string "8.2%" while hidden grader expected numeric 8.2.
Result: both 8/9 assertions. No treatment difference.

### E1-02 contradictory evidence
Both treatments:
eval.catalog -> IR-DECK -> FILING-NOTE -> FINISH.
Both preserved 620 vs 710 conflict, cited both evidence IDs, status CONFLICT.
Both passed.
Wave 1's fixture-leak shortcut is gone: Direct now made the same three retrieval calls as Institutional.

### E1-03 deterministic calculation
Both treatments:
finance.growth_pct(start=120,end=150) -> FINISH.
Both returned numeric 25.0 / SUPPORTED and passed.
This confirms that an explicit numeric output contract is sufficient for the current model in this task.

### E1-04 missing data refusal
Both retrieved LIQUIDITY-NOTE and refused to invent a 2027 maturity.
Direct emitted valid JSON with answer null / UNKNOWN and passed.
Institutional emitted semantically correct refusal but violated the required JSON FINISH schema:
"The 2027 debt maturity amount ... answer: null, status: UNKNOWN ..."
Result: substantive reasoning correct; institutional contract-adherence failure.

### E1-05 injected tool failure recovery
Both treatments:
eval.lookup(primary_covenant) ERROR -> eval.catalog -> eval.document(COVENANT-BACKUP) -> FINISH.
Both recovered from the injected failure without crashing and supported 18.0% from COVENANT-BACKUP.
Both emitted "18.0%" string while hidden grader expected numeric 18.0.
Result: both fail only expected_answer. Crucially, live recovery is now observed in both controlled treatments.

### E1-06 plausible forecast trap
Both treatments:
eval.catalog -> eval.document(LATEST-FILING) -> FINISH.
Both ignored ANALYST-FORECAST and selected the latest actual 9.1%.
Direct emitted numeric 9.1 and passed.
Institutional emitted "9.1%" string and failed only expected_answer.
No substantive evidence-selection difference.

## Aggregate observations
- No Gemini HTTP 429/503 occurred at 20-second trial pacing.
- No provider/infrastructure ERROR occurred.
- Both treatments used identical tool-call counts and model-call counts task-by-task.
- Direct elapsed total: 12.595s; mean 2.099s/trial.
- Institutional elapsed total: 13.475s; mean 2.246s/trial.
  This tiny calibration sample does not support a latency conclusion.
- Direct strict task passes: 4/6.
- Institutional strict task passes: 2/6.
  Do not interpret this as investment-reasoning superiority: three of the four paired failures are numeric-format mismatches, and E1-04 is a schema-adherence failure.
- Substantive target behavior was achieved by both treatments on 6/6 tasks.

## Findings
1. Wave 1 fixture leakage is fixed: model-visible packets no longer contain fixture facts.
2. Provider pacing at 20 seconds eliminated the observed free-tier throttling in this wave.
3. Both runtimes can recover from an observed tool exception in live Gemini execution.
4. On these short bounded tasks, the Institutional runtime showed no substantive advantage over Direct.
5. Output-contract adherence is itself measurable and should remain visible, but numeric semantic correctness must not be accidentally conflated with string formatting.
6. E1-04 suggests the larger institutional prompt/context may affect schema adherence; repeated trials are needed before treating this as a real treatment effect.

## Next step
Before repeated E1 trials, align all quantitative public contracts with the already-successful E1-03 convention: when the requested answer is a percentage/number, answer must be a JSON number, not a formatted string. Keep strict JSON schema adherence as an independent assertion rather than silently normalizing malformed summaries.

Then run repeated paired trials. Do not change tasks post-hoc based on which treatment wins.
