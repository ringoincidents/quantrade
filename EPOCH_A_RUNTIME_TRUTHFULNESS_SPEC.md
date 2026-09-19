# QuanTrade Development Era II — Epoch A: Runtime Truthfulness

Date: 2026-09-19  
Status: Implementation started

## Purpose

Epoch A makes existing institutional claims true before QuanTrade gains a scheduler or broader autonomy.

The first failure being corrected is:

```
SYSTEM creates office-level WorkOrder
→ record exists
→ no concrete employee necessarily owns it
```

and the related dependency failure:

```
employee requests another office
→ request remains open
→ employee can still declare parent WorkOrder completed
```

## First vertical proof

Required lifecycle:

```
SYSTEM WorkOrder(recipient_office)
→ capable employee claims office work
→ employee creates cross-office WorkRequest
→ parent FINISH is blocked
→ receiving employee claims request
→ request materializes as linked child WorkOrder
→ child completes
→ WorkRequest completes
→ waiting parent resumes
→ parent may complete only after dependencies are terminal
→ Ledger reconstructs the lifecycle
```

## Invariants

1. Office-addressed work is not considered owned until a concrete ACTIVE employee claims it.
2. An employee cannot claim another office's work.
3. Cross-office requests create bounded child WorkOrders when accepted.
4. Child authority remains research-only; live trade remains forbidden.
5. A model cannot override dependency state by emitting FINISH.
6. WorkOrder completion is a runtime decision, not a model assertion.
7. Completing a request child resolves the request and wakes a waiting parent.
8. The full lifecycle is auditable in the institutional Ledger.

## Explicit non-goals

This slice does not yet add:
- continuous scheduler;
- background workers;
- leases/heartbeats;
- retry/dead-letter queues;
- production data providers;
- live execution;
- committee artifact gates.

Those follow only after the synchronous lifecycle is correct and tested.

## Next Epoch A obligations

After this vertical proof:
1. durable dispatcher/worker claim semantics with leases and crash recovery;
2. schema version/migrations;
3. P1.4 time-indexed cashflow correction;
4. minimal P1.3F parallel artifact readiness gate;
5. restart/recovery integration test;
6. only then attach scheduling/event triggers.


## Durable claim / recovery slice

Epoch A now adds a versioned migration layer and durable worker leases.

Runtime distinction:

```
Employee ownership = institutional responsibility
Worker lease       = temporary process execution right
```

A worker crash must not permanently strand a WorkOrder. The lease expires,
a restarted worker can reclaim the same employee-owned WorkOrder, and the
existing Workspace remains the recovery checkpoint.

Required invariants:
1. structural changes after Epoch A are recorded in `schema_migrations`;
2. migrations are forward-only and idempotent on restart;
3. active leases cannot be stolen by another worker;
4. heartbeat extends only the owning worker's live lease;
5. expired leases can be reclaimed with a higher generation;
6. WorkOrder and Workspace survive process restart;
7. claim/reclaim/release remain Ledger-visible;
8. live execution authority is unchanged.
