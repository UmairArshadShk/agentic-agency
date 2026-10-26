# M4: Finalize and tickets

**Goal:** from an approved design to a signed-off spec, an architecture document, a scaffolded repo, and a populated Jira board where every requirement is covered by at least one ticket and every acceptance criterion has an executable check.

**Before starting:** confirm the Definition of Done for ticket and project (proposal in `docs/SPEC.md` section 6). Provide Jira and GitHub credentials through environment variables.

## Scope

- Requirements finalization stage: the PM compares the approved design with the requirements, asks remaining questions, and writes the final `requirements.md` (new version, statuses set). Sign-off gate for the client.
- `ARCHITECTURE.md` written by the architect: structure, conventions, test-hook convention, data model, environment notes.
- Project scaffolding step: create the GitHub repo from the template, set branch protection, install CI secrets, push the initial commit.
- Task breakdown: the architect produces a task graph (tickets, dependencies, order). Validate that it is a DAG, tickets are small, and every requirement ID is covered.
- PM adds acceptance criteria and requirement links to each ticket.
- `tools/jira.py`: create tickets with links to requirement IDs, mirror status from Postgres, read and comment. Status changes are only callable from workflow code.
- QA authoring: for each acceptance criterion, QA writes an executable Playwright check stored in the repo, independent of any developer tests.
- Jira reconciliation stub that reports drift between Postgres and Jira.
- Reference briefs: define 3 sample projects in `evals/briefs/` (for example a landing page, a small CRUD app, a content site) with expected outcomes, and run them through M0 to M4 as the first regression evals.

## Tasks

- [ ] Finalization stage and sign-off gate
- [ ] `ARCHITECTURE.md` generation
- [ ] Repo scaffolding from template
- [ ] Task graph generation and DAG validation
- [ ] Acceptance criteria and requirement links
- [ ] Jira tool and status mirroring
- [ ] QA check authoring from acceptance criteria
- [ ] Reconciliation stub
- [ ] Reference briefs and eval run

## Acceptance criteria

- [ ] For each reference brief the run produces: a signed-off `requirements.md`, `ARCHITECTURE.md`, a scaffolded repo with CI, and a Jira board with tickets.
- [ ] Coverage check passes: every requirement ID is linked to at least one ticket, and every ticket has acceptance criteria with a matching check.
- [ ] The task graph has no cycles and every ticket lists its dependencies.
- [ ] Agents cannot change Jira status (test proves the tool is not exposed to them).
- [ ] Manually editing a ticket's status in Jira is detected by the reconciliation stub.

## Out of scope

Developers, review, preview deploys, QA runs.
