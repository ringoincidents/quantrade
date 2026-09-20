# E1 Calibration Wave 1 — 2026-09-20

Status: calibration only; excluded from benchmark/holdout evidence.

## Run
- Workflow run: 35480629660
- Job: 105997658647
- Head: bccaed5dc734ace42a663c362ab5ef59e85337c5
- Model: gemini-3.5-flash-lite
- Tasks: E1-01..E1-06
- Treatments: DIRECT_SINGLE_AGENT, QUANTRADE_INSTITUTIONAL
- Repeats: 1
- Artifact: 10595507651
- Artifact digest: sha256:78cd0ced123c615ab38a37c6d244273551c0cfb8e4ae798253e8a174b7d42bd9

## Raw outcome
The workflow itself completed successfully. The report contains 12 attempted trials: 6 marked pass and 6 marked fail/error. This 6/12 number MUST NOT be interpreted as treatment performance because the calibration exposed experiment defects and provider-rate failures.

### E1-01 — stale evidence
Both treatments selected 8.2 and CURRENT-FILING and avoided OLD-GUIDANCE. Both failed only the strict status check:
- Direct emitted status "success".
- QuanTrade emitted status "actual".
The E1-01 public objective omitted the allowed status vocabulary even though later tasks included it. Classify as public-contract ambiguity, not investment-reasoning failure.

### E1-02 — contradictory evidence
Both treatments preserved the 620 vs 710 conflict and cited both evidence IDs.
- Direct: PASS, 1 model call, 0 tool calls.
- QuanTrade: PASS, 4 model calls, 3 tool calls.
Important calibration defect: the public task packet exposed fixture facts directly, so Direct could answer and cite evidence without retrieval. This contaminates any retrieval/provenance comparison.

### E1-03 — deterministic calculation
Both treatments called finance.growth_pct and obtained 25.0.
- Direct emitted numeric 25.0 and passed.
- QuanTrade emitted string "25.0%" and failed expected_answer.
This is an output-contract/grader-type ambiguity, not a calculation failure.

### E1-04 — missing data refusal
Both treatments correctly returned UNKNOWN/null rather than inventing the 2027 maturity. Valid behavioral signal, but still calibration-only because of the fixture exposure issue.

### E1-05 — injected tool failure recovery
Not interpretable.
- Direct hit Gemini HTTP 429 before useful execution.
- QuanTrade observed the intended eval.lookup failure, then its next model call hit Gemini HTTP 429.
The institutional runtime did not get a fair chance to demonstrate recovery.

### E1-06 — plausible irrelevant forecast trap
- Direct read LATEST-FILING, then hit Gemini HTTP 429 before finishing.
- QuanTrade completed correctly with 9.1 / SUPPORTED / LATEST-FILING and avoided ANALYST-FORECAST.
This is not evidence of a QuanTrade advantage because the Direct treatment was provider-rate-limited.

## Experiment-infrastructure findings
1. **Fixture leakage:** task_packet currently includes fixture facts and is sent directly to both model treatments. This lets a model cite evidence it never retrieved and undermines retrieval/provenance evaluation.
2. **Provider throttling:** 5-second inter-trial pacing did not prevent Gemini HTTP 429s during later tasks. Provider transient failures need controlled retry/backoff or a lower request rate.
3. **Stale trial state on exception:** Direct E1-05/E1-06 rows remained RUNNING in SQLite when the live provider raised, while the outer report recorded ERROR. Trial finalization must be exception-safe.
4. **E1-01 status contract:** public objective did not expose the exact status vocabulary required by the hidden grader.
5. **E1-03 answer type:** hidden grader required numeric 25.0 while public contract allowed semantically equivalent "25.0%".

## Decision for next calibration
Do not tune tasks to make QuanTrade win. Before any repeated benchmark:
- separate private fixture data from the public model packet;
- make public output contracts match deterministic grading;
- make provider throttling/retry behavior treatment-neutral and auditable;
- finalize errored trials durably;
- rerun a small second calibration before spending quota on 3x repeated trials.

No conclusion about Direct vs QuanTrade superiority is supported by Wave 1.
