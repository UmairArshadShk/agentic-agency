# Specification

Status: draft 2, October 2026. This document defines what the agency does. `docs/CONFIG.md` defines how it is configured, and `docs/ROADMAP.md` defines the build order.

## 1. Scope

V1 builds web apps and websites only, from one or two golden-path stack templates (for example Next.js with Postgres, or a static site). Games, mobile apps and desktop apps are out of scope. V1 serves one owner, who is also the client. Auth and per-project isolation are still designed in from the start.

## 2. Roles

| Agent | Count | Responsibility |
| --- | --- | --- |
| PM | 1 | Interviews the client, removes ambiguity, writes `requirements.md` with requirement IDs, owns acceptance criteria and requirement links on tickets, handles change requests. |
| Designer | 1 | Builds a clickable HTML/CSS prototype and a design tokens file inside the architect's chosen stack. |
| Architect | 1 | Picks the stack from the golden-path templates, writes `ARCHITECTURE.md` and conventions, owns the technical task graph (tickets, dependencies, order). |
| Developer | N (config) | Implements one ticket on its own branch in its own sandbox and opens a PR. |
| Reviewer | N (config) | Reviews PR diffs and new dependencies. Must run on a different model than the developers. |
| QA | N (config) | Turns acceptance criteria into executable Playwright checks independently of the developer, runs them on the PR preview (QA PR) and on staging (QA Main), reports requirement coverage. |

The PM, designer and architect work at sequential gates, so their count is fixed at 1. Developer, reviewer and QA counts are set in config.

Agents have no memory between runs. Shared knowledge lives in the project workspace: `requirements.md`, `ARCHITECTURE.md`, `designs/` (with a tokens file), and a decisions log.

## 3. Project workflow

1. **Requirements gathering.** The PM interviews the client in chat and covers non-functional needs: security, performance, accessibility, SEO, content and copy, image assets, browser support, and third-party services (who supplies API keys). Output: draft `requirements.md`.
2. **Stack check.** The architect picks a stack from the golden-path templates so the design targets something implementable.
3. **Design.** The designer produces the prototype and tokens file. **Gate: client approves or requests changes.**
4. **Requirements finalization.** The PM compares the approved design with the requirements, asks remaining questions, and writes the final `requirements.md`. Each requirement has an ID (R-1, R-2, ...), a status and a version. **Gate: client signs off.**
5. **Architecture.** The architect writes `ARCHITECTURE.md` and conventions, including the test-hook convention (stable `data-testid` names) that QA checks rely on.
6. **Project scaffolding and task breakdown.** The system creates the repo from the template, sets branch protection and CI secrets. The architect produces the task graph and dependencies. The PM adds acceptance criteria and requirement links to each Jira ticket. QA turns each criterion into an executable check.
7. **Run tickets.** The ticket graph (section 4) runs for every ticket, in parallel where dependencies allow and developers are free.
8. **Release and handover.** When every ticket is Done, QA produces a requirement-coverage report from QA (Main) results. The system deploys to production if in scope and writes a handover README.
9. **Final acceptance.** **Gate: client accepts the project.**

## 4. Ticket graph

```
pick up -> implement -> open PR
  -> review loop (max 3, then escalate)
  -> CI -> preview deploy
  -> QA (PR) loop (max 3, then escalate)
  -> rebase on main + CI -> merge queue (serialized)
  -> staging deploy -> QA (Main) loop (max 3, auto-revert on failure, then escalate)
  -> Done
```

### QA stages

- **QA (PR)** runs on a preview deployment of the branch before merge. It runs the ticket's checks plus a smoke test.
- **QA (Main)** runs after merge on a persistent staging environment deployed from `main`. It runs the ticket's checks, the accumulated regression suite, and a screenshot comparison against the approved prototype. It catches integration and database migration problems that a fresh per-PR preview cannot.
- A ticket is **Done only after QA (Main) passes.**

### Merge rules

- Merges are serialized through a queue: one merge at a time.
- Before merging, the branch is rebased on the latest `main` and CI re-runs.
- If QA (Main) fails (default `on_qa_main_failure: revert`): the merge is reverted automatically, further merges pause until `main` is green, the failure report is attached to the ticket, and the ticket returns to In Progress as the next round.
- Dependent tickets unblock at Done (default `unblock_dependents_at: done`).

### Statuses

Jira and Postgres use: To Do, In Progress, In Review, QA (PR), QA (Main), Done, Blocked. Postgres holds the authoritative state; Jira mirrors it. Only workflow code changes status. A reconciliation job detects manual Jira edits and reports drift.

### Escalation

When a loop reaches its cap, or a budget is exceeded, the ticket moves to Blocked and the owner is notified (email, Slack or push). The owner chooses one outcome: raise the cap or budget, split the ticket, change the acceptance criteria (PM drafts, owner approves), drop or descope the requirement, or take over manually. The workflow resumes from the recorded choice.

## 5. Change requests

The PM assesses impact, updates `requirements.md` (new version, status changes), creates or modifies tickets, and asks for owner approval. Tickets already Done are never silently changed; a change creates new tickets that reference the same requirement IDs.

## 6. Definitions of Done (proposed, confirm by M4)

- **Ticket:** reviewer approved; CI green; all acceptance-criterion checks pass in QA (PR) and QA (Main); regression suite green; no new dependency flagged; requirement links intact; docs updated when conventions changed.
- **Project:** every requirement is covered by at least one passing check; coverage report has no gaps; staging regression suite green; handover README written; owner accepted.

## 7. Environments

Per-PR preview deployments (torn down on merge, close or abandonment, and by a time limit), one persistent staging environment from `main`, and production if in scope. Hosting for these is decided by M5.

## 8. Security

- Developer agents run only in Docker sandboxes with CPU and memory limits, an egress allowlist, and per-agent scoped tokens.
- Client links, web content, and package dependencies are untrusted. The reviewer checks every new dependency for hallucinated or malicious packages.
- Secrets live in environment variables or a secret store, never in config, prompts, logs or git. Logs redact secrets.
- Third-party API keys needed by the built product are supplied by the owner through the secret store, never pasted into chat.

## 9. Observability and cost

- Trace every agent run (Langfuse or LangSmith) from M0.
- Log every LLM call with project, ticket, agent, model, tokens, cost, and config version.
- Budgets are enforced in code: per run, per ticket, per project. Hitting a budget escalates.
- Reference briefs (2 or 3 sample projects) run as regression evals when prompts, models or config change.

## 10. Data model sketch

Postgres tables (names are guidance; finalize in M0):

| Table | Purpose |
| --- | --- |
| `projects` | id, name, owner, status, created_at, graph_version |
| `project_config_snapshots` | project_id, version, effective_config (JSON), applied_at, applied_by, reason |
| `requirements` | project_id, req_id, version, status, text, design_ref |
| `tickets` | project_id, key, jira_key, state, round counters per loop, requirement_ids, depends_on, branch, pr_url |
| `qa_runs` | ticket, stage (`qa_pr` or `qa_main`), commit_sha, round, result, report_url |
| `approvals` | project_id, gate, decision, comment, decided_at |
| `llm_calls` | project_id, ticket, agent, model, tokens_in, tokens_out, cost, config_version, trace_id |
| `events` | append-only audit log of workflow transitions and escalations |
| LangGraph checkpoint tables | managed by the Postgres checkpointer |

## 11. Out of scope for V1

Multiple clients or tenants, games, mobile and desktop apps, automatic production rollbacks beyond the QA (Main) revert, and a visual workflow editor.
