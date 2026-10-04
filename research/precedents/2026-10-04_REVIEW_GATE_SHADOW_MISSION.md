# Mission Record — ReviewGate Shadow Measurement

Status: **SANDBOX / SHADOW MEASUREMENT IMPLEMENTED**  
Date: **2026-10-04**  
Parent precedent: `2026-10-04_CONDITIONAL_REVIEW_GATE_DECISION.md`

## Mission

Measure whether the deterministic ReviewGate could reduce unnecessary review work **without allowing it to influence the actual QuanTrade path**.

## Departmental positions

### Performance & Learning — Mission owner
Needs measurable observations before any efficiency claim. Owns the shadow summary, not production promotion.

### Research
Accepts shadow observation because no review is actually suppressed. Requires potential false negatives to remain visible.

### Risk & Compliance
Requires mandatory-risk discrepancies to be surfaced. Shadow mode may flag a missed escalation but cannot silently repair or override the historical path.

### Strategy / Client Intelligence
Client mandate and liquidity conflicts remain mandatory classifications. Private Client values are not required by this measurement artifact; event classification is sufficient.

### Portfolio / Committee / Decision Management
No portfolio proposal, Committee decision, or timing state may change from shadow output.

### Execution
No effect permitted.

## Holdings mapping

```text
Mission: evaluate ReviewGate usefulness
  ↓
Work: observe gate recommendation beside actual path
  ↓
Artifact: ShadowReviewRecord / summary
  ↓
Proposal: future promotion proposal (NOT created here)
  ↓
Decision: future departmental/HQ decision
```

The Artifact is evidence for a later Proposal. It is not itself authority.

## Metrics recorded

- gate distribution;
- avoidable-review **candidates**;
- potential false negatives;
- escalation matches;
- observed model-cost field when supplied;
- observed latency field when supplied.

## Anti-overclaim rule

`claimed_savings_usd` is always zero in this implementation.

An actual historical call being classified `NO_REVIEW` only creates an **avoidable-review candidate**. It does not prove the call was unnecessary or that its cost would safely have been saved.

## Promotion gate

Shadow data cannot automatically enable production routing.

A future promotion review must include:
1. sufficient sample size;
2. manual inspection of potential false negatives;
3. Risk review of mandatory escalations;
4. Research review of missed material events;
5. Performance & Learning analysis of actual cost/latency;
6. explicit Proposal and Decision.

## Implementation

- `quantrade/capabilities/review_gate_shadow.py`
- `tests/capabilities/test_review_gate_shadow.py`

This is intentionally not wired into live orchestration yet. Integration requires identifying a stable existing event boundary and proving that observation itself does not expose private Client data or alter runtime behavior.
