# Decision — Bind ReviewGate Shadow to Institutional Case Precheck

Status: **APPROVED / SHADOW-ONLY LIVE BINDING**  
Date: **2026-10-04**

## Candidate boundaries reviewed

1. Market indicator generation — rejected for first binding: deterministic measurements exist, but there is no existing AI-review intent to compare against.
2. CEO operating review — deferred: current history explicitly reports model telemetry unavailable, so efficiency measurement would be mostly empty.
3. Institutional Case Precheck — selected: it already emits a sanitized deterministic artifact with Strategy/Client conflict reasons, an existing `ai_call_gate`, explicit no-execution authority, and deletes private Client input before publication.

## Departmental review

- **Client Intelligence:** approve only because binding consumes the sanitized precheck, never the private Client brief.
- **Strategy:** approve comparison against existing routing intent; do not let the new gate redefine mandate.
- **Research:** useful as a disagreement detector between routing systems; unknown/unmapped reasons must remain visible.
- **Risk:** existing gate remains authoritative for current experiment; shadow mismatch cannot suppress review.
- **Portfolio / Committee / Decision Management / Execution:** no path changes permitted.
- **Performance & Learning:** actual model call, cost and latency are currently unavailable; record them as `null`, never infer them from `call_ai=true`.

## Important semantic distinction

`ai_call_gate.call_ai=true` means **routing intent**, not proof that an AI call actually happened.

Therefore this binding measures:
- old-vs-new routing agreement;
- event translation coverage;
- future telemetry gaps.

It does **not** yet measure realized savings.

## Failure isolation

The binding is designed as a post-precheck observer. Its artifact has no authority and the existing Institutional Case precheck remains the source of current routing behavior.

## Promotion

No production replacement is authorized. Promotion requires real call/cost/latency telemetry plus review of every routing disagreement.
