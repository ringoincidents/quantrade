# QuanTrade P0.5 — Vision-to-Implementation Gap Audit

Date: 2026-09-19  
Status: Working architecture baseline  
Target model: DEC-003 — QuanTrade Target Operating Model & Institution-as-Interface

## 1. Executive finding

The repository already contains substantial research, portfolio reporting, deterministic risk, real-account read-only sync, post-trade review, experiments, and governance checks. The primary problem is not absence of functionality. It is that several generations of QuanTrade coexist without one canonical institutional runtime.

The current repository has two portfolio domains:
- legacy/simulation: `portfolio.json`, `analyze.py`, `pending_actions.json`, `check_updates.py`
- real/current: `real_portfolio.json`, `portfolio_report.py`, `post_trade_review.py`, `autoexec.py`

There is no canonical Case / Evidence / InstitutionalPosition / FounderOrder / InvestmentDecision lifecycle connecting Research → Portfolio → Risk → Committee → Founder → Ledger.

P0.3.1 establishes the target institution visually. P1 must make that institution real in code.

## 2. Classification legend

- KEEP — sound capability that should survive conceptually.
- MOVE — capability is useful but belongs under another institutional boundary.
- REFACTOR — capability survives but its schema/API/ownership must change.
- RETIRE — legacy operational path should stop being part of the future runtime; preserve history where useful.
- BUILD — missing target capability.

## 3. Target organization vs current implementation

| Target office / function | Current implementation | Current behavior | Classification | P1 disposition |
|---|---|---|---|---|
| Founder / Client | P0.3.1 `company.html`; Telegram commands; scattered JSON approvals | UI is prototype-local; approval paths are split | REFACTOR + BUILD | Founder API, inbox, orders, decisions backed by canonical DB |
| 최고투자설계실 (CIAO) | `CLAUDE.md`, design docs, policy notes | Architecture/policy exists mostly as prose | BUILD | machine-readable institutional policy + authority registry |
| 고객자본관리실 (CCO) | `real_portfolio.json`, `income_schedule.json`, `target_allocation.json` | real holdings sync exists; capital policy is partly provisional | REFACTOR | canonical Account/Position/CapitalConstraint models |
| 투자정보본부 (IID) | `news_event_cards.py`, `market_indicators.py`, `ai_briefing.py`, parts of `analyze_lib.py` | observation/explanation pipeline exists; AI briefing can fail independently | KEEP + MOVE | preserve collectors/generators behind Research/Evidence interfaces |
| Evidence Intelligence Fabric (EIF) | common-event helpers in `analyze_lib.py`; source fields in reports/cards | partial provenance; no unified evidence object/store | REFACTOR + BUILD | canonical Evidence + Source + Claim links |
| 전략·포트폴리오본부 (SPMG) | `portfolio_report.py`, allocation/role mappings | strong calculations but reporting, policy and portfolio logic are coupled | REFACTOR | split portfolio engine from report rendering and policy inputs |
| 독립위험관리실 (IPRO) | `portfolio_report.py` risk engine, `analyze.py` guardrails, `autoexec.py` rules | deterministic risk exists but policy is distributed | REFACTOR | one RiskPolicy + RiskAssessment service |
| 반대검증실 (ARU) | experiment culture and audits only | no case-level counter-thesis/challenge workflow | BUILD | Challenge / CounterThesis institutional object |
| 투자위원회 (IC) | no canonical committee domain | no formal agenda, positions, dissent or recommendation record | BUILD | CommitteeCase + InstitutionalPosition + unresolved questions |
| 투자결정통제실 (IDCO) | `pending_actions.json`, autoexec approvals, `policy_exception.py` | multiple incompatible approval models | REFACTOR | authority/precondition validation around canonical decisions |
| 주문집행·시장운영실 (EMO) | `autoexec.py`, `toss_order_endpoint_probe.py` | sell-only execution concept; actual order layer unavailable/disabled | HOLD + LATER BUILD | keep broker disabled through P1; define interface only |
| 성과분석실 (PAO) | `post_trade_review.py`, PnL histories | useful post-decision analysis exists | KEEP + REFACTOR | link attribution to canonical decision/case IDs |
| 투자과학·학습연구소 (ISLL) | backtests, significance tests, news experiments | strong experiment/gate culture | KEEP / ISOLATE | keep research artifacts outside production decision state |
| 데이터·투자기술본부 (IDEP) | GitHub Actions, JSON state, sync scripts | Git doubles as scheduler, DB and audit transport | REBUILD | SQLite first; service/repository layer; scheduler separated later |
| 모델위험·감사실 (MRGA) | self-tests, forbidden-field audits, `policy_exception.py` | good controls, scattered across scripts | KEEP + CENTRALIZE | invariant tests + audit events + policy exceptions |

## 4. File-level disposition

### KEEP / adapt
- `real_portfolio_sync.py` — preserve read-only account ingestion.
- `portfolio_report.py` — preserve deterministic calculations, but split engine from presentation.
- `post_trade_review.py` — preserve review logic; link to decisions/cases.
- `news_event_cards.py`, `market_indicators.py` — preserve as observation producers.
- backtest/significance/experiment scripts — preserve as Investment Science research tooling.
- `policy_exception.py` and existing audit/self-test patterns — preserve governance ideas.

### REFACTOR / MOVE
- `analyze_lib.py` — currently a large mixed utility/research/data/AI module. Break into market data, evidence, research experiments, and shared utilities.
- `ai_briefing.py` — move toward Secretary/Founder briefing generated from institutional state, not a standalone intelligence product.
- `target_allocation.json`, `portfolio_role_mapping.json`, `asset_class_mapping.json` — treat as policy/config inputs, not authoritative runtime state.
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

## 5. Concrete drift found on 2026-09-19

1. `portfolio.json` contains cash and no positions, while `real_portfolio.json` contains the actual current holdings. They are different portfolio domains.
2. `pending_actions.json` still contains old crypto and stale real-position actions. It cannot be the future decision queue.
3. `target_allocation.json` explicitly declares itself `provisional: true` and contains unresolved interpretation notes. It cannot silently become canonical policy.
4. `asset_class_mapping.json` and `portfolio_role_mapping.json` contain active mappings for positions no longer present in the current `real_portfolio.json`, while current holding BTAIQ is not represented. Configuration has drifted from holdings.
5. `ai_briefing.json` currently reports `status: api_failed`; Founder briefing therefore needs graceful state-derived fallback rather than dependence on one LLM call.
6. `autoexec.py` has no active periodic workflow that invokes its main rule execution path. The repository has a kill-switch fast-path but no live autoexec scheduler.
7. Current mutable state is primarily JSON committed by multiple GitHub Actions. Several workflows use push/rebase retries. This is acceptable as historical prototype infrastructure, not as the future transactional state store.
8. Real broker execution remains disabled/unavailable. This is the correct P1 safety boundary.

## 6. P1 canonical domain

P1 should introduce a small institutional kernel before adding more features.

Required core entities:

- `Case` — one institutional matter moving through the company.
- `Evidence` — sourced observation/claim attached to a case.
- `InstitutionalPosition` — an office's formal position on a case.
- `Challenge` — adversarial review / unresolved counter-thesis.
- `FounderOrder` — instruction with route, destination and status.
- `InvestmentDecision` — final decision output; not the conceptual center of QuanTrade.
- `LedgerEvent` — append-only record of institutional state transitions.
- `PortfolioSnapshot` — immutable snapshot of account/positions used by a case.
- `RiskAssessment` — deterministic risk result tied to policy version and snapshot.

Conceptual center: Client / Founder.  
Operational unit: Case.  
Durable history: LedgerEvent.  
Decision is an output of the institutional process.

## 7. P1.0 first implementation slice

Do not begin with live market APIs, multi-agent orchestration, or broker execution.

Implement one end-to-end vertical slice:

1. Create a Case equivalent to mock CASE-041.
2. Attach Evidence.
3. Record Portfolio and Risk institutional positions.
4. Record an Adversarial Challenge.
5. Move the case to Investment Committee.
6. Produce a committee package without erasing dissent.
7. Place it on Founder desk.
8. Founder records approve / hold / reject / research.
9. Append every transition to a ledger.
10. Reload the process from persistent storage and reproduce the same state.

Technical baseline:
- Python package for institutional domain/runtime.
- SQLite for P1 local transactional persistence.
- explicit repository/service boundaries so SQLite can later be replaced.
- deterministic risk functions separated from LLM/research code.
- no broker execution.
- tests for allowed state transitions, append-only ledger behavior, decision immutability, and dissent preservation.
- existing P0.3.1 UI remains a prototype client until the runtime API is stable.

## 8. Migration order

1. Build P1 institutional kernel in parallel with legacy code.
2. Prove CASE-041 end-to-end with tests.
3. Connect read-only `real_portfolio_sync` output through a PortfolioSnapshot adapter.
4. Move deterministic portfolio/risk calculations behind the new services.
5. Connect Research/Evidence producers.
6. Connect P0.3.1 Founder Console to the runtime.
7. Migrate post-trade review/performance attribution.
8. Only after parity is demonstrated, disable legacy portfolio/pending-action runtime paths.
9. Broker execution remains a later, separately approved phase.

## 9. Non-goals for P1.0

- no live buy/sell orders
- no autonomous investment decisions
- no multi-agent framework merely for organizational appearance
- no deletion of failed experiments/history
- no broad UI redesign
- no migration of every old JSON file at once

## 10. Gate to P1.1

P1.0 passes only if a test can prove:

`Case → Evidence → Office Positions → Challenge → Committee → Founder Decision → Ledger → Reload`

with the same IDs, preserved dissent, immutable decision record, and no broker side effect.
