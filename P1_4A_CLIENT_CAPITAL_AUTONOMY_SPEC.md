# QuanTrade P1.4A — Client Capital → Mandate → Autonomous Work

Date: 2026-09-19
Status: Implementation candidate

## Why this phase exists

P1.3 proved that employees can receive WorkOrders, reason through a provider-neutral loop, use granted tools, preserve Workspace state, communicate across offices, and operate under institutional controls.

That is not enough.

If the Founder must continuously invent and issue every research task, the Founder becomes QuanTrade's human scheduler. That violates the intended Personal Portfolio Management System / Virtual Investment Firm operating model.

P1.4 begins closing the operating loop around the Client.

## Operating doctrine

The Founder has two distinct roles:

1. **Client** — owns the life goals, cash needs, capital and explicit risk constraints.
2. **Founder / final control authority** — resolves material policy, exception and high-attention decisions.

Routine institutional work should be generated from Client facts + mandate + observed portfolio/research state, not from constant Founder prompting.

## P1.4A flow

```
Client Intelligence
    ↓
Capital Plan (deterministic)
    ↓
Investment Mandate
    ↓
Autonomous Work Engine
    ↓
WorkOrders
    ├─ CCO
    ├─ SPMG
    ├─ IPRO
    └─ ISLL
```

P1.4A does **not** execute investments.

## Client Intelligence

Client facts are versioned. Updating a Client profile never silently overwrites the prior profile.

Current explicit planning inputs may include:
- essential monthly spending
- emergency reserve months
- known income
- known planned expenses
- goals and target dates
- explicit maximum drawdown constraint
- planning-return ceiling
- research universe
- prohibited actions

The runtime must not infer psychological risk tolerance from LLM conversation or employee behavior.

## Capital Plan

The deterministic Capital Planner calculates:
- emergency reserve
- scheduled reserved outflows
- liquidity reserve
- investable capital available now
- recurring monthly investable surplus
- goal-linked required planning return
- planning conflicts

The required return is a **planning rate**, not an expected-return forecast.

If a goal requires a rate above the Client's explicit planning ceiling, the system records a conflict. It must not silently increase risk.

## Investment Mandate

The Mandate carries:
- investable capital
- monthly investable surplus
- required planning return
- explicit max drawdown
- liquidity reserve
- research universe
- prohibited actions
- planning conflicts
- authority boundaries

P1.4A always sets:
- research = allowed
- backtest = allowed
- internal work generation = allowed
- live execution = forbidden
- silent policy change = forbidden
- human approval required for live execution

The Mandate contains no security recommendation.

## Autonomous Work Engine

The engine deterministically recognizes *work gaps*, not investments.

Initial triggers:
- CAPITAL_PLAN_CONFLICT → CCO
- STRATEGY_COVERAGE_GAP → SPMG
- ALLOCATION_GAP → SPMG
- RISK_POLICY_BREACH → IPRO
- NEW_INVESTABLE_SURPLUS → SPMG
- STRATEGY_REVIEW_REQUIRED → ISLL

Generated WorkOrders can then be handled by P1.3 employee reasoning loops.

Trigger fingerprints make repeated evaluation idempotent so unchanged state does not spam employees.

## Reinvestment doctrine

Performance or new cash does not automatically become deployable capital.

The intended closed loop is:

```
Performance / income / realized cash
    ↓
Client Capital reconciliation
    ↓
reserve known Client needs
    ↓
Investable Surplus
    ↓
Mandate-constrained deployment/research WorkOrder
    ↓
institutional review
```

P1.4A implements the Client Capital/Mandate foundation and the NEW_INVESTABLE_SURPLUS work trigger. Full performance-attribution-to-capital reconciliation is a later P1.4 slice.

## Acceptance gate

P1.4A passes when:
1. Client profile history is versioned.
2. reserved Client money is excluded before investable capital is calculated.
3. required return is deterministic and labelled as planning, not forecast.
4. impossible/aggressive planning conflicts do not silently raise risk.
5. Mandate preserves explicit risk/liquidity/authority constraints.
6. Strategy/reinvestment/risk/learning work can be generated without Founder prompting.
7. repeated unchanged triggers are idempotent.
8. generated work has no trade/policy-change authority.
9. all capital/mandate/work-generation transitions are auditable.
10. no broker side effect exists.
