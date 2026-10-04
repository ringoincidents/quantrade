# Trading Capability Provider Contract

Status: **ACTIVE ARCHITECTURE CONTRACT**  
Effective date: **2026-10-04**

This contract defines how external trading engines may enter QuanTrade without owning QuanTrade's domain semantics.

## Provider boundary

A provider supplies a bounded capability. It does not receive organizational authority.

Minimum provider metadata:

```text
provider_id
capability
implementation
version_or_revision
license
deterministic
network_access
capital_effect
evidence_effect
status
```

Allowed `status` values:

```text
RESEARCH
SANDBOX
PAPER
APPROVED
DISABLED
RETIRED
```

## Invariants

1. Provider output is not automatically canonical Evidence.
2. Provider output is not an Investment Committee decision.
3. Provider code cannot raise its own authority level.
4. Risk limits are supplied by QuanTrade, never invented by a provider.
5. Live execution requires a separately authorized execution path.
6. Provider/version must be identifiable in generated artifacts for reproducibility.
7. A provider can be disabled without rewriting historical Decisions.
8. Replacement providers should satisfy the same QuanTrade-facing contract.

## First target seams

The first implementation seams to standardize are:

```text
MarketDataProvider
FeatureProvider
SimulationProvider
PortfolioAnalyticsProvider
ExecutionProvider
PerformanceProvider
```

`RiskPolicy`, `CommitteeDecision`, `DecisionPlan`, Client Mandate and Evidence promotion remain QuanTrade-native authority-bearing components.

## Development consequence

When the current OSS research selects candidates, integrations should be implemented behind these seams rather than importing a framework's application model into the QuanTrade core.

The first PoC should prove **replaceability**: the same bounded QuanTrade case should be runnable with a reference/native provider and at least one external provider, with differences captured as evidence rather than hidden.
