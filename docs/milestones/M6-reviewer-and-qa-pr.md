# M6: Reviewer and QA (PR)

**Goal:** every PR is reviewed and QA-tested on its preview before it can merge, with capped loops, escalation, and a serialized merge queue.

## Scope

- `agents/reviewer.py`: reads the PR diff, comments on GitHub, checks every new dependency for hallucinated or malicious packages, approves or requests changes. Runs on a different model than the developers (validated by config).
- Review loop: developer fixes, reviewer re-reviews, up to `loop_caps.review` rounds (default 3), then escalate to Blocked.
- `agents/qa.py` in QA (PR) mode: runs the ticket's checks (written in M4) and a smoke test against the PR preview. Reports pass or fail with logs and screenshots, and writes a `qa_runs` row (`qa_pr`).
- QA (PR) loop: failures go back to the developer, up to `loop_caps.qa_pr`, then escalate.
- Jira moves from workflow code: In Review, then QA (PR).
- Merge queue: serialized, one merge at a time. Before merging, rebase on the latest `main` and re-run CI. The merge happens only after QA (PR) passes.
- Round counters stored in Postgres per ticket and per loop.

## Tasks

- [ ] Reviewer agent, dependency check, GitHub review comments
- [ ] Review loop with cap and escalation
- [ ] QA (PR) mode: run checks against the preview, collect evidence
- [ ] `qa_runs` table writes
- [ ] QA (PR) loop with cap and escalation
- [ ] Serialized merge queue with rebase and CI re-run
- [ ] Jira status moves for In Review and QA (PR)

## Acceptance criteria

- [ ] A PR cannot merge without reviewer approval, green CI, and a passing QA (PR) run on the latest commit (test tries each missing condition).
- [ ] A PR that adds a nonexistent or suspicious package is flagged by the reviewer in a seeded test.
- [ ] Each loop stops at its cap and the ticket becomes Blocked with the owner notified.
- [ ] Two PRs ready at once merge one at a time; the second is rebased and re-tested before merging.
- [ ] QA checks come from the M4 criteria-based checks, not from developer-written tests (verified by provenance in the repo).
- [ ] Reviewer and developer on the same model fails config validation.

## Out of scope

Staging, QA (Main), auto-revert.
