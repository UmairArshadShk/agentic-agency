# M7: Staging and QA (Main)

**Goal:** after a merge, `main` is verified on a persistent staging environment. A ticket is Done only after QA (Main) passes, and a failure reverts the merge automatically.

**Before starting:** confirm the QA (Main) defaults (revert on failure, serialized merges, unblock at Done) and the regression run cadence.

## Scope

- Persistent staging environment deployed from `main` on every merge, with its own database and real migration history.
- `agents/qa.py` in QA (Main) mode: runs the ticket's checks, the accumulated regression suite (all checks from previously merged tickets), and a screenshot comparison against the approved prototype. Writes a `qa_runs` row (`qa_main`).
- Regression suite management: checks from each merged ticket are added to the suite. Keep a fast smoke subset per merge; run the full suite per the chosen cadence (every merge, at milestones, or nightly).
- On failure (`on_qa_main_failure: revert`): automatically revert the merge, pause the merge queue until `main` is green, attach the failure report to the ticket, and return it to In Progress as the next round. Support `freeze_and_fix_forward` as the alternative.
- QA (Main) loop cap (`loop_caps.qa_main`, default 3), then Blocked and notify.
- Done only after QA (Main) passes; then unblock dependent tickets (`unblock_dependents_at: done`, with `merged` as the alternative).
- Jira second QA column (QA (Main)) mirrored from Postgres.

## Tasks

- [ ] Staging environment and deploy-on-merge
- [ ] QA (Main) mode with regression suite and screenshot comparison
- [ ] Suite growth and smoke subset selection
- [ ] Auto-revert and merge-queue pause and resume
- [ ] Round handling and cap
- [ ] Done transition and dependent unblocking
- [ ] Jira QA (Main) status

## Acceptance criteria

- [ ] Seeded failure test: two tickets whose migrations conflict pass QA (PR) separately; the second fails QA (Main), is reverted automatically, `main` is green again, and merges resume.
- [ ] While `main` is red, no new merge starts.
- [ ] Dependent tickets stay blocked until the dependency is Done, not merely merged.
- [ ] After 3 failed QA (Main) rounds the ticket is Blocked and the owner is notified.
- [ ] Postgres state and Jira column agree at every step of the failing and passing paths.
- [ ] Changing the config values (`on_qa_main_failure`, `unblock_dependents_at`) changes behavior for new projects only.

## Out of scope

Production deploy, change requests.
