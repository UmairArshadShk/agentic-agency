# Decisions

Claude Code: append new decisions here with the date, the choice, and the reason. Move items from Open to Decided when resolved. Record pinned library versions at the bottom.

## Decided

| Topic | Decision |
| --- | --- |
| V1 scope | Web apps and websites only, from one or two golden-path stack templates |
| Orchestration | Python with LangGraph, deterministic workflow; agents act only inside a stage |
| Agent building blocks | LangChain Deep Agents for each role's inner work |
| Developer runtime | Deep Agent with sandbox, or a wrapped coding agent (Claude Agent SDK or Claude Code headless). Decided by the M1 spike |
| Client interface | Web chat UI with approvals and a design preview pane |
| Source of truth | LangGraph state in Postgres; Jira mirrors it; workflow code makes all status moves |
| Task tracking | Jira; GitHub Issues and Projects is the fallback if Jira is not required |
| Code hosting | GitHub, one branch and PR per ticket |
| QA | Two stages: QA (PR) on a preview before merge, QA (Main) on staging after merge. Done only after QA (Main) |
| On QA (Main) failure | Auto-revert, pause merges until green, ticket back to the developer |
| Merges | Serialized queue with rebase and CI re-run |
| Dependent tickets | Unblock at Done |
| Agent configuration | One YAML file, validated at startup, snapshotted per project |
| Reviewer model | Must differ from the developer model |
| Users | One owner who is also the client; auth and isolation designed in from M0 |
| Observability | Tracing and cost logging from M0 |

## Open

| Item | Decide by | Notes |
| --- | --- | --- |
| Jira vs GitHub Issues | M0 | Jira site and key provided (see Log); confirm Jira is kept |
| Owner auth before any non-local deployment | Before first non-local deploy | M0 ships with no login (see Log) |
| Developer sandbox: local Docker vs remote service; egress rules; scoped tokens | Before M1 | |
| Models per role; per-run and per-ticket budgets; starting developer count | M2 | |
| Golden-path stack templates (one or two) | M3 | Candidates: Next.js plus Postgres; static site |
| Notification channel | M3 | Email, Slack or push |
| Definition of Done (ticket, project) | M4 | Proposal in `SPEC.md` section 6 |
| Preview and staging hosting; production in scope? | M5 | Production decision can wait until M8 |
| Regression suite cadence on staging | M7 | Smoke per merge, full suite at milestones or nightly |
| Release scope | M8 | |

## Proposed defaults (apply unless overridden)

These came from reviewing the plan. They are not yet confirmed by the owner.

- Test-hook convention: stable `data-testid` names defined in `ARCHITECTURE.md` and the templates, so QA checks are not brittle.
- Project scaffolding is an explicit step before ticket 1: create the repo from the template, set branch protection, install CI secrets.
- Escalation outcomes: raise cap or budget, split ticket, change acceptance criteria, drop or descope, take over manually.
- The PM interview captures third-party services and who supplies the keys.
- Preview environments are torn down on merge, close or abandonment, and after a time limit.
- Auth for V1: a single owner account (password or token session).

## Pinned versions

To be filled in during M0 (Python, LangGraph, deepagents, FastAPI, Next.js, Playwright, Postgres).

## Log

Add entries as `YYYY-MM-DD: decision, reason`.

- 2026-10-26: Stack defaults from CLAUDE.md confirmed for M0 (Python 3.12 with uv, FastAPI, LangGraph with Postgres checkpointer, Pydantic v2, SQLAlchemy 2 with Alembic, Postgres 16, pytest, ruff, pyright, Next.js with pnpm). Reason: owner approved the M0 plan.
- 2026-10-26: Tracing is Langfuse, self-hosted through docker compose. Reason: owner choice; keeps trace data local.
- 2026-10-26: Jira site `recidiviz-internal.atlassian.net`, project key `ATKAMAL123`. Used as placeholders in config until M4; token comes from `JIRA_API_TOKEN`.
- 2026-10-26: Code hosting at GitHub account `UmairArshadShk`, repo `agentic-agency`, private.
- 2026-10-26: No login in M0; anyone who can reach the app can use it. This replaces the "single owner login" in M0 scope and the proposed V1 auth default. Per-project scoping and workspace isolation stay. API and UI bind to localhost by default. Reason: owner wants to keep it simple for now. Auth is an Open item before any non-local deployment.
- 2026-10-26: The one real-model traced run in M0 uses OpenAI. The starter config uses two distinct OpenAI models so the reviewer-differs-from-developers rule can pass.
- 2026-10-26: Milestone files moved from `milestones/` to `docs/milestones/` to match the paths in CLAUDE.md, README.md and ROADMAP.md.
