# QuanTrade P0.5 — Vision-to-Implementation Gap Audit

Date: 2026-09-19  
Status: Architecture baseline accepted for P1  
Target model: DEC-003 — QuanTrade Target Operating Model & Institution-as-Interface

## 1. Executive finding

The repository already contains substantial research, portfolio reporting, deterministic risk, real-account read-only sync, post-trade review, experiments, and governance checks. The primary problem is not absence of functionality. It is that several generations of QuanTrade coexist without one canonical institutional runtime.

The current repository has two portfolio domains:
- legacy/simulation: `portfolio.json`, `analyze.py`, `pending_actions.json`, `check_updates.py`
- real/current: `real_portfolio.json`, `portfolio_report.py`, `post_trade_review.py`, `autoexec.py`

There is no canonical Event → Case → institutional review → Founder escalation → Decision Management → Execution → Outcome/Review lifecycle.

P0.3.1 establishes the target institution visually. P1 must make that institution real in code.

## 2. Accepted operating principle

Not every event becomes a Case.

A **Case is opened when an event or situation requires material investment judgment, cross-office review, an exception, or durable decision memory.** Routine observations and mechanically resolvable events should be processed internally and logged without consuming Founder attention.

Canonical escalation:

```
EVENT
  ↓
Can policy/deterministic logic resolve it safely?
  ├─ YES → internal processing + LedgerEvent
  └─ NO  → CASE
             ↓
       Research / Portfolio / Risk / Adversarial Review
             ↓
       materiality / escalation
          ├─ LOW    → internal resolution + log
          ├─ MEDIUM → periodic Founder Briefing
          └─ HIGH   → Founder Desk
```

Case is therefore the core unit of **material investment work**, not the unit of all system activity.

Founder attention is a scarce institutional resource and must be protected by escalation policy.

## 3. Classification legend

- KEEP — sound capability that should survive conceptually.
- MOVE — capability is useful but belongs under another institutional boundary.
- REFACTOR — capability survives but its schema/API/ownership must change.
- RETIRE — legacy operational path should stop being part of the future runtime; preserve history where useful.
- BUILD — missing target capability.

## 4. Target organization vs current implementation

| Target office / function | Current implementation | Current behavior | Classification | P1 disposition |
|---|---|---|---|---|
| Founder / Client | P0.3.1 `company.html`; Telegram commands; scattered JSON approvals | UI is prototype-local; approval paths are split | REFACTOR + BUILD | Founder inbox receives only escalated matters, briefing, orders and decisions |
| 최고투자설계실 (CIAO) | `CLAUDE.md`, design docs, policy notes | Architecture/policy exists mostly as prose | BUILD | machine-readable institutional policy + escalation/authority registry |
| 고객자본관리실 (CCO) | `real_portfolio.json`, `income_schedule.json`, `target_allocation.json` | real holdings sync exists; capital policy is partly provisional | REFACTOR | canonical Account/Position/CapitalConstraint models |
| 투자정보본부 (IID) | `news_event_cards.py`, `market_indicators.py`, `ai_briefing.py`, parts of `analyze_lib.py` | observation/explanation pipeline exists; AI briefing can fail independently | KEEP + MOVE | preserve collectors/generators behind Event/Research/Evidence interfaces |
| Evidence Intelligence Fabric (EIF) | common-event helpers in `analyze_lib.py`; source fields in reports/cards | partial provenance; no unified evidence object/store | REFACTOR + BUILD | canonical Event, Evidence, Source and Claim links |
| 전략·포트폴리오본부 (SPMG) | `portfolio_report.py`, allocation/role mappings | strong calculations but reporting, policy and portfolio logic are coupled | REFACTOR | split portfolio engine from report rendering and policy inputs |
| 독립위험관리실 (IPRO) | `portfolio_report.py` risk engine, `analyze.py` guardrails, `autoexec.py` rules | deterministic risk exists but policy is distributed | REFACTOR | one RiskPolicy + RiskAssessment service |
| 반대검증실 (ARU) | experiment culture and audits only | no case-level counter-thesis/challenge workflow | BUILD | Challenge / CounterThesis institutional object |
| 투자위원회 (IC) | no canonical committee domain | no formal agenda, positions, dissent or recommendation record | BUILD | CommitteeCase + InstitutionalPosition + unresolved questions |
| 투자결정통제실 (IDCO) | `pending_actions.json`, autoexec approvals, `policy_exception.py` | multiple incompatible approval models | REFACTOR | authority/precondition validation + post-approval Decision Management |
| 주문집행·시장운영실 (EMO) | `autoexec.py`, `toss_order_endpoint_probe.py` | sell-only execution concept; actual order layer unavailable/disabled | HOLD + LATER BUILD | execution planning interface only in P1; broker remains disabled |
| 성과분석실 (PAO) | `post_trade_review.py`, PnL histories | useful post-decision analysis exists | KEEP + REFACTOR | link outcome tracking and 30D/90D review to Case/Decision |
| 투자과학·학습연구소 (ISLL) | backtests, significance tests, news experiments | strong experiment/gate culture | KEEP / ISOLATE | keep research artifacts outside production decision state |
| 데이터·투자기술본부 (IDEP) | GitHub Actions, JSON state, sync scripts | Git doubles as scheduler, DB and audit transport | REBUILD | SQLite first; service/repository layer; scheduler separated later |
| 모델위험·감사실 (MRGA) | self-tests, forbidden-field audits, `policy_exception.py` | good controls, scattered across scripts | KEEP + CENTRALIZE | invariant tests + audit events + policy exceptions |

## 5. File-level disposition

### KEEP / adapt
- `real_portfolio_sync.py` — preserve read-only account ingestion.
- `portfolio_report.py` — preserve deterministic calculations, but split engine from presentation.
- `post_trade_review.py` — preserve review logic; link to decisions/cases.
- `news_event_cards.py`, `market_indicators.py` — preserve as event/observation producers.
- backtest/significance/experiment scripts — preserve as Investment Science research tooling.
- `policy_exception.py` and existing audit/self-test patterns — preserve governance ideas.

### REFACTOR / MOVE
- `analyze_lib.py` — break into market data, events/evidence, research experiments and shared utilities.
- `ai_briefing.py` — move toward Secretary/Founder briefing generated from institutional state.
- `target_allocation.json`, `portfolio_role_mapping.json`, `asset_class_mapping.json` — policy/config inputs, not authoritative runtime state.
- `autoexec.py` — separate deterministic trigger/risk logic from execution. Do not activate broker execution.
- GitHub Actions workflows — retain experiments/read-only jobs temporarily, but stop treating Git commits as the future mutable runtime state mechanism.

### RETIRE from future runtime
Preserve history, but do not build new P1 behavior on:
- `portfolio.json`
- legacy approval semantics in `pending_actions.json`
- legacy portfolio mutation in `check_updates.py`
- the old `analyze.py` portfolio lifecycle
- root `index.html` as the future institutional interface

These may remain during migration until replacements are validated.

## 6. Concrete drift found on 2026-09-19

1. `portfolio.json` contains cash and no positions, while `real_portfolio.json` contains the actual current holdings.
2. `pending_actions.json` still contains old crypto and stale real-position actions.
3. `target_allocation.json` declares itself `provisional: true` and contains unresolved interpretation notes.
4. `asset_class_mapping.json` and `portfolio_role_mapping.json` contain active mappings for positions no longer present in current `real_portfolio.json`, while current holding BTAIQ is not represented.
5. `ai_briefing.json` currently reports `status: api_failed`; Founder briefing needs a state-derived fallback.
6. `autoexec.py` has no active periodic workflow invoking its main rule execution path.
7. Mutable state is primarily JSON committed by multiple GitHub Actions, with push/rebase retries. This is prototype infrastructure, not a future transactional state store.
8. Real broker execution remains disabled/unavailable. This is the correct P1 safety boundary.

## 7. P1 canonical domain

Required core entities:

- `Event` — raw or normalized occurrence observed by QuanTrade; most Events never become Cases.
- `Case` — material investment matter requiring judgment and durable institutional workflow.
- `Evidence` — sourced observation/claim attached to a Case.
- `InstitutionalPosition` — an office's formal position on a Case.
- `Challenge` — adversarial review / unresolved counter-thesis.
- `FounderOrder` — instruction with route, destination and status.
- `InvestmentDecision` — Founder-authorized decision output; not the conceptual center.
- `DecisionPlan` — post-approval timing/conditions/implementation plan controlled by IDCO.
- `ExecutionRecord` — later record of intended/actual execution; no live broker implementation in P1.
- `ReviewSchedule` / `OutcomeReview` — post-decision follow-up such as 30D/90D review.
- `LedgerEvent` — append-only record of institutional state transitions.
- `PortfolioSnapshot` — immutable account/position snapshot used by a Case.
- `RiskAssessment` — deterministic risk result tied to policy version and snapshot.

Conceptual center: Client / Founder.  
Observation unit: Event.  
Material-work unit: Case.  
Durable history: LedgerEvent.  
Decision is an output; approval does not necessarily close the Case.

## 8. Case lifecycle

A Case can continue after Founder approval:

```
TRIGGER / EVENT
      ↓
CASE OPEN
      ↓
Research / Portfolio / Risk / Adversarial Review
      ↓
Investment Committee
      ↓
Founder Desk
      ↓
Founder Decision
      ↓
Decision Management
      ↓
Execution Plan
  - now
  - after a named event
  - conditional
  - hold
      ↓
Execution Record
      ↓
Outcome Tracking
      ↓
Scheduled Review(s)
      ↓
CASE CLOSED
```

P1 must model this lifecycle even while actual broker execution remains disabled.

## 9. P1.0 first implementation slice

Implement one end-to-end vertical slice:

1. Ingest a synthetic Event.
2. Demonstrate one routine Event resolved/logged without creating a Case.
3. Demonstrate one material Event escalated into CASE QT-2026-0041.
4. Attach Evidence and PortfolioSnapshot.
5. Record Portfolio and Risk institutional positions.
6. Record an Adversarial Challenge.
7. Move the Case to Investment Committee.
8. Produce a committee package without erasing dissent.
9. Route HIGH materiality to Founder Desk; support MEDIUM briefing and LOW internal resolution in policy/tests.
10. Founder records approve / reject / hold / research.
11. On approval, create a DecisionPlan rather than closing the Case.
12. Record a simulated/no-broker ExecutionRecord.
13. Schedule 30D/90D OutcomeReview placeholders.
14. Close only when lifecycle conditions are satisfied.
15. Append every transition to LedgerEvent.
16. Reload from persistent storage and reproduce the same state.

Technical baseline:
- Python package for institutional domain/runtime.
- SQLite for P1 local transactional persistence.
- explicit repository/service boundaries so SQLite can later be replaced.
- deterministic escalation/risk logic separated from LLM/research code.
- no broker execution.
- tests for allowed state transitions, append-only ledger behavior, decision immutability, dissent preservation, Founder escalation filtering, and no broker side effects.
- existing P0.3.1 UI remains a prototype client until runtime API is stable.

## 10. Migration order

1. Build P1 institutional kernel in parallel with legacy code.
2. Prove Event filtering + CASE QT-2026-0041 end-to-end with tests.
3. Connect read-only `real_portfolio_sync` output through a PortfolioSnapshot adapter.
4. Move deterministic portfolio/risk calculations behind new services.
5. Connect Research/Event/Evidence producers.
6. Connect P0.3.1 Founder Console to runtime.
7. Migrate post-trade review/performance attribution.
8. Only after parity is demonstrated, disable legacy portfolio/pending-action runtime paths.
9. Broker execution remains a later, separately approved phase.

## 11. Non-goals for P1.0

- no live buy/sell orders
- no autonomous investment decisions
- no multi-agent framework merely for organizational appearance
- no deletion of failed experiments/history
- no broad UI redesign
- no migration of every old JSON file at once
- no rule that every Event must become a Case
- no rule that every Case must reach Founder Desk

## 12. Gate to P1.1

P1.0 passes only if tests prove both paths:

`Routine Event → deterministic/internal handling → Ledger → no Case → no Founder interruption`

and

`Material Event → Case → Evidence → Office Positions → Challenge → Committee → escalation → Founder Decision → DecisionPlan → simulated ExecutionRecord → Review schedule → Ledger → Reload`

with stable IDs, preserved dissent, immutable decision record, selective Founder escalation and zero broker side effect.
