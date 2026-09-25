# QuanTrade verification map

Scope: institutional experimental branch, based on `2bc63bfc93ac15e23805e02e9df3e4fc19aa4967`. This is not a map of every legacy UI/trading feature. Read implementations before changing behavior.

| Behavior / entry | Source | Verification |
|---|---|---|
| Case lifecycle, audit ledger | `quantrade/institutional/service.py`, `demo.py` | `tests/institutional/test_kernel.py`, `test_migrations_recovery.py`; no-broker demo |
| Employee work requests and workspace | `organization.py`, `employee_agent.py`, `work_dispatcher.py` in the institutional package | `test_organization_runtime.py`, `test_work_dispatcher.py`, `test_runtime_truthfulness.py` |
| Tool discovery, grants, call budget | `quantrade/institutional/tools.py` | `tests/institutional/test_tool_registry.py` |
| Evidence ingestion; reject AI briefing as authoritative evidence | `quantrade/institutional/evidence_adapters.py` | `tests/institutional/test_evidence_adapters.py` |
| Model usage telemetry | `model_providers.py`, `direct_agent.py`, `eval_harness.py` | `tests/institutional/test_model_usage_telemetry.py` |
| E2-A public packets and grading | `e2a_suite.py`, `e2a_runner.py` | `test_e2a_problem_discovery.py`, `test_e2a_grading_integrity.py` |
| E2-A execution completeness | `experiment_receipt.py`, `scripts/verify_e2a_report.py`, `scripts/run_e2a_live.py` | `test_experiment_receipt.py`, `test_e2a_live_contract.py`; offline historical-report CLI |

Unqualified source names above are under `quantrade/institutional/`; test names are under `tests/institutional/`.

## Safe commands (repository root)

Full tests require the existing `requests` dependency. No model key is needed; tests use scripted/fake providers.

```sh
python -m unittest discover -s tests/institutional -p 'test_*.py' -v
python -m quantrade.institutional.demo
PYTHONPATH=. python scripts/verify_e2a_report.py --report docs/experiments/E2A_CALIBRATION_WAVE2_RAW.json --receipt /tmp/quantrade-wave2-receipt.json
```

Choose an unused receipt path. The last command intentionally exits **3**: the historical wave has 18 planned trials, 16 completed and 2 execution errors. This is the regression evidence, not a new model run. Original outputs are unchanged.

| Exit | Meaning | Does not mean |
|---|---|---|
| 0 | All planned trial identities present once and completed; report fields internally consistent | Every task passed, or QuanTrade beats Direct |
| 2 | Invalid/missing/duplicate/nonterminal report, unreadable input or receipt could not be written | A scientific loss against baseline |
| 3 | All planned trial identities accounted for, but one or more execution errors | Successful model execution |

## Evidence and limits

P1 CI preserves test logs, demo output, the known-failure receipt, checked commit, source hashes and worktree status as a 30-day artifact, even when earlier steps fail. Missing evidence must not be described as a pass. SHA-256 identifies bytes; it is not a signature or independent correctness proof. The receipt checks trial coverage/status/check consistency, not semantic validity, aggregate metric correctness or SQLite/report reconciliation.

The demo asserts its ledger check and no-broker flag. This is scoped to the synthetic demo, not a certification that the entire legacy repository can never place orders. Financial correctness requires separate tests and review. UI profiling/screenshots apply only to actual UI changes; there is no reason to add CPU traces to every research experiment.

The live E2-A runner refuses existing DB/report/receipt paths and emits a nonzero status after saving evidence when trials error. Interrupted runs may retain only partial DB evidence; no final receipt means NOT_VERIFIED. Live workflow authorization remains restricted; no provider run is part of this change.
