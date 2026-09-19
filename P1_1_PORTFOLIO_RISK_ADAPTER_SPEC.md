# QuanTrade P1.1 — Portfolio / Risk Adapter Spec

Date: 2026-09-19  
Status: Ready for implementation  
Base: P1.0 Institutional Kernel (validated and merged to architecture branch)

## Objective

Connect the first existing real QuanTrade capabilities to the new institutional runtime without turning legacy JSON files into the new source of truth.

P1.1 connects:
- `real_portfolio.json` → immutable `PortfolioSnapshot`
- deterministic calculations in `portfolio_report.py` → institutional `RiskAssessment`
- rule matches → normalized Events that may be triaged by the P1 kernel

This is an adapter/migration step, not a rewrite of portfolio policy.

## Safety / policy boundary

1. Read-only integration only.
2. No broker order path.
3. No mutation of `real_portfolio.json`.
4. No use of `pending_actions.json`.
5. No activation of `autoexec.py`.
6. Provisional thresholds remain explicitly provisional.
7. A rule match is an Event/observation, not automatically a HIGH Case.
8. Event triage and Case materiality remain separate.
9. Mapping drift must be surfaced as data-quality evidence, not silently repaired.
10. Existing portfolio/risk calculations remain deterministic.

## Current source facts

Current `real_portfolio.json` schema:
- synced_at
- cash
- positions[]
  - symbol
  - name
  - market_country
  - currency
  - quantity
  - avg_price
  - current_price
  - eval_amount
  - eval_amount_krw
  - return_pct

Existing deterministic functions to preserve:
- `portfolio_report.compute_positions(real)`
- `portfolio_report.evaluate_rules(...)`
- `portfolio_report.build_risk_engine(...)`

Known limitations:
- `THRESHOLDS.provisional == true`
- `RISK_ENGINE.provisional == true`
- MDD budget is explicitly an unrealized-return proxy, not true peak-to-trough MDD.
- volatility/correlation require price history and may be unavailable.
- asset/role mapping can drift from current holdings.

## Required adapters

### RealPortfolioSnapshotAdapter

Input:
- parsed real portfolio dict

Output:
- canonical snapshot payload suitable for `InstitutionalKernel.add_snapshot()`

Must:
- preserve source `synced_at`
- preserve cash and position facts
- include calculated total assets / weights from deterministic code
- include source marker `real_portfolio_read_only`
- never mutate source data
- include a data-quality section

### PortfolioDataQualityAudit

Compare current holdings against:
- `asset_class_mapping.json`
- `portfolio_role_mapping.json`

Report:
- held symbols missing from active asset-class mapping
- held symbols missing from active role mapping
- active mappings whose symbols are no longer held
- provisional policy/config flags

Do not automatically edit mappings.

### PortfolioRuleEventAdapter

Convert deterministic rule matches into normalized institutional Events.

Example:
`{"rule":"집중도", ...}`
→ event_type `PORTFOLIO_RULE_MATCH`
→ payload contains rule, symbol, observed, threshold, fact, policy provisional flag.

This Event is not itself a trade instruction and does not receive LOW/MEDIUM/HIGH at ingestion.

### DeterministicRiskAdapter

Input:
- canonical portfolio snapshot
- optional symbol price histories
- mapping/config

Output:
- RiskAssessment result containing the existing deterministic Risk Engine sections:
  - position sizing calculations
  - MDD-budget proxy
  - concentration
  - correlation
  - cost-adjusted returns
- policy version / provisional status
- limitations / missing-data notes

No LLM call is permitted.

## Integration demonstration

Using repository fixture data or synthetic copy of its schema:

1. Load a read-only portfolio.
2. Build canonical PortfolioSnapshot.
3. Run data-quality audit.
4. Run deterministic portfolio/risk calculations.
5. Convert any rule match to Event(s).
6. Ingest Event(s) into InstitutionalKernel.
7. Verify that Event triage does not bypass the Case workflow or directly create a Founder decision.
8. Persist Snapshot/RiskAssessment to a Case only when a Case exists.
9. Verify no source JSON file changed.

## Tests

- source portfolio dict remains byte/structurally unchanged after adapter
- total assets and position weights match `compute_positions`
- missing/obsolete mapping drift is reported
- provisional policy status survives into outputs
- rule match becomes Event, not Decision
- no rule Event directly enters Founder Desk
- deterministic risk output can be attached to a Case
- missing price history is represented as missing/limited, not fabricated
- no broker/execution imports in adapter package

## Gate to P1.2

P1.1 passes when real-account-shaped read-only data can flow:

`real_portfolio → PortfolioSnapshot → deterministic Portfolio/Risk → Event → optional Case`

with data-quality drift visible, provisional policy clearly labelled, no live-order side effect, and no legacy approval queue dependency.
