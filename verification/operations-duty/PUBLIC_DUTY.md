# Scheduled public reference work (verification)
First actual domain workloads: US Treasury 2Y/10Y par yields at 07:05/19:05 KST and BLS CPI/core CPI/payroll/unemployment at 07:10/19:10 KST. Schedule is an operational sampling choice, not release timing or exchange finality. Weekends included, no more than two scheduled requests per provider per day on one installed instance. Values are public reference only, not actual portfolio/decision inputs; BLS is latest revised, Treasury par is not FRED CMT, no original publication times or finality claimed. No API credentials, LLM or account calls. Raw source is hashed but not archived. Private local SQLite stores compact observations and hourly immutable reports, not a PIT data vault. Failed attempt blocks until next scheduled window; old observations explicitly historical. No retroactive source replay; missed windows recorded, with bounded 30-day catch-up metadata. First startup only looks back two hours.

## Reuse
Unmodified pinned source modules copied from existing QuanTrade verification/work-lifecycle-20261128 because that branch is unmerged and concurrently maintained. Git blob pins:
- verification/private-office/bls_direct.py fe14889f0fc1c784d09bcee658f6b0b1aa0ce933
- verification/private-office/macro_view.py 0874162a71f79aa1ba33ebeeb5ffa6a6ac9d5f9b
- verification/private-office/treasury_view.py a29c7ec6aeca61bab0ab92e5056231d300683105
- research/market_data_vault/treasury_pilot.py 19c6bd9fcafd25ef360e18f1a58263c9e2ede1b0
Use direct fetch/parse only; do not use embedded dated fallback/cache as actual evidence. Consolidate imports after reviewed upstream adoption; no independent permanent copy intended.

## Install gate
Existing Vultr only, after review and confirmed access, disk, firewall and backup. Create nonlogin qt-duty user; root-owned pinned checkout at /opt/quantrade. Install qt-public-duty.service and .timer; verify with systemd-analyze verify, systemctl daemon-reload, systemctl enable --now qt-public-duty.timer. Inspect timer and journal. Use either this pilot or synthetic timer according to scope; no duplicate service per department. Stop with systemctl disable --now qt-public-duty.timer; preserve state. No external inbound listener. Outbound network allowed by unit, Python fixed HTTPS URLs and no redirect; OS egress allowlisting remains a deployment hardening gate. The CLI logs public reference results only, no private values. The hourly report is fixed at first tick in that hour; later results appear next hour. No live HQ transport yet. Never expose private portfolio state via GitHub or logs.

## Test
Offline CI tests exercise schedule windows, no duplicate requests, missed jobs, restart containment, clock reversal, digest, historical labels. Separate bounded PR probe explicitly runs real public sources once each in disposable runner DB; failure is nonzero and not a claim of continuous schedule operation. Main not merged, no GitHub cron activated, no Railway/Vultr deploy. No new paid resources. For the actual test use the pinned reviewed service and record 24h, 72h and 7-day elapsed results. Preserve #142 gate and #150 integration plan.
