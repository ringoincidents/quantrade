> **Sequence correction — 2026-09-19**
>
> This design remains valid but is deferred to **P1.3F**.
> It must not be implemented as the next layer by itself.
> QuanTrade first needs the Employee Runtime, Department Workstations, and common Organizational Communication Protocol defined in `P1_3_EMPLOYEE_RUNTIME_SPEC.md`. Artifact gates then govern the outputs those employees actually produce.
>
# QuanTrade P1.3 — Parallel Institutional Review & Artifact Gates

Date: 2026-09-19
Status: Initial vertical slice implemented

## Finding

The P1.0 kernel proved persistence, ledger, immutability and Founder routing, but its current Case transition chain is too linear:

RESEARCH → PORTFOLIO_REVIEW → RISK_REVIEW → ADVERSARIAL_REVIEW → COMMITTEE

That sequence is useful as a test scaffold, not as the final institutional operating model. In the target firm, Research, Portfolio, Risk and Adversarial Review may work in parallel and revise their outputs.

## Objective

Replace stage-order dependence with artifact/gate readiness while preserving:
- Case as operational unit
- append-only LedgerEvent history
- dissent
- immutable Founder decisions
- Founder attention only after institutional review
- no broker side effects

## P1.3 model

A Case has a coarse institutional phase. Offices produce artifacts independently.

Required Committee-entry artifacts:
1. at least one canonical Evidence record
2. at least one Portfolio institutional position
3. deterministic RiskAssessment tied to a PortfolioSnapshot
4. at least one Risk institutional position
5. at least one Adversarial Challenge

Committee readiness is computed from artifacts, not from the order in which offices worked.

### Parallelism

Allowed examples:
- Risk can assess a snapshot while Research continues adding Evidence.
- ARU can challenge a Portfolio thesis before Research is “finished”.
- Portfolio may supersede its position after new Evidence.
- Risk may issue a new assessment/position after the Portfolio position changes.

The ledger records each artifact/revision. Old records are not overwritten.

## Gate semantics

`committee_readiness(case_id)` returns:
- ready: bool
- present artifacts
- missing artifacts
- latest relevant artifact IDs
- unresolved challenges

`enter_committee(case_id)`:
- succeeds only if readiness is true
- does not erase dissent
- appends a ledger event describing which artifact IDs satisfied the gate

No numeric completion percentage.

## Coarse Case phase

P1.3 should introduce or migrate toward:
- OPEN
- INSTITUTIONAL_REVIEW
- COMMITTEE
- FOUNDER_PENDING
- DECIDED
- DECISION_MANAGEMENT
- EXECUTION_PENDING
- OUTCOME_TRACKING
- CLOSED

Legacy granular review statuses may remain readable during migration but new P1.3 orchestration must not require their serial order.

## Supersession

InstitutionalPosition already supports `supersedes_id`.

P1.3 readiness should use the latest non-superseded position for each required office while preserving all historical positions.

RiskAssessment remains append-only; latest assessment is selected by creation order and must remain tied to its snapshot and policy version.

## Office identifiers for the first vertical slice

- Portfolio: SPMG
- Risk: IPRO
- Adversarial review: ARU
- Research/Evidence: IID / EIF provenance

These identifiers are runtime role labels, not separate LLM agents.

## Tests

- Portfolio and Risk artifacts can be produced in either order
- Challenge can be recorded before or after Risk position
- Committee gate fails with explicit missing artifacts
- Committee gate passes when all required artifacts exist
- superseded Portfolio/Risk positions remain in history but readiness selects current position
- unresolved ARU challenge survives Committee entry
- Founder is not notified merely because Committee gate becomes ready
- no completion percentages
- no broker/autoexec/pending_actions dependency
- ledger reproduces the artifact set used to enter Committee

## Deferred governance fork

P1.3 does NOT decide whether IPRO has an absolute veto or whether Founder may override a policy breach through a documented PolicyException.

That authority rule is a Founder/CEO governance decision and must be decided before live Decision Control / execution authority is implemented.

## Gate to P1.4

P1.3 passes when a Case can collect Evidence, Portfolio, Risk and ARU work in parallel and enter Committee based on artifacts rather than a hard-coded departmental sequence.


## Epoch A implementation note

The first artifact-gate vertical slice is now implemented after Employee Runtime,
workstations, durable routing and restart recovery.

Implemented:
- coarse `INSTITUTIONAL_REVIEW` phase while legacy granular states remain readable;
- `committee_readiness(case_id)`;
- `enter_committee(case_id)`;
- latest non-superseded SPMG/IPRO position selection;
- deterministic RiskAssessment + same-Case PortfolioSnapshot requirement;
- ARU office provenance on Challenges;
- unresolved dissent preservation;
- Ledger record of the exact artifact IDs satisfying Committee entry;
- no Founder routing merely because the gate becomes ready.

This slice does not decide the deferred IPRO-veto / Founder-override governance fork.
