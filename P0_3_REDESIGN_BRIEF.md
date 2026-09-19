# QuanTrade P0.3 — Institution, not App

## Classification
Project Update / Experiment

## Objective
Rebuild the mobile prototype so it feels like a private investment institution that happens to be operated through a phone, not a fintech app/dashboard.

## Self-critique of P0.2
1. Bottom four-tab navigation makes the product read as a conventional mobile app.
2. Rounded cards, pills, progress bars and dashboard counters dominate the visual grammar.
3. Department pages reuse the same generic template, so departments feel like menu items rather than distinct offices with different responsibilities.
4. "Company monitor" is a dashboard widget rather than an institutional information channel.
5. Secretary is a chatbot bottom sheet. It should behave as an office that routes orders and returns documents.
6. Fake progress percentages create false precision and game-like task tracking.
7. Records is presented as a feature tab rather than institutional memory/audit trail.
8. Founder sees too much raw operational information. Information should compress upward.
9. The organization shown in P0.2 is incomplete relative to the target operating model.
10. Excessive rounded rectangles and app-like affordances weaken the "company on screen" metaphor.

## Design doctrine
- Institution-as-Interface.
- Documents, offices, ledgers, orders and institutional positions are the primary objects.
- No persistent bottom tab bar.
- Use a restrained institutional visual language: paper, rules, ledgers, directories, internal wire, document codes.
- Reduce rounded cards/pills/shadows drastically.
- Korean-first, mobile-first.
- Founder Office has the lowest raw-data density and highest decision density.
- Department status is qualitative (researching / reviewing / challenged / waiting), not fake percentage progress.
- Every screen should answer: in a real firm, whose desk is this information on, who produced it, where does it go next, and who has authority?

## P0.3 information architecture
### Persistent masthead
QUANTRADE / Private Investment Office / Founder Console
- breadcrumb-like location
- Secretary Office call
- no bottom navigation

### Founder Office
1. Secretary Note — one memo, not a dashboard card
2. On My Desk — document docket/registry
3. Company Wire — compressed institutional event wire
4. Doors to Company and Situation Room

### Company
Render the institution as floors / institutional zones, not a menu:
- Executive Office
  - 최고투자설계실
- Client & Capital
  - 고객자본관리실
- Research Floor
  - 투자정보본부
- Investment Floor
  - 전략·포트폴리오본부
- Independent Control
  - 독립위험관리실
  - 반대검증실
- Decision Floor
  - 투자위원회
  - 투자결정통제실
- Operations Floor
  - 주문집행·시장운영실
- Post-Decision
  - 성과분석실
  - 투자과학·학습연구소
- Platform
  - 데이터·투자기술본부
- Governance
  - 모델위험·감사실

Evidence Intelligence Fabric is an information fabric, not a department button.

### Department office
Each office page contains:
- office identity / mandate
- office briefing
- open matters ledger
- department-specific institutional output
- Founder Direct Order
- route through Secretary Office
No generic percentage progress bars.

### Situation Room
Append-only operational ledger:
time / origin office / event / classification / next destination.

### Institutional Memory
Audit-style record, not a generic "Records" app feature.

### Decision docket
CASE-041 should read like a formal committee paper:
- executive abstract
- institutional positions
- unresolved questions
- Founder note
- reject / hold / research / approve
- decision becomes an append-only ledger event

### Secretary Office
Full institutional workspace rather than chatbot sheet.
Functions:
- ASK: retrieve/summarize existing institutional information
- ORDER: classify and route Founder instruction, create work number
- RETURN: bring only decision-worthy results back to Founder desk

## Interaction requirements
- Preserve mobile touch support.
- Preserve localStorage prototype state.
- Founder orders must appear in department ledger and Situation Room.
- Decisions must update Founder desk and institutional ledger.
- Existing root index.html must never be modified.
- Real broker/order connectivity must remain disabled.
- All investment data remains explicitly illustrative/mock.

## Visual constraints
Avoid:
- fintech dashboard
- SaaS admin
- four-tab app nav
- floating rounded card stacks
- decorative KPI tiles
- fake percentage progress
- excessive blue gradients
- game UI

Prefer:
- warm neutral paper background
- black/gray institutional typography
- serif display type sparingly for office/document identity
- thin rules and ledger rows
- document codes and timestamps
- restrained blue only for action/navigation
- red/amber only for disagreement/risk
- minimal radius and minimal shadows

## Acceptance test
On first impression, a user should say:
"This feels like I entered a small investment firm / family office."
not:
"This looks like a portfolio management app."

The Founder should be able to:
1. read Secretary Note,
2. open CASE-041,
3. inspect institutional disagreement,
4. make a decision,
5. see it recorded,
6. enter Company,
7. open different offices,
8. issue a direct order,
9. see that order in the office and Situation Room,
10. route an instruction through Secretary Office.
