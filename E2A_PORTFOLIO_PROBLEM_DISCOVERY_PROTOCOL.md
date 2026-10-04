# E2-A Portfolio Problem Discovery Protocol v0

Date: 2026-09-20
Status: calibration protocol
Purpose: test whether additional QuanTrade capabilities improve **what deserves attention**, before testing how a problem is solved.

## 1. Research question

Given the same Client portfolio snapshot, can a system identify the material problems/opportunities that deserve further investigation while ignoring plausible but decision-irrelevant noise?

E2-A does **not** test stock picking, final allocation, or multi-agent architecture.

It tests the capability stack before organizational topology.

## 2. Treatments

All treatments use the same model, system action contract, output schema, iteration ceiling, and public portfolio snapshot.

### A — SNAPSHOT_ONLY
Strong LLM + portfolio snapshot.
No hidden QuanTrade memory or deterministic diagnostic feed.

This is the official minimum baseline QuanTrade must beat.

### B — SNAPSHOT_PLUS_DIAGNOSTICS
A + deterministic portfolio/risk diagnostics exposed through a read-only tool.

Tests the marginal value of deterministic financial machinery.

### C — SNAPSHOT_PLUS_DIAGNOSTICS_PLUS_MEMORY
B + persistent investment-memory records exposed through a read-only tool.

Tests the marginal value of time-crossing thesis/decision memory.

This is intentionally **not** Single Agent vs Institution. If B/C fail to add value here, wrapping them in departments would not rescue the underlying capability.

## 3. Output contract

The model must FINISH with JSON only:

{
  "issues": [
    {
      "issue_type": "<allowed vocabulary or OTHER>",
      "priority": "HIGH|MEDIUM|LOW",
      "action": "IGNORE|MONITOR|INVESTIGATE|RISK_REVIEW",
      "reason": "<brief portfolio-relevance reason>",
      "evidence_refs": ["<public/tool refs>"]
    }
  ],
  "no_other_material_issues": true|false
}

Allowed issue vocabulary:
- FACTOR_CONCENTRATION
- THESIS_BREAK
- LIQUIDITY_MISMATCH
- FX_EXPOSURE
- CORRELATION_SHIFT
- EVIDENCE_STALENESS
- VALUATION_RISK
- CLIENT_CONSTRAINT
- OTHER

The vocabulary makes deterministic calibration grading possible without requiring the model to know hidden answer IDs.

## 4. Hidden grading

Each synthetic case defines:
- material_issue_types: issues that should be escalated;
- optional_issue_types: reasonable but nonessential observations;
- forbidden_false_positive_types: unsupported claims;
- decoy_refs: salient information that should not cause unnecessary investigation;
- minimum/maximum issue count;
- expected action for selected issue types when necessary.

Primary metrics:
- Material Issue Recall
- Material Issue Precision
- False Research Rate
- Decoy Escalation Rate
- Appropriate No-Action Rate
- Evidence/tool provenance
- Model calls / tool calls
- Provider token usage
- serialized context size
- elapsed time

Do not collapse these into one flattering score during calibration.

## 5. Initial synthetic case families

### PD-01 Hidden factor concentration
Several apparently diversified holdings share the same AI/data-center capital-spending driver. Snapshot-only has enough clues to form a hypothesis; deterministic diagnostics expose common factor concentration.

### PD-02 Thesis break visible only through memory
Current company metrics look acceptable in isolation, but a prior decision explicitly required a margin floor that has now been breached. Memory should materially improve detection.

### PD-03 Liquidity/client constraint
Portfolio assets are individually reasonable, but near-term Client cash need makes the allocation unsafe. Tests whether Client constraints outrank interesting market narratives.

### PD-04 Correlation regime shift
Historical diversification has weakened. Deterministic diagnostics expose a recent correlation jump without prescribing a decision.

### PD-05 Salient decoy news
A dramatic headline concerns a tiny position with negligible portfolio impact while a quieter concentration issue matters more. Tests selective attention, not headline summarization.

### PD-06 Healthy portfolio / zero-research case
No material issue is present. A successful system should be willing to return no INVESTIGATE/RISK_REVIEW items.

## 6. Fairness

This experiment tests **incremental information/capability value**, so B and C intentionally receive additional legitimate QuanTrade information.

Fairness means:
- same model;
- same public snapshot;
- same output schema;
- same iteration ceiling;
- same hidden truth;
- deterministic diagnostic/memory tools return only information that the named capability is supposed to provide;
- no hidden expected answer or grader language appears in public prompts;
- no future information;
- no treatment-specific coaching.

Token/tool cost is measured rather than artificially equalized in E2-A. Later architecture comparisons must use matched or explicitly budgeted inference resources.

## 7. Anti-leakage rules

Before any live run:
1. assert hidden issue types are absent from treatment-specific tool descriptions unless they are generic vocabulary;
2. assert hidden expected values are absent from public task text;
3. assert decoy/material labels never enter model context;
4. inspect a serialized first-turn context for each treatment in CI;
5. run scripted-model tests before spending live API quota.

## 8. Promotion rule

E2-A is successful as an experiment if it tells us whether diagnostics and memory change discovery quality/cost. It does not need QuanTrade to win.

Possible findings:
- A ~= B ~= C: simplify; extra capability is not justified for these cases.
- B > A, C ~= B: deterministic diagnostics matter; persistent memory does not yet.
- C > B: institutional memory has measurable value.
- extra information increases false positives/noise: attention policy needs filtering, not more context.

## 9. What follows E2-A

Only after E2-A is calibrated:
- E2-B Problem Resolution Architecture: Single Agent vs Independent Ensemble vs Specialist Team vs Institutional Process on the **same discovered problem**.
- Historical Replay with point-in-time data.
- Dynamic Router design only after task-family evidence exists.

No production Attention Engine or Dynamic Router is authorized by E2-A.
