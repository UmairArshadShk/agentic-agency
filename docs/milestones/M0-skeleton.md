# M0: Skeleton, config and observability

**Goal:** a runnable skeleton where a workflow can pause for a human, survive a restart, and resume, with config, tracing and cost logging in place from day one.

**Before starting:** confirm the stack defaults in `CLAUDE.md`, and get the owner's Jira and GitHub details (these can be placeholders until M4).

## Scope

- Repo setup: uv project, ruff, pyright, pytest, pre-commit, `Makefile`, GitHub Actions for lint and tests, `.env.example`.
- `docker compose` with Postgres 16.
- FastAPI app with health endpoint, project endpoints, chat streaming (SSE or WebSocket) and approval endpoints.
- LangGraph project graph stub with 3 dummy stages and one human gate using `interrupt`, backed by the Postgres checkpointer.
- Bare Next.js chat UI: message list, input, streaming output, Approve and Request changes buttons.
- Config: `config/schema.py` (Pydantic v2), loader with the merge order from `docs/CONFIG.md`, all 10 validation rules, per-project immutable snapshot table.
- Provider abstraction: `get_model(agent_config)` returning a chat model for `provider:model` strings, plus a fake model for tests.
- Tracing (Langfuse or LangSmith, chosen by env) and an `llm_calls` cost table filled by a callback on every model call.
- State versioning: a `graph_version` stored in state and a migration hook run on resume.
- Auth and isolation: single owner login; every query scoped by `project_id`; a separate workspace directory per project.
- Alembic migrations for `projects`, `project_config_snapshots`, `llm_calls`, `events`, `approvals`.

## Tasks

- [ ] Repo, tooling, CI, compose
- [x] DB models and migrations
- [x] Config schema, loader, validation, snapshot
- [x] Provider abstraction and fake model
- [ ] Tracing and cost-logging callback
- [ ] Project graph stub with interrupt and checkpointer
- [ ] FastAPI endpoints and streaming
- [ ] Bare chat UI with approval buttons
- [ ] Owner auth and project scoping
- [ ] State versioning hook
- [ ] Record pinned versions in `docs/DECISIONS.md`

## Acceptance criteria

- [ ] Start a project, reach the gate, stop the server, restart it, approve in the UI, and the workflow continues from where it paused.
- [ ] Each validation rule in `docs/CONFIG.md` has a test that fails on bad input, including: unknown tool, singleton role with count above 1, reviewer and developer on the same model, missing env var, over-budget parallelism.
- [ ] Snapshot immutability test: editing `agency.yaml` after a project starts does not change that project's effective config.
- [ ] A run with the fake model writes `llm_calls` rows with project, agent, model and config version; a real-model run appears in the tracing tool.
- [ ] Another project's data is unreachable through the API (isolation test).
- [ ] `make test` and `make lint` are green in CI.

## Out of scope

Real agents, Jira, GitHub, sandboxes, preview environments.
