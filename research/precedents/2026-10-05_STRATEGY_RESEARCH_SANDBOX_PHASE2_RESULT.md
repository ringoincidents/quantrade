# Strategy Research Sandbox Phase 2 — Safe Candidate Provider Result

Status: **SANDBOX IMPLEMENTED / NOT PROMOTED**  
Date: **2026-10-05**  
Parent: `2026-10-05_STRATEGY_RESEARCH_SANDBOX_IMPLEMENTATION_PLAN.md`  
Execution mode: **single-model organizational simulation; not independent review**

## 1. Objective

Implement QT-STRAT-002 without recreating the unsafe pattern observed in external strategy-finding prototypes where generated formulas can be passed to unrestricted language/runtime evaluation.

The Phase 2 contract is:

```text
CandidateProvider
→ bounded declarative AST
→ deterministic validator
→ past-only signal compiler
→ Phase 1 deterministic StrategyEvaluator
```

No candidate provider in this phase may execute Python, call a model, access the network, mutate portfolio state, or authorize execution.

## 2. Implemented safe DSL

The first DSL intentionally supports only close-price-based deterministic primitives:

### Numeric primitives

- `CLOSE`
- `CONST`
- `RETURN(window)`
- `SMA(window)`
- `EMA(window)`
- `STD(window)`
- `ZSCORE(window)`
- `REF(value, periods)`
- `ADD`
- `SUB`
- `MUL`
- `DIV`

### Boolean primitives

- `GT`
- `LT`
- `AND`
- `OR`

The root expression must be boolean because v1 compiles only long/flat target positions.

ATR, volume-based operators, cross-sectional rank and other richer primitives are deliberately deferred until the market-bar/data contract exposes the required inputs cleanly. They are not approximated from unavailable data.

## 3. Safety bounds

`CandidatePolicy` makes the following limits explicit:

- maximum candidates per batch;
- maximum AST depth;
- maximum AST node count;
- maximum lookback window;
- maximum absolute constant.

The validator rejects:

- unknown operators;
- missing keys;
- extra keys;
- invalid operand types;
- out-of-range windows;
- non-finite/oversized constants;
- non-boolean root expressions.

Exact-key checking also prevents a candidate from smuggling fields such as `python`, `code`, shell commands or other uninterpreted payloads into a valid node.

## 4. No arbitrary code execution

There is no `eval()`, `exec()`, dynamic import, subprocess, file I/O, network access or model call in the DSL compiler.

Division by zero is deterministic:

- numeric result becomes unavailable;
- a comparison depending on that unavailable value becomes `False`;
- the compiler emits a flat position instead of raising into an uncontrolled runtime path.

## 5. Past-only signal semantics

For each return period:

```text
signal effective_at = current bar timestamp
information_cutoff = current bar timestamp
position applies to current bar → next bar return
```

The compiler has no operator that can reference a future index.

A regression test mutates the final future price and confirms earlier compiled signals remain unchanged.

Phase 1 still independently checks the resulting `information_cutoff`, so candidate generation and strategy evaluation retain separate timing guards.

## 6. Candidate provider seam

Implemented `StrategyCandidateProvider` protocol and `StaticCandidateProvider`.

The static provider is intentionally first. It proves that QuanTrade can validate provider provenance and candidate contracts before adding an LLM-backed provider.

Each emitted candidate preserves:

- provider ID;
- implementation;
- version/revision;
- license;
- deterministic flag;
- network-access flag;
- model-access flag;
- capital-effect flag;
- sandbox status.

The provider rejects:

- duplicate candidate IDs;
- duplicate canonical formulas;
- candidate batches above policy;
- MarketScope mismatch;
- rebalance-horizon mismatch.

## 7. End-to-end reference harness

`strategy_candidate_evaluation.py` now runs:

```text
StaticCandidateProvider
→ Safe AST Validation
→ Past-only Signal Compiler
→ Deterministic Strategy Evaluator
```

with two deliberately simple reference candidates:

1. SMA trend reference
2. Z-score mean-reversion reference

They are infrastructure fixtures, not alpha claims.

The artifact explicitly records:

- `model_called = false`
- `canonical_evidence_created = false`
- `portfolio_proposal_created = false`
- `strategy_approved = false`
- `investment_decision_created = false`
- `execution_authorized = false`

## 8. Tests added

Phase 2 tests cover:

1. unknown operator rejection;
2. AST depth bound;
3. lookback-window bound;
4. deterministic division-by-zero behavior;
5. candidate-count bound;
6. duplicate-formula rejection;
7. provider provenance preservation;
8. extra-field/code-smuggling rejection;
9. future-price mutation does not alter earlier signals;
10. provider → compiler end-to-end seam;
11. candidate → compiler → evaluator full sandbox artifact remains non-authoritative.

## 9. Verification evidence

GitHub Actions workflow: `Strategy Research Capability Tests`

Verified commit:

`afc7077f91e2d2e92b95c22f46d60d695f643b6f`

Workflow run:

`37253421339`

Result: **SUCCESS**

The run:

- compiled capability/test/script modules successfully;
- ran **19 strategy-research tests, all passing**;
- executed the Phase 1 deterministic research harness successfully;
- executed the Phase 2 safe candidate harness successfully.

An earlier run failed after all 19 tests had already passed because the harness script was invoked as a file and therefore lacked the repository root on Python's import path. The workflow was corrected to invoke both harnesses as modules. This was a CI invocation defect, not a strategy-calculation failure, and the failed run is preserved in Actions history.

## 10. Files

- `quantrade/capabilities/strategy_candidates.py`
- `quantrade/capabilities/strategy_candidate_evaluation.py`
- `tests/capabilities/test_strategy_candidates.py`
- `scripts/run_strategy_candidate_evaluation.py`
- `.github/workflows/strategy_research_tests.yml`

`CandidateStrategy` was extended with optional:

- `formula_ast`
- `parameter_set`
- `generator_provider`

Existing Phase 1 callers remain compatible because these fields have defaults.

## 11. Current boundary

Phase 2 does **not** implement `LLMCandidateProvider`.

That omission is intentional.

The next LLM experiment should be thin:

```text
LLM
→ JSON candidate only
→ same validator
→ same compiler
→ same evaluator
```

The model must never receive a bypass around the AST validator, and generated prose cannot override a deterministic rejection.

## 12. Next step

QT-STRAT-003 should add the robustness gate and conditional specialist review.

Before expensive reasoning:

- reject leakage;
- reject insufficient sample;
- reject excessive turnover/cost sensitivity;
- evaluate drawdown and benchmark;
- detect near-duplicate candidates;
- measure regime/parameter instability where data permits.

Only surviving top-K candidates should be eligible for bounded MSIP specialist review.

No result in this phase changes Portfolio, Risk, Committee or Execution authority.
