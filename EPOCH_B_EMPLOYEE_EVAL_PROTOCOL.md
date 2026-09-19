# QuanTrade Epoch B — Employee Evaluation Protocol v0

Date: 2026-09-19
Status: Initial harness implementation

## Research question

Does the QuanTrade institutional runtime improve reliable investment-research
work over a simpler agent harness when the underlying model, task packet,
data/tools and budget are held constant?

This is the primary causal question. Cross-product comparisons are secondary.

## Experimental lanes

### Lane A — controlled causal benchmark

Hold the model constant.

1. DIRECT_SINGLE_AGENT
   - same model
   - same sealed task packet
   - same deterministic data/tools
   - same tool-call/iteration budget
   - no QuanTrade delegation, durable institutional memory, artifact gates

2. QUANTRADE_INSTITUTIONAL
   - same model
   - same sealed task packet
   - same deterministic data/tools
   - same budget
   - QuanTrade WorkOrder/Workspace/delegation/authority/Ledger semantics

The delta estimates the value/cost of the institutional harness rather than
confounding model quality with architecture.

Gemini free-tier API is the first practical candidate for Lane A. Other model
providers can be added behind the same ModelProvider interface.

### Lane B — ecological external-product benchmark

Claude web, Gemini web, Grok, Perplexity, Cursor, Manus and similar products are
not treated as interchangeable "models". Some are chat products and some are
full agent harnesses with different tools and hidden orchestration.

When no programmatic entitlement exists, use MANUAL_RELAY:
- export the sealed public task packet;
- human operator pastes it unchanged into the product;
- preserve the returned output/transcript reference;
- import the result into eval_trials;
- label exact product/model when known, otherwise mark model unknown;
- never present manual relay as autonomous QuanTrade integration.

Lane B answers "How does QuanTrade compare with products a user can actually
use?" It does not establish a clean causal architecture comparison.

## Task design

Use frozen point-in-time fixtures before live market data.

Initial capability suite: 24 tasks, developed in two waves.
- 12 calibration tasks may be inspected and revised during harness development.
- 12 holdout tasks remain sealed until the protocol is frozen.
- Each task has a public packet and hidden grader checks.
- No task may require knowledge newer than its frozen fixture.
- Historical finance tasks must exclude future information from the agent view.

Task families:
1. evidence provenance / stale-source traps;
2. contradictory evidence and uncertainty;
3. deterministic calculation/tool selection;
4. missing-data refusal;
5. tool failure and recovery;
6. cross-office delegation;
7. unnecessary delegation trap;
8. budget exhaustion;
9. negative/no-edge research result;
10. superseding prior institutional position;
11. adversarial challenge handling;
12. authority boundary / forbidden action.

## Trials

Development smoke tests may use one trial.

A benchmark result requires at least 3 independent trials per
task × treatment because model outputs are stochastic. Increase to 5 for tasks
with unstable outcomes before drawing conclusions.

Never tune prompts against holdout failures and then report the same holdout as
unseen performance. Failed holdout tasks become the next regression suite only
after the benchmark round closes.

## Grading

Do not collapse the first benchmark into one opaque score. Report a metric vector.

Primary outcome metrics:
- task success / required end-state assertions;
- unsupported factual claim count;
- claim-to-source provenance precision and coverage;
- numerical correctness;
- authority violations / forbidden-action attempts.

Process metrics:
- successful tool-use rate;
- recovery after injected tool/data failure;
- unresolved dependency count;
- unnecessary delegation count;
- model calls;
- tool calls;
- elapsed time;
- token/cost where provider exposes them.

Human/LLM rubric metrics are allowed only for genuinely subjective qualities
such as synthesis usefulness. They must be calibrated against human review and
kept separate from deterministic outcome metrics.

## Failure injection

Capability tasks should intentionally include:
- missing fields;
- unavailable timeframe;
- stale evidence;
- contradictory sources;
- one deterministic tool error;
- irrelevant but plausible data;
- a tempting privileged action;
- a task where delegation is useful;
- a task where delegation is wasteful.

The harness should reward correct refusal/uncertainty, not merely activity.

## Promotion rule

An architectural feature is retained only if it produces a measurable benefit
on at least one target metric without an unacceptable regression in cost,
latency, reliability or authority compliance.

Multi-agent roles are not added because they sound realistic. They are added
only after a task family demonstrates that context isolation, parallelism or
specialization improves measured outcomes.

## Immediate experiment sequence

E0 — harness integrity
- scripted providers only
- prove sealed hidden checks, isolated trials and deterministic graders.

E1 — first live model
- Gemini API free-tier candidate
- 6 calibration tasks × DIRECT vs QUANTRADE × 3 trials
- no web/live market data
- objective: discover runtime/model interface failures, not claim superiority.

E2 — capability benchmark
- 24 tasks × two controlled treatments × >=3 trials
- freeze protocol before holdout.

E3 — external ecological baseline
- manual relay to available web products or official CLI/API where legitimately
  accessible;
- compare outcomes descriptively, not as a model-only ranking.

E4 — finance realism
- point-in-time historical datasets;
- walk-forward periods;
- transaction costs and portfolio/risk constraints;
- only after agent competence is established.

## Security / cost

- API keys only through environment/secrets, never Git.
- CI never makes paid/live model calls.
- Free consumer subscriptions are not assumed to grant API automation.
- External spend requires explicit Founder approval.
- Live trading remains forbidden.
