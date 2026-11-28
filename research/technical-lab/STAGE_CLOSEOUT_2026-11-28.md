# QT-MAR technical research stage closeout — 2026-11-28

**Engineering milestone: completed offline research run and independent artifact diagnostics. Investment validation: EXPLORATORY_NOT_VALIDATED / G0 BLOCKED. Do not merge or promote signals.**

## Verified evidence
- Original universe run https://github.com/ringoincidents/quantrade/actions/runs/46139748823 ; source checkout 36adf234a7b98e1bb30356350a9274d33e63f835 ; tested PR head 2bf2793083ebffeca639d70735c66dc75925d855. All 1,299 files audited: 835 shape-pass, 451 unresolved extreme move, 13 short history. 142 of shape-pass had no decision coverage; 693 used, zero execution errors. 30 previously viewed, 509 expansion, 154 security holdout. 79,644 horizon-level records including overlapping/censored observations, NOT independent trades. No missing or hash-mismatch status in this run.
- Source run evidence ZIP artifact 15261517003 (SHA256 60c000728926cfe02354c66ef6cd9efc55b385ff0364112407d28a350eb7ba2e); artifact originally retained 14 days. Durable aggregate log extract universe_run_46139748823.json.
- Independent artifact diagnostics https://github.com/ringoincidents/quantrade/actions/runs/46140090087 succeeded; verified audit hash linkage and recomputed grouped statistics. Durable log extract universe_diagnostics_run_46140090087.json; full diagnostic artifact retained 30 days.
- Node 22 offline CI https://github.com/ringoincidents/quantrade/actions/runs/46139748744 succeeded. Later research-only trigger changes pinned source commit and gated heavy runs behind explicit PR labels or manual dispatch; these revised trigger/fetch paths have not themselves been rerun. No changes to production, strategy thresholds, brokerage or capital.
 
## Primary 60-day results (% points, event minus eligible control)
| Rule | Expansion pooled SPY-relative | Holdout pooled SPY-relative | Holdout equal-year SPY-relative | Holdout exploratory 3-year block 95% range |
|---|---:|---:|---:|---|
| Annual reclaim | -0.92 | +0.17 | -2.34 | [-5.55,+0.82] |
| Monthly compression | +0.83 | +0.89 | +1.53 | [-0.08,+3.01] |
| 100-month support | -0.37 | +0.42 | -1.51 | [-3.72,+0.33] |

Adverse-10 pooled differences in expansion/holdout: annual -10.21/-10.19 pp; monthly compression -7.87/-1.86 pp; 100m support -1.19/-3.81 pp. Annual equal-year holdout risk difference +4.40 pp; thus pooled risk association does not establish robust risk mitigation. The monthly compression holdout relative effect above/below SPY SMA200 was +0.04/+6.27 pp (descriptive, post-outcome diagnostic only, not a new rule). All holdout year-block intervals for relative return contain zero; no positive investment edge confirmed. Three-year block bootstrap is exploratory, not two-way cluster or multiplicity-adjusted inference. Equal-year means need not equal block resampling center.

## Disposition
- Annual reclaim: risk association research candidate only; no entry or allocation rule.
- Monthly compression: descriptive trend feature / relative-strength research candidate; no entry rule.
- 100m support: deprioritize entry/risk candidate; not demonstrated in robust relative-return or downside metrics.
- No parameter tuning, new indicators, live signals or portfolio changes. Negative and ambiguous results retained.
- Existing split by filename hash is provisional security split, not issuer-identity or independent temporal split. Now considered viewed. Freeze new independent data/time sample before further analysis; do not recycle current holdout as proof.
- 451 extreme-move quarantines can materially bias results. Resolve via independent corporate-action and raw-price evidence; exact terminal proceeds, splits/dividends, merger ratios, historical security/issuer mapping, calendar and PIT sector/index membership absent. See CORPORATE_ACTION_GATE.md. Sector benchmark unimplemented; no false inference from SPY. Uniform 0.5% cost is not realistic execution model. No trading approval.

## Reproducibility / handoff
Commands and inputs in README, source_inventory.json, prior PR comment 7238534796, and CI logs. For exact source checkout use 36adf234a7b98e1bb30356350a9274d33e63f835 and verify all byte hashes. Run audit_universe.mjs, run_universe.mjs then universe_diagnostics.mjs on paired immutable outputs. Full original artifact expires; durable JSON aggregates in branch allow review, but not substitute for complete event ledger. Explicit label technical-lab-universe starts heavy replay and technical-lab-audit audits the original pinned run; future manual dispatch can specify completed run ID when available. Revised workflow trigger paths not yet tested. 
**STOP:** close this exploratory research iteration; do not repeatedly rerun same inputs or add indicators. Reopen only on independent data evidence, a preregistered independent temporal/issuer sample, or an identified reproducibility defect. Canonical G0 remains blocked; keep PR draft and main unchanged. 
