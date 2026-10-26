# M5: Ticket pipeline

**Goal:** a pool of developer agents turns ready tickets into PRs in parallel, with CI, preview deploys, workflow-driven Jira moves, budgets, and escalation.

**Before starting:** decide hosting for preview and staging environments (production can wait). Use the runtime chosen in M1.

## Scope

- Ticket graph stages up to "open PR, CI, preview deploy" (review and QA come in M6 and M7).
- Scheduler: finds tickets whose dependencies are met, assigns them to free developer instances, honors `developer.count` and `workflow.max_parallel_tickets`.
- Per-developer isolation: own sandbox, branch and scoped token. Developers cannot touch each other's branches.
- Developer runs use the configured runtime, model, prompt, tools, sandbox and limits.
- CI on every PR; preview deploy for each PR from the template's hook, with teardown on merge, close, abandonment and after a time limit.
- Workflow-driven Jira moves: To Do to In Progress when picked up, In Progress to In Review when the PR opens.
- Budgets and step limits enforced per run and per ticket. Reaching one moves the ticket to Blocked and notifies the owner.
- Escalation handling: the owner's chosen outcome (raise cap or budget, split ticket, change acceptance criteria, drop or descope, take over) is recorded and the workflow resumes.
- Secrets and permissions: scoped tokens, secret store access, log redaction.

## Tasks

- [ ] Scheduler honoring count, parallelism and dependencies
- [ ] Per-developer sandbox, branch, token
- [ ] Developer node using the chosen runtime
- [ ] PR open, CI trigger, preview deploy and teardown
- [ ] Jira moves from workflow code
- [ ] Budget and step enforcement, Blocked state, notification
- [ ] Escalation outcomes handler
- [ ] Secrets handling and log redaction

## Acceptance criteria

- [ ] With `developer.count: 4` and enough ready tickets, four tickets run at once; with `count: 2`, only two. Never more than `max_parallel_tickets`.
- [ ] A ticket never starts before its dependencies are Done.
- [ ] Each PR gets a working preview URL, which is removed after merge, close, or the time limit.
- [ ] Jira status always matches Postgres after each transition.
- [ ] A ticket that hits its budget becomes Blocked, the owner is notified, and each escalation outcome resumes the workflow correctly (tests for all five).
- [ ] Secrets never appear in logs, transcripts or traces (scan test).
- [ ] Changing `developer.count` in a project's config applies at the next scheduling step without disturbing in-flight tickets.

## Out of scope

Reviewer, QA, merge queue, staging.
