# Roadmap

The order is risk-first: M1 tests whether a developer agent can reliably produce a working PR before the front half of the pipeline is built.

| # | Milestone | Outcome | File |
| --- | --- | --- | --- |
| M0 | Skeleton, config and observability | Pause and resume works across restarts; config loaded, validated and snapshotted; tracing and cost logging live | `milestones/M0-skeleton.md` |
| M1 | Developer spike | One hand-written ticket becomes a PR from a sandboxed developer agent; runtime choice made with evidence | `milestones/M1-developer-spike.md` |
| M2 | PM agent | Requirements interview over chat produces a draft `requirements.md` with IDs | `milestones/M2-pm-agent.md` |
| M3 | Architect and Designer | Stack check, prototype, tokens file, preview pane, approve and request-changes, notifications | `milestones/M3-architect-designer.md` |
| M4 | Finalize and tickets | Signed-off spec, `ARCHITECTURE.md`, scaffolded repo, populated Jira board, QA checks per criterion | `milestones/M4-finalize-and-tickets.md` |
| M5 | Ticket pipeline | Developer pool opens PRs from tickets in parallel with CI, preview deploys and workflow-driven Jira moves | `milestones/M5-ticket-pipeline.md` |
| M6 | Reviewer and QA (PR) | Review loop, QA on the preview, serialized merge queue, loop caps and escalation | `milestones/M6-reviewer-and-qa-pr.md` |
| M7 | Staging and QA (Main) | Staging deploy, regression suite, auto-revert, Done only after QA (Main) | `milestones/M7-staging-and-qa-main.md` |
| M8 | Release and hardening | Release and handover, change requests, reconciliation, budgets, regression evals in CI | `milestones/M8-release-and-hardening.md` |

M0 to M4 yields the first demonstrable result: talk to the agency, get a signed-off spec and a populated Jira board. M5 to M7 complete the build pipeline. M8 makes it dependable.

## Dependencies

- M1 needs M0's sandbox-free pieces only (config loader, provider abstraction, tracing). It does not need the project graph.
- M2 to M4 build the project graph on M0's pause and resume.
- M5 needs M1's runtime decision and M4's tickets.
- M6 needs M5. M7 needs M6.
- The reference briefs start in M4 and run as regression evals from M5 onward.

## Decisions needed before each milestone

| Decide by | Decision |
| --- | --- |
| M0 | Jira site and project key, GitHub account or org, and whether GitHub Issues and Projects can replace Jira |
| Before M1 | How developer agents run code (local Docker or remote sandbox), egress rules, scoped tokens |
| M2 | LLM providers and models per role (reviewer different from developers), per-run and per-ticket budgets, starting developer count |
| M3 | The one or two golden-path stack templates; the notification channel |
| M4 | Definition of Done for ticket and project (proposal in `SPEC.md`) |
| M5 | Hosting for preview and staging environments (and production, if in scope) |
| M7 | Confirm QA (Main) defaults: revert on failure, serialized merges, unblock at Done, regression cadence |
| M8 | Release scope: production hosting, domain, environment config, handover README, or declared out of scope |
