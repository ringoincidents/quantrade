# QuanTrade P1.3C — Strategy Employee Vertical Slice

Date: 2026-09-19
Status: Implementation candidate

## Purpose

Prove that a Strategy employee can receive a broad objective, inspect available workstation capabilities, choose deterministic tools, persist work context, request another office, and revise the same work after a Founder follow-up.

This slice deliberately separates **employee intelligence** from **employee infrastructure**.

## Important validation boundary

CI uses a deterministic `ScriptedModelProvider`.

That proves:
- model-provider interchangeability,
- structured action contract,
- context assembly,
- tool discovery,
- permission enforcement,
- persistent workspace,
- follow-up continuity,
- cross-office requests,
- model/tool audit.

It does **not** prove that a production LLM is intelligent enough to perform the work well.

A live LLM provider adapter and evaluation suite are required before claiming autonomous analytical quality.

## Provider-neutral reasoning contract

The model receives:
- employee role/charter/authority,
- WorkOrder,
- current Task and plan,
- persistent Workspace,
- authorized ToolRegistry descriptions,
- WorkOrder messages/follow-ups,
- recent tool results,
- institutional runtime rules.

The model may return only structured actions:
- TOOL
- UPDATE_PLAN
- REQUEST_WORK
- SAVE_WORKSPACE
- CREATE_ARTIFACT
- FINISH

Runtime code, not the model, executes mutations and enforces permissions/budgets.

## First Strategy workstation

P1.3C installs two generic primitives:
- `data.catalog`
- `data.query`

`data.query` can join authorized tabular sources by symbol and apply arbitrary field or field-to-field predicates. The example investment screen is therefore expressed as data/query arguments, not as a bespoke function such as `screen_growth_foreign_buy()`.

P1.3C uses clearly synthetic Korean-market fixture rows. No claim is made that live KRX, fundamentals, foreign/institution/pension flow, or minute-bar coverage is connected yet.

## Acceptance scenario

Initial Founder objective:
"Find KOSPI/KOSDAQ names with >20% YoY sales growth, two consecutive quarters of improving operating margin, and foreign net buying over the last 10 sessions. Add reasons and risks."

Follow-up:
"Keep only names also net-bought by institutions and pension funds."

Acceptance requires:
1. no bespoke screen function;
2. employee discovers only granted tools;
3. employee can create/update its own Task plan;
4. deterministic query produces the candidate set;
5. Workspace persists tool outputs and analysis state;
6. employee can request another office through WorkRequest;
7. follow-up is visible in the same WorkOrder context;
8. follow-up modifies the existing Task/query rather than requiring new code;
9. model calls and tool calls are auditable;
10. no live order capability.

## Next gate

P1.3C is not complete as an autonomous employee until a real model adapter is connected and evaluated against multiple unseen broad objectives.

That evaluation must measure:
- correct tool discovery/use,
- numerical correctness,
- unnecessary tool calls,
- unsupported claims,
- ability to recover from missing data/tool errors,
- follow-up continuity,
- quality of cross-office delegation,
- reproducibility of final claims.

Do not confuse runtime completion with intelligence validation.
