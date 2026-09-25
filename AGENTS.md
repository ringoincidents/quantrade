# QuanTrade engineering and experiment rules

Read `docs/VERIFICATION_MAP.md` and the source/test entries for the affected behavior before changing it. A map is navigation, not evidence that a feature works.

- State the hypothesis or defect, scope, and checkable outcome first. Preserve existing work and experiment artifacts.
- Keep changes small. Do not add employees, orchestration layers, dependencies or live integrations without a task-specific reason.
- Distinguish execution completion, scientific grade, investment quality and authorization. None implies the others.
- Use deterministic checks for arithmetic and invariants; connect research claims to evidence. AI prose is not evidence.
- When changing a prompt, tool contract, grader or public packet, add a regression/evaluation check. Freeze benchmark versions; never silently rewrite historical results or train on the holdout.
- Run relevant tests and the no-broker demo. Report the exact command, checked revision, outcome, failures and limitations. Unavailable checks are NOT_RUN, not passed.
- For E2-A use the execution receipt check; retain incomplete, errored and scientifically failing trials. Never turn a model-format failure into a successful retry without a separately approved protocol.
- Do not auto-merge, enable live orders, access broker credentials or trigger paid model experiments as a consequence of routine verification. Those require explicit task scope.
- Do not remove financial assumptions or useful rationale comments merely to imitate another project's style rules. Update stale documentation with the code.
- CI evidence supports review; required-check/branch-protection enforcement is a separate repository setting, not guaranteed by this file.
