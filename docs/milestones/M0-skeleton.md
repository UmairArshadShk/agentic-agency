# M0: Skeleton, config and observability

**Status: done (2026-10-27). All tasks and acceptance criteria pass.**

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
- Auth and isolation: no login for now (see `docs/DECISIONS.md`); every query scoped by `project_id`; a separate workspace directory per project.
- Alembic migrations for `projects`, `project_config_snapshots`, `llm_calls`, `events`, `approvals`.

## Tasks

- [ ] Repo, tooling, CI, compose
- [x] DB models and migrations
- [x] Config schema, loader, validation, snapshot
- [x] Provider abstraction and fake model
- [x] Tracing and cost-logging callback
- [x] Project graph stub with interrupt and checkpointer
- [x] FastAPI endpoints and streaming
- [x] Bare chat UI with approval buttons
- [x] Project scoping (no login, per `docs/DECISIONS.md`; the API-level isolation test lands with the API task)
- [x] State versioning hook
- [x] Record pinned versions in `docs/DECISIONS.md` (deepagents is pinned when first used, in M1/M2)

## Acceptance criteria

- [x] Start a project, reach the gate, stop the server, restart it, approve in the UI, and the workflow continues from where it paused. Evidence: `web/e2e/restart.e2e.ts` (hard `SIGKILL`, new server process, approve in the browser; `make web-e2e`), plus `tests/test_api.py::test_paused_project_resumes_after_the_server_restarts` and `tests/test_project_graph.py::test_pause_survives_a_restart_with_the_postgres_checkpointer`.
- [x] Each validation rule in `docs/CONFIG.md` has a test that fails on bad input, including: unknown tool, singleton role with count above 1, reviewer and developer on the same model, missing env var, over-budget parallelism. Evidence: `tests/test_config.py` (rules 1 to 10, plus rule 11 for pricing).
- [x] Snapshot immutability test: editing `agency.yaml` after a project starts does not change that project's effective config. Evidence: `tests/test_config_snapshot.py::test_editing_agency_yaml_does_not_change_a_started_project`, and database triggers in `tests/test_db.py`.
- [x] A run with the fake model writes `llm_calls` rows with project, agent, model and config version (`tests/test_llm_cost.py`); a real-model run appears in the tracing tool (`scripts/check_tracing.py`: a real `llama3.1:8b` call produced a Langfuse trace whose id matches the `llm_calls` row). The OpenAI path is untested until an `OPENAI_API_KEY` is available.
- [x] Another project's data is unreachable through the API (isolation test). Evidence: `tests/test_api.py::test_projects_are_isolated_from_each_other`, `tests/test_project_scope.py`, `tests/test_workspaces.py`.
- [x] `make test` and `make lint` are green in CI. Evidence: the Python job (121 tests, ruff, pyright) and the web job (lint, typecheck, unit tests, build) are green on `main`. The web job caught a real gap: `next typegen` must run before `tsc` on a clean checkout.

## Out of scope

Real agents, Jira, GitHub, sandboxes, preview environments.
