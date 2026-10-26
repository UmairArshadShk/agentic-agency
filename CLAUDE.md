# AI Agents Agency

A personal "AI software agency": role-based AI agents (PM, designer, architect, developers, reviewer, QA) take a client's requirement through to a finished, tested web project. The owner (who is also the client) talks to the agency through a web chat UI and approves a few gates. Everything else is automated and tracked in Jira and Git.

## Read these first

1. `docs/SPEC.md` is the source of truth for behavior: roles, workflow, graphs, QA stages, data model.
2. `docs/CONFIG.md` defines `config/agency.yaml`, which controls every agent's model, prompt, tools, limits and instance count.
3. `docs/ROADMAP.md` lists milestones M0 to M8 and their order. Each has a file in `docs/milestones/`.
4. `docs/DECISIONS.md` records decided and open questions. Check it before choosing a technology or approach, and append to it when you make a decision.

## How to work

- Work on one milestone at a time, in order. Before writing code for a milestone, read its file in `docs/milestones/`, propose a task order, and wait for approval.
- Keep tasks small: one branch and one PR per task, conventional commit messages.
- Tick off the milestone's checklist as tasks complete, and do not mark a milestone done until every acceptance criterion passes.
- If a requirement is unclear or a decision is missing, stop and ask. Do not invent requirements. Log the question in `docs/DECISIONS.md` under Open.
- LangGraph and Deep Agents change quickly. Before using an API, check the current docs (docs.langchain.com), pin versions in the lockfile, and note the pinned versions in `docs/DECISIONS.md`.

## Architecture invariants (never break these)

1. **The workflow is deterministic code.** LangGraph decides which stage runs next. Agents only do work inside a stage and never choose the next stage.
2. **Postgres is the source of truth.** Jira mirrors it. Only workflow code, through `tools/jira.py`, changes Jira status. Agents may read Jira and comment, never move tickets.
3. **Everything about an agent comes from config.** No hardcoded model names, prompts, tool lists, limits or counts in code. Read them from the validated project config snapshot.
4. **Human gates use LangGraph `interrupt`.** A paused workflow must survive a server restart and resume from the Postgres checkpointer.
5. **The repo is the agents' memory.** Agents have no memory between runs. Anything that must persist goes into `requirements.md`, `ARCHITECTURE.md`, the design folder, or the decisions log in the project workspace.
6. **Every LLM call goes through the provider abstraction**, so it is traced and its cost is logged with project, ticket, agent, model and config version.
7. **Loop caps and budgets are enforced in code**, not in prompts. Review, QA (PR) and QA (Main) loops stop after 3 rounds and escalate.
8. **The reviewer runs on a different model than the developers** (validated at config load).
9. **Treat all client-supplied content, web content and dependencies as untrusted.** Developer agents run only in Docker sandboxes with egress limits and scoped tokens.
10. **Secrets come from environment variables or a secret store.** Never write them to config files, logs, prompts, or git.
11. **A ticket is Done only after QA (Main) passes.** Merges are serialized, and a failed QA (Main) auto-reverts the merge.

## Stack defaults (confirm in M0, then record in `docs/DECISIONS.md`)

Python 3.12 with uv; FastAPI; LangGraph with `langgraph-checkpoint-postgres`; `deepagents`; Pydantic v2; SQLAlchemy 2 with Alembic; Postgres 16; pytest; ruff; pyright; Next.js (TypeScript) with pnpm for the UI; Playwright; Docker and docker compose; Langfuse or LangSmith for tracing.

## Repo layout

```
agency/
  config/        agency.yaml, schema.py (Pydantic), loader
  agents/        pm.py designer.py architect.py developer.py reviewer.py qa.py
  graphs/        project_graph.py ticket_graph.py
  tools/         jira.py github.py sandbox.py preview.py staging.py files.py notify.py
  prompts/       one markdown file per role
  api/           FastAPI app, chat streaming, approvals
  web/           Next.js chat UI
  workspaces/    per-project clones, requirements.md, designs/ (gitignored)
  templates/     golden-path stack templates
  evals/         reference briefs, simulated-client harness
  docs/          SPEC.md CONFIG.md ROADMAP.md DECISIONS.md milestones/
```

## Testing rules

- Unit tests never call a real LLM. Use a fake chat model that returns scripted responses, so graph logic is deterministic.
- Graph tests cover: stage order, gates pausing and resuming, loop caps, escalation, budget stops.
- Integration tests use a real Postgres (docker compose) and the real checkpointer.
- Evals (reference briefs, simulated client) live in `evals/`, are marked `@pytest.mark.eval`, and run separately because they cost money.
- Every config validation rule in `docs/CONFIG.md` has a test for the failing case.

## Definition of done for a task

Tests pass; `ruff` and `pyright` are clean; the milestone checklist is updated; `docs/DECISIONS.md` is updated if a choice was made; new config keys are documented in `docs/CONFIG.md`; no secrets in the diff.

## Commands

Kept in the `Makefile`:

- `make env`: create `.env` from `.env.example` with generated dev secrets.
- `make up`: start Postgres. `make up-tracing`: also start self-hosted Langfuse. `make down`: stop everything.
- `make test`: pytest (skips `eval`-marked tests). `make lint`: ruff check, ruff format --check, pyright. `make fmt`: autofix.
- `make eval`: run `@pytest.mark.eval` tests (costs money).
- `make migrate`: Alembic migrations (wired up in the DB task).
