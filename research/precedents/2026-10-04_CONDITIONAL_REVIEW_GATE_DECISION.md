# Organizational Review — Conditional AI / Research Review Gate

Status: **APPROVED FOR SANDBOX IMPLEMENTATION**  
Date: **2026-10-04**  
Direction: **EXTENDS** the canonical Conditional AI Invocation principle  
Scope: deterministic review routing only

## 1. Mission

Question: can QuanTrade reduce unnecessary model/research calls without weakening organizational safety or turning a routing component into an investment authority?

Proposed capability:

```text
structured organizational events
        ↓
deterministic ReviewGate (D0)
        ↓
NO_REVIEW | BOUNDED_REVIEW | MANDATORY_REVIEW
```

The gate does **not** call an LLM. A later orchestrator may use the result to decide whether an authorized bounded review should be created.

## 2. Organizational review

This section records reviewable positions and objections, not hidden model chain-of-thought.

### Client Intelligence

**Potential benefit:** avoids repeatedly exposing/requesting Client context when no material downstream question exists.

**Objection:** a Client mandate or liquidity conflict must never be filtered as routine noise.

**Required safeguard:** `CLIENT_MANDATE_CONFLICT` and `LIQUIDITY_CONSTRAINT_BREACH` force `MANDATORY_REVIEW`.

### Strategy / Investment Mandate

**Potential benefit:** preserves attention for changes that can alter capital posture.

**Objection:** the gate must not infer a new mandate or decide that a conflict is acceptable.

**Required safeguard:** classification only; no mandate mutation.

### Research

**Potential benefit:** routine market updates need not consume reasoning-model calls.

**Objection:** over-aggressive thresholds can hide regime changes or unresolved evidence.

**Required safeguard:** material changes request bounded review; unresolved departmental disagreement cannot become `NO_REVIEW`.

### Portfolio Management

**Potential benefit:** reduces noise reaching portfolio deliberation.

**Objection:** review routing must not become a buy/sell signal or position-sizing engine.

**Required safeguard:** no PortfolioProposal output and no security/action semantics in the gate.

### Risk & Compliance

**Position:** conditional approval.

**Primary objection:** cost optimization must never suppress risk escalation.

**Required safeguard:** risk-policy breach forces mandatory review regardless of numerical materiality; the gate cannot override a risk veto.

### Investment Committee

**Position:** the gate is below Committee authority.

A `MANDATORY_REVIEW` result is not a Committee decision. A `NO_REVIEW` result cannot approve an investment action.

### Decision Management

**Potential benefit:** explicit reasons make later routing auditable.

**Objection:** review necessity and execution timing are separate.

**Required safeguard:** no NOW/DEFERRED/CONDITIONAL execution state is created here.

### Execution

**Position:** no execution dependency should be introduced in this sandbox precedent.

**Required safeguard:** `execution_authorized = false` invariant.

### Performance & Learning

**Potential future benefit:** review frequency, avoided calls, false negatives and escalations can later be measured.

**Objection:** claiming cost savings before telemetry exists would be unsupported.

**Required safeguard:** this precedent makes no quantified efficiency claim. Measurement is follow-up work.

## 3. Holdings OS review

Mapped to the Holdings operating model:

- **D0:** this deterministic gate.
- **D1/D2:** remain downstream and are not implemented here.
- **Authority:** D0 may recommend review necessity but receives no investment authority.
- **Knowledge:** reasons are transportable as an Artifact.
- **Responsibility:** the downstream Mission/role remains responsible for the actual review.
- **Escalation:** mandatory organizational conflicts move upward; they are not silently swallowed.

This follows: authority remains vertical while knowledge/reasons can move horizontally.

## 4. Impact assessment

| Area | Expected impact | Risk |
|---|---|---|
| Client Intelligence | fewer unnecessary context requests later | low |
| Strategy | explicit mandate-conflict escalation | low |
| Research | fewer routine review candidates later | medium |
| Portfolio | less noise; no direct authority | low |
| Risk | mandatory escalation path | medium if misconfigured |
| Committee | none directly | low |
| Decision Mgmt | receives auditable reason later | low |
| Execution | none | very low |
| Cost/latency | potentially lower after orchestration integration | unmeasured |

### Blast radius decision

The implementation is acceptable **only as a sandbox classifier** because:
1. it does not call AI;
2. it does not suppress mandatory Client/Risk conflicts;
3. it does not create domain decisions;
4. it does not touch execution;
5. thresholds are explicit policy inputs;
6. invalid materiality fails closed.

## 5. Decision

**APPROVE — SANDBOX ONLY.**

Not approved:
- wiring it directly to production model invocation;
- claiming measured cost savings;
- using `NO_REVIEW` as permission to trade;
- allowing the gate to override Risk or Client constraints.

## 6. Implementation binding

Implemented as:
- `quantrade/capabilities/review_gate.py`
- `tests/capabilities/test_review_gate.py`

Future promotion requires telemetry that measures:
- total candidate events;
- NO/BOUNDED/MANDATORY distribution;
- model calls actually avoided;
- review reversals / false negatives;
- Risk/Client forced escalations;
- cost and latency deltas.

## 7. Precedent for future LLM workers

A future worker proposing a material capability should not jump from idea to code.

Minimum durable flow:

```text
Mission
→ departmental positions
→ objections / safeguards
→ Holdings authority review
→ impact + blast-radius assessment
→ Proposal
→ Decision
→ bounded implementation
→ verification evidence
→ promotion or rejection
```

The purpose is not ceremonial multi-agent roleplay. A department should participate only when it owns a real affected question or authority boundary.
