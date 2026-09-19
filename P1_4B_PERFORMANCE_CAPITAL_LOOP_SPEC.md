# QuanTrade P1.4B — Performance → Capital Reconciliation → Reinvestment/Learning Work

Date: 2026-09-19
Status: Implementation candidate

## Purpose

Close the next part of the autonomous operating loop without treating investment profit as automatically reinvestable money.

```
Performance facts
    ↓
Client Capital reconciliation
    ↓
protect current Client cash needs
    ↓
new Capital Plan + Mandate
    ↓
incremental Investable Surplus
    ↓
SPMG deployment/reinvestment planning

Performance review signal
    ↓
ISLL hypothesis review / experiments
```

## Doctrine

1. Performance is recorded as fact before any capital action.
2. Unrealized portfolio value is not automatically deployable cash.
3. Realized cash/income matters only insofar as it appears in current liquid/brokerage cash.
4. Client emergency reserve and planned spending are re-applied every reconciliation.
5. Only the **incremental** deployable cash versus the prior Mandate creates a new reinvestment WorkOrder.
6. A reinvestment WorkOrder is a planning/research instruction, never an order.
7. Strategy underperformance/review can generate ISLL work without Founder prompting.
8. Live execution remains forbidden.

## Performance record

P1.4B records:
- start/end portfolio value
- net external flows
- realized PnL
- investment income
- fees
- taxes
- attribution payload
- deterministic economic PnL = end - start - external flows

The difference between economic PnL and reported realized/income facts remains visible rather than being silently reconciled.

## Capital reconciliation

Inputs:
- Client liquid cash
- brokerage cash
- invested market value
- current Client profile/goals/cashflows
- optional prior Mandate
- optional performance record

The existing P1.4A Capital Planner creates a fresh Capital Plan and Mandate.

The reconciliation then calculates:
- protected liquidity reserve
- deployable cash after Client needs
- previous deployable cash
- incremental investable surplus

Known future spending can therefore absorb newly available cash before any reinvestment work is created.

## Work generation

Incremental surplus > 0:
→ SPMG receives a mandate-constrained deployment/reinvestment planning WorkOrder.

Strategy performance review_required:
→ ISLL receives a strategy performance/hypothesis review WorkOrder.

Both routes reuse P1.4A AutonomousWorkEngine and therefore remain:
- research/backtest capable
- trade forbidden
- policy-change forbidden
- auditable

## Acceptance gate

P1.4B passes when:
1. performance facts persist separately from investment action;
2. realized profit does not itself place an order;
3. current Client spending/reserve needs are protected before reinvestment;
4. only incremental deployable cash creates reinvestment planning work;
5. unchanged cash does not repeatedly generate reinvestment work;
6. strategy review can create ISLL work without Founder prompting;
7. all generated work has no live-trade authority;
8. performance and reconciliation are auditable;
9. no broker side effect exists.
