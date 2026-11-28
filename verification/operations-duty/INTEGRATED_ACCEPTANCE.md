# Integrated installation candidate / pre-deployment acceptance

Use existing VPS only after access, security review, available resources, and backup destination verified. No new server or paid provisioning. Existing Railway services are actively used by other workstreams, do not repoint. No production merge, provider spending, trading or private disclosure.

## Intended timers (all uninstalled)
- qt-public-duty.timer every 5 min: collect only scheduled public jobs, process deterministic handoffs and close reports.
- qt-operations-audit.timer minute 04/19/34/49: read-only operations checks, separate audit ledger.
- qt-audit-hq-prepare.timer minute 06/21/36/51: prepare public-safe exception / recovery status when finding counts change. Initial healthy check and repeated same findings do not queue a message. No network in this service.
- HQ exchange is a separately gated CLI invocation; no recurring token-bearing unit or credential installed. It requires explicit identity and repository-scoped credential. Only fixed code/count projection; never expose financial values or arbitrary text. Uncertain delivery reconciles rather than blind retry; stale/unknown pending rows block subsequent send and require operator review. Bounded GitHub comment scan is a temporary pilot, not a permanent event bus.

## Backup / restore
Use spool_backup.py snapshot --db /var/lib/qt-public-duty/public.sqlite --bundle <new private directory>; verify --bundle <directory>; restore --bundle <directory> --db <new private path>. SQLite backup API captures WAL-backed spool consistently; full integrity and recorded payload digest checks plus file hash and counts. Does not overwrite destination or transfer backups. Partial failure may leave a non-valid bundle; verify before use. No automatic deletion, retention, offsite encryption, cross-ledger atomic backup, audit/HQ outbox backup, or real VPS restore yet. Do not restore into live service. Snapshot/restore test is isolated.

## Install gate
After independent review of pinned commit, administrator checks Linux systemd, Python 3.10+, tzdata, disk and quota, permissions, owner-only backup; create non-login qt-duty and root-owned reviewed checkout at /opt/quantrade. Run systemd-analyze verify with target paths installed. Install and start public duty service first, ensure DB exists; then audit and offline HQ preparation timers. Inspect timers/journals and verify actual 24h, 72h restart and 7-day elapsed behavior. Stop by disabling timers and stopping corresponding services, preserve DBs. Audit read-only WAL compatibility with target filesystem and sandbox must be verified on actual VPS. No actual deployment was performed.

## Acceptance evidence
Offline integration test simulates seven days of 5-minute ticks using file-backed SQLite reopened every tick, reads audit DB separately every 15min, validates 28 source jobs, 84 follow-on stages and 169 hourly report snapshots, backs up/restores to a new file and re-audits. Uses fixed fixture observations, not live data or elapsed 7-day test. Separate one-shot official provider probe remains a real source compatibility check but not proof of scheduled execution. No Holdings canonical Work/Gateway binding or independent financial reviewer; those remain gated. #142 and #150 remain authoritative.
