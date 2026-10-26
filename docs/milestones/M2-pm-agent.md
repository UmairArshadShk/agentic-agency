# M2: PM agent

**Goal:** the requirements interview works end to end over the chat UI and produces a draft `requirements.md` with stable requirement IDs.

**Before starting:** decide models per role (reviewer different from developers), per-run and per-ticket budgets, and the starting developer count. Fill the model placeholders in `config/agency.yaml`.

## Scope

- `agents/pm.py`: a Deep Agent built from the `pm` config, with `prompts/pm.md`.
- `ask_user` tool implemented with LangGraph `interrupt`, so a question pauses the workflow until the client answers in chat.
- Requirements tools: read and write `requirements.md` in the project workspace, and an index of requirements in Postgres (`requirements` table).
- Requirement IDs (R-1, R-2, ...) with a status (draft, approved, changed, dropped) and a version. IDs are never reused.
- Interview coverage checklist in the prompt and as a structured check: goals and users, features, content and copy, image assets, security, performance, accessibility, SEO, browser support, third-party services and who supplies keys, deadlines, out-of-scope items.
- Project graph stages `intake` and `clarify` wired to the PM, ending in a draft for the later gates.
- Simulated-client harness in `evals/`: scripted personas (vague client, decisive client, contradictory client) answering the PM's questions, used as evals.

## Tasks

- [ ] PM agent and prompt, driven by config
- [ ] `ask_user` via interrupt, streamed to the chat UI
- [ ] Requirements store (file plus table) with IDs, status, version
- [ ] Coverage checklist and completeness check
- [ ] Graph stages `intake` and `clarify`
- [ ] Simulated-client harness and first evals
- [ ] Budget and step limits enforced for the PM run

## Acceptance criteria

- [ ] A real chat interview produces a `requirements.md` where every requirement has an ID, status, version and testable wording.
- [ ] The PM asks at least one follow-up on an ambiguous answer and covers every checklist area (verified by the eval harness for all three personas).
- [ ] Closing the browser mid-interview and returning later resumes the same interview.
- [ ] Changing `agents.pm.model` or `system_prompt_append` in config changes behavior for new projects only.
- [ ] A run that exceeds its cost or step limit stops and escalates instead of continuing.

## Out of scope

Design, finalization, tickets, Jira.
