## QuanTrade three-space UI / founder feedback 2026-11-28

Isolated, offline, read-only prototype. Open `index.html` directly; no installation, network calls, private data, credentials or order functionality. Keep the existing gray left rail, white paper, square edges, monochrome typography and semantic colors only. Top-level spaces fixed to Field / Lab / Office. Existing ten-tab pilot stays untouched. Field: short market summary, risk scale, candidates, date-select calendar. Lab: named research plans and milestone details; unknown progress stays unknown. Office: NAV vs net contributed capital, TWR, sampled MDD, allocation, inbox and reports. Details use native modal dialog (bottom on mobile / right on desktop), restore focus and scroll. All displayed numbers, schedules and research stages are examples, not live data. No production routing or deployment.

### Acceptance checklist (not yet verified on actual device)
- [ ] iPhone Safari: three rail tabs; no horizontal overflow at 320/375/390px; selected white rail joins white page.
- [ ] Tap calendar date Dec 10, inspect only its three example events; month navigation and empty days work.
- [ ] Tap each metric, research title, asset chart and administrative row; close via X, Escape or outside; focus and scroll restored.
- [ ] Keyboard navigation and modal focus trapping; reduced motion and screen-reader review.
- [ ] Founder design acceptance; no actual data activation or merge before review.

### Integration boundary
#142 single-workflow acceptance remains authoritative. Do not modify its provider, report, private auth pilot, scheduler, or backend. Integrate approved read-only projections later only after review and explicit scope reconciliation. No fabricated stage progress, no inferred live status, no hidden missing/stale flags. The prototype intentionally does not implement auth, live fetch, or persistence. Existing production code remains unchanged.
