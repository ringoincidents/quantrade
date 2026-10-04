# Trading OSS Research & Adoption Program

Status: **ACTIVE / OFFICIAL RESEARCH PROGRAM**  
Effective date: **2026-10-04**  
Authority: subordinate to `QUANTRADE_CANONICAL_VISION.md`  
Direction classification: **EXTENDS**

## 1. Purpose

QuanTrade will continuously study mature open-source trading systems, but will not become a collection of copied trading bots.

The objective is to convert external engineering knowledge into durable QuanTrade capabilities while preserving QuanTrade's identity as an AI-native Private Investment Office.

This record exists so future developers and AI research workers can see:
- what external systems were investigated;
- what was learned;
- what was rejected and why;
- what was adopted as a dependency;
- what was reimplemented as a QuanTrade-native capability;
- what evidence justified promotion.

## 2. Canonical rule

External OSS is **input, not authority**.

An external project's architecture, popularity, backtest result or production claim does not override:
- Client mandate;
- QuanTrade authority boundaries;
- deterministic risk controls;
- evidence/provenance requirements;
- validation gates;
- execution approval.

## 3. Adoption modes

Every candidate must end in one of these dispositions:

- **DEPEND** — mature commodity capability; use the library directly behind an adapter.
- **ADAPT** — reuse a bounded component while hiding it behind a QuanTrade interface.
- **LEARN_AND_BUILD** — study the design, then implement the capability natively because domain semantics, governance, observability or differentiation matter.
- **EXPERIMENT_ONLY** — useful for a bounded laboratory but not trusted as production infrastructure.
- **REJECT** — unsuitable because of architecture, maintenance, license, security, validation or product fit.

No candidate may silently move from research to production dependency.

## 4. Capability map

Research should classify candidates against the investment-company loop:

| QuanTrade capability | What to study externally | Default bias |
|---|---|---|
| Market/Data adapters | broker/exchange connectors, normalized feeds | DEPEND / ADAPT |
| Market State Compiler | indicators, features, event/time-series computation | ADAPT / LEARN_AND_BUILD |
| Research laboratory | factor research, notebooks, ML pipelines | ADAPT |
| Backtest/Simulation | event engines, fills, costs, slippage, clocks | ADAPT / LEARN_AND_BUILD |
| Portfolio engine | allocation, optimization, rebalancing | ADAPT / LEARN_AND_BUILD |
| Risk engine | exposure, limits, drawdown, scenario/stress | LEARN_AND_BUILD |
| Execution adapters | broker APIs, FIX, order primitives | DEPEND / ADAPT |
| Execution policy | authorization, timing, safe order lifecycle | LEARN_AND_BUILD |
| Performance & Learning | attribution, benchmark, execution quality | ADAPT / LEARN_AND_BUILD |
| AI orchestration | model-assisted interpretation and escalation | QUANTRADE-NATIVE |

## 5. Evaluation record

Each investigated project must have a durable record containing:

- project/repository and pinned revision or release;
- investigation date;
- license and commercial-use notes;
- maintenance/activity evidence;
- architecture summary;
- capability mapping;
- useful modules/patterns;
- integration boundaries;
- data/security implications;
- deterministic vs probabilistic responsibilities;
- validation evidence;
- operational failure modes;
- disposition;
- rationale;
- implementation binding, if any;
- later supersession or retirement.

Popularity is discovery evidence, not adoption evidence.

## 6. Promotion gate

The path is:

```text
DISCOVERED
→ REVIEWED
→ LICENSE_CLEARED
→ SANDBOXED
→ BENCHMARKED
→ SHADOW/PAPER
→ APPROVED_CAPABILITY
→ PRODUCTION_BINDING
```

A stage may be skipped only by an explicit governed decision.

For anything that can affect orders, capital, risk limits or canonical Evidence, promotion additionally requires:
1. deterministic boundary tests;
2. failure-mode tests;
3. reproducible fixtures;
4. provenance;
5. authority-boundary tests;
6. rollback/disable path.

## 7. Architecture rule: adapters, not ownership inversion

External engines sit below QuanTrade domain semantics.

```text
Client / Mandate
      ↓
QuanTrade Research / Portfolio / Risk / Committee
      ↓
QuanTrade capability interfaces
      ↓
Adapters
      ↓
OSS engine / broker / exchange / data provider
```

An OSS framework must not become the place where Client policy, Committee authority or canonical investment decisions live.

This makes LEAN, NautilusTrader, vectorbt, Qlib, broker SDKs or future alternatives replaceable implementation providers rather than QuanTrade's organizational core.

## 8. What should usually NOT be reinvented

Unless research finds a concrete reason:
- protocol parsing;
- broker/exchange HTTP/WebSocket plumbing;
- FIX primitives;
- standard indicators;
- numerical optimization primitives;
- common dataframe/time-series operations;
- basic order-type serialization.

## 9. What QuanTrade should own

QuanTrade's differentiation should remain in:
- Client-aware mandate translation;
- evidence/provenance model;
- Market State semantics optimized for AI consumption;
- Research→Portfolio→Risk separation;
- deterministic independent risk policy;
- Committee/DecisionPlan governance;
- conditional AI invocation;
- authority-aware execution;
- decision/outcome learning;
- capability promotion and audit history.

## 10. Initial candidate universe

The 2026-10 research wave explicitly includes, without pre-judging adoption:
- QuantConnect LEAN
- NautilusTrader
- Microsoft Qlib
- FinRL
- vectorbt
- Backtrader
- Zipline-family projects
- Hummingbot
- Freqtrade
- vn.py
- Jesse
- PyAlgoTrade
- QuickFIX-family implementations
- OpenBB
- additional candidates discovered during research.

Candidate names in this section are a research queue, **not approved dependencies**.

## 11. Required output of the current deep-research wave

The active research must produce:
- S/A/B ranking;
- capability-by-capability comparison;
- top repositories to clone/read;
- license red flags;
- target architecture mapping;
- 30/60/90-day PoC roadmap;
- DEPEND vs ADAPT vs LEARN_AND_BUILD recommendations;
- explicit recommendations for what QuanTrade should implement next.

Those conclusions must be appended as a dated research artifact rather than silently editing historical conclusions.

## 12. Handoff to future QuanTrade workers

Before adding a trading dependency or copying an external architecture:
1. read `QUANTRADE_CANONICAL_VISION.md`;
2. read this program;
3. find the candidate's latest research record;
4. verify license and pinned version again;
5. identify its capability boundary;
6. run the promotion gate;
7. record the resulting Decision and implementation binding.

A future research agent should be able to recognize this document as evidence that external-technology scouting is an ongoing organizational function, not an ad-hoc chat exercise.
