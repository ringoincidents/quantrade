# Strategy Research Sandbox Phase 3 — Robustness Gate + Bounded Review Planning

Status: **SANDBOX IMPLEMENTED / NOT PROMOTED**  
Date: **2026-10-05**  
Parent: `2026-10-05_STRATEGY_RESEARCH_SANDBOX_IMPLEMENTATION_PLAN.md`  
Execution mode: **single-model organizational simulation; no independent specialist was actually invoked**

## 1. Objective

Prevent the Strategy Research Sandbox from turning every generated idea into an expensive multi-agent meeting.

Phase 3 implements:

```text
Phase 1 deterministic evaluation
→ robustness gate
→ near-duplicate suppression
→ deterministic research priority
→ top-K bound
→ existing ReviewGate
→ bounded specialist Work plan
```

The planner creates Work requests only. It does not call models.

## 2. Robustness gate

A candidate is rejected before specialist reasoning when any configured hard condition fails.

Current measurable checks:

- upstream Phase 1 screen must have survived;
- minimum return-period sample;
- maximum drawdown;
- minimum benchmark excess return;
- maximum turnover per period;
- maximum transaction-cost drag.

The policy remains explicit and replaceable.

This does not claim these thresholds are universally optimal. It creates one auditable place where research-screening assumptions live.

## 3. Research prioritization is not an investment score

Surviving candidates are ordered only to ration expensive review capacity.

Ordering basis:

1. higher benchmark excess return;
2. higher Sharpe;
3. lower cost drag;
4. lower turnover;
5. deterministic candidate ID tie-break.

The artifact explicitly states `investment_score_created = false`.

A higher research priority cannot approve a strategy, set position size, override Risk, or authorize execution.

## 4. Near-duplicate suppression

Phase 2 already rejects exact duplicate formula ASTs.

Phase 3 adds a second kind of duplicate control:

> different formulas that produce effectively the same long/flat signal path.

Two equal-length signal vectors are compared by position agreement ratio.

If similarity meets the configured threshold, the lower-priority candidate is suppressed as:

`NEAR_DUPLICATE_SIGNAL_PATH`

This avoids spending model/tool budget reviewing multiple formulations of nearly the same exposure.

## 5. Top-K review bound

After hard rejection and duplicate suppression, only the first `top_k` candidates can become specialist-review candidates.

Overflow is recorded as:

`TOP_K_BOUND:<K>`

It is not silently deleted.

This implements the intended architecture:

```text
many cheap candidates
→ deterministic measurement
→ deterministic rejection
→ duplicate suppression
→ small survivor set
→ bounded reasoning
```

## 6. Existing ReviewGate reused

Phase 3 does not invent another AI-call router.

Selected research survivors are converted to structured `ReviewEvent` records and passed into the existing QuanTrade `ReviewGate`.

Current reference policy produces `BOUNDED_REVIEW` for strategy-research survivors.

If no candidate survives, the gate produces `NO_REVIEW` and no specialist Work is planned.

Review necessity remains separate from investment authority.

## 7. Specialist Work contract

For a selected candidate, the planner can create:

### Always decision-changing for a research survivor

- `QUANT_MARKET`
  - can statistical/market-structure evidence falsify the candidate?
- `COUNTER_RESEARCH`
  - what strongest evidence/failure mode contradicts the candidate?

### Context-dependent

- `PORTFOLIO_MANAGEMENT`
  - only when current portfolio context is actually available/relevant;
- `RISK_COMPLIANCE`
  - when risk review is required for the intended validation step;
- `DEEP_EXTERNAL_RESEARCH`
  - only when an external theory/mechanism/source dependency requires verification.

Each planned Work request is bounded by default to:

- max model calls: **1**
- max tool rounds: **3**

These are research-budget controls, not guarantees of analytical quality.

## 8. TradingAgents lesson absorbed without copying its fixed graph

The useful TradingAgents patterns now have concrete QuanTrade-native equivalents:

- isolated specialist roles → explicit `SpecialistWorkRequest`;
- bounded analyst loops → model/tool budgets;
- parallel-capable specialists → independent Work requests before a future join;
- deterministic routing → ReviewGate + explicit routing inputs;
- no unlimited debate → top-K and stop-before-review gates.

What was **not** copied:

- fixed Bull/Bear/Trader/Risk debate topology;
- a trader agent with execution authority;
- a framework-owned organizational graph.

QuanTrade retains its own Research → Portfolio → Risk → Committee authority model.

## 9. Reference experiment

The Phase 3 reference harness contains four synthetic candidates:

- `SURVIVOR-A`
- `NEAR-DUPLICATE-B`
- `SURVIVOR-C`
- `COST-SENSITIVE-D`

Expected behavior:

- A survives;
- B is suppressed because it emits the same signal path as A;
- C survives as a distinct path;
- D is rejected by cost-sensitivity guard despite superficially stronger gross metrics;
- only A and C enter bounded review;
- current reference context plans Quant, Counter-Research, Portfolio and Risk for each;
- **8 Work requests are planned, 0 are invoked**.

This is a control experiment, not a strategy-performance claim.

## 10. Verification evidence

GitHub Actions workflow:

`Strategy Research Capability Tests`

Verified commit:

`005d495e50adec55f1b1a41761c8b6c5d6994b48`

Workflow run:

`37253703262`

Result: **SUCCESS**

The run reports:

```text
Ran 28 tests
OK
```

It also executes successfully:

- Phase 1 deterministic strategy-research harness;
- Phase 2 safe candidate-generation harness;
- Phase 3 robustness-review harness.

## 11. Implemented files

- `quantrade/capabilities/strategy_robustness.py`
- `quantrade/capabilities/strategy_robustness_evaluation.py`
- `tests/capabilities/test_strategy_robustness.py`
- `scripts/run_strategy_robustness_evaluation.py`

The existing strategy capability CI workflow was extended to run the Phase 3 harness.

## 12. Authority result

Phase 3 cannot:

- call an LLM;
- create canonical Evidence;
- create a Portfolio proposal;
- change Risk limits;
- approve a strategy;
- create an Investment Decision;
- authorize execution;
- promote automatically to PAPER.

`specialists_planned` and `specialists_invoked` are deliberately separate telemetry fields.

## 13. Remaining work before QT-STRAT-004

Do not call the current reference harness a PAPER Golden Run.

A real QT-STRAT-004 requires:

1. one explicit bounded MarketScope;
2. point-in-time market dataset/provenance;
3. actual candidate set frozen before results;
4. benchmark and friction assumptions frozen before results;
5. cost/latency telemetry for any model calls;
6. a failure log;
7. review artifacts from actually independent specialist Work when Holdings Runtime is used;
8. explicit Proposal → Decision before StrategyPassport/PAPER promotion.

The existing open institutional branch/PR #108 also has an unresolved Evidence timestamp issue and should be reconciled before deeper institutional binding is treated as complete.

## 14. Next recommendation

**Stop architecture expansion here and prepare QT-STRAT-004 as an experiment design, not as another generic framework feature.**

Phase 1–3 now provide enough machinery to ask a more valuable question:

> given one frozen MarketScope and frozen candidates, does the new pipeline produce better research decisions than the old ad-hoc strategy loop at acceptable cost?

That should be measured before adding RL, FinBERT, or an LLM candidate provider.
