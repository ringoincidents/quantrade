# QuanTrade duty pilot — verification only

Founder direction 2026-11-28: programs run from plans; HQ reads reports hourly and coordinates exceptions. This is a bounded Domain/Research adapter, NOT a replacement for Holdings Core, not a production activation, and not an expansion or completion of #142. Existing alerts and investment authority remain untouched.

## Authority and reuse
Holdings LLMH-047 doctrine and LLMH-046 Core boundary already own Mission/Work/Handoff, Gateway, Authority, Budget, Approval, Evidence and audit. Do not create a parallel permanent ontology. Local SQLite here is a pilot execution spool; integration must map each SOP to a canonical Mission/Work and use governed Core gateway/approval. No claims of independent review from same-process assertions. See Holdings docs/operations/ORGANIZATIONAL_OPERATING_DOCTRINE_v0.1.md and docs/architecture/CORE_BOUNDARY_v0.2.md.

## Server split
Existing Vultr VPS: one systemd timer and single process, no paid resource addition, five-minute synthetic slots, hourly immutable report. Railway: existing specialized private office, data/research and broker gateway only; no new paid service or automatic broker activity. ChatGPT scheduled HQ: hourly report review, no Plus automation API from VPS. Future transport must authenticate, redact and validate commands; do not publish private data to GitHub. No live LLM/API calls until identity, hard spend enforcement, provider and permissions verified. No actual price or account data here.

## SOP pilot
- Data / collect: fixed synthetic price/target fixture only.
- Research / compare: integer comparison, REVIEW or WAIT only, never a trade.
- Risk / assure: deterministic consistency and digest checks, not independent evidence.
- Staff / report: prior UTC hour, expected 36 jobs, coverage, exceptions, zero external LLM calls. Korea time displays are a future projection.
- 60s wake, 300s logical slots, bounded catchup (12 slots), durable state, duplicate suppression. Interrupted jobs BLOCKED rather than blind replay; no arbitrary shell command execution. No external connections.
- Hourly first report may be incomplete. Late corrections require separate append-only report revision mechanism (not implemented). Digest is corruption check, not authenticated tamper proof. No automated retry of failed jobs.

## Local test
```sh
python -m unittest discover -s verification/operations-duty -v
python verification/operations-duty/duty.py --db /tmp/qt-duty-pilot.sqlite tick
python verification/operations-duty/duty.py --db /tmp/qt-duty-pilot.sqlite report
```

## Vultr install (not executed)
After independent review, verify existing Linux VPS identity, available RAM/disk, backup and cost. No new VM purchase. As administrator create non-login service user qt-duty; install reviewed pinned checkout into /opt/quantrade (root-owned and read-only to worker); copy qt-duty.service and qt-duty.timer to /etc/systemd/system; daemon-reload; enable --now qt-duty.timer. Inspect systemctl list-timers and journalctl -u qt-duty.service. To stop disable --now qt-duty.timer, stop qt-duty.service. Preserve /var/lib/qt-duty and test restore before removal. Never use root as execution user. Report command must run as the service account when no tick holds lock; retry later if busy. No network is permitted by unit. No actual Vultr access or verification is implied.

## Acceptance gates / remaining plan
1. Read current Holdings TASKS and decisions; reconcile current work and exact interfaces. No Holdings changes in this PR.
2. Independent code review, CI, local restart and adversarial tests, then existing VPS install after access and budget checks. 24h/72h/7d autonomous fixture run. Check coverage and CPU/RAM/disk.
3. Bind one actual read-only workflow to approved #142 session/finality/provider rights; secure durable store and backup. Preserve existing gates and ten trading-session parity.
4. Bind report transport and command proposals to authenticated Holdings Mission/Work; structured allowlist, scope, idempotency, TTL, signer, evidence, revocation. Local signed receipt only; no remote transport or arbitrary command executor in pilot.
5. Add exact exchange calendars, release calendars, quarterly/weekly plans, approved research dependencies and separate deterministic assurance. Never synthesize missing data.
6. Integrate existing Gateway and provider usage/cost reservations (including retries/uncertain outcomes), budgets, stop switch, independent review. No LLM provider traffic in pilot.
7. Integrate approved development/research workflows via isolated workers, no production merge or live orders. Confirm actual 7-day autonomous operation, report continuity, recovery and spend before promotion.

## Extended verification contracts
- `plan.json`: active synthetic SOP inventory and disabled daily/weekly/monthly/quarterly roadmap. This is a proposed domain schedule projection, not a canonical Holdings plan. Future schedule entries are explicitly disabled; runtime active handlers remain hardcoded and do not execute arbitrary manifest content.
- `command_contract.py`: local HMAC-authenticated ACK_REPORT / REQUEST_REVIEW envelopes with exact field allowlist, TTL, report digest binding, duplicate detection, and key-file mode/ownership validation. A request appears in the next hourly window; it is not authority to execute code, make investments, call a model or deploy. Shared-secret possession is not independently authenticated GPT identity. No transport, signing keys or real commands deployed. For offline testing, use an isolated database and owner-only randomly generated 32-byte key file; never commit keys. CLI: `duty.py --db ... ingest-command --envelope ... --key-file ...`. Report digest is SHA256 of canonical sorted compact JSON of the report body. Report acknowledgements do not change report contents.
- `test_seven_day.py`: 7 days of virtual time with an in-memory DB, not an elapsed-time or VPS durability test. A full hour distinguishes coverage from successful completion. The initial report is partial by construction. The clock regression check prevents new execution on backwards clock.
- LLM disabled hard in this pilot; no provider call path or real budget reservation here. Integrate the existing Holdings Gateway rather than duplicating it. Cost hard cap and provider receipt reconciliation remain gates.
