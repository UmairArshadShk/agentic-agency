# Agency build kit

Specification and milestone plans for the AI Agents Agency, written to be used with Claude Code.

## Contents

| File | Purpose |
| --- | --- |
| `CLAUDE.md` | Project context and rules that Claude Code loads automatically. Goes in the repo root. |
| `docs/SPEC.md` | Full behavior spec: roles, workflow, graphs, QA stages, data model, security. |
| `docs/CONFIG.md` | The `agency.yaml` configuration file: agent models, prompts, counts, limits, validation rules. |
| `docs/ROADMAP.md` | Milestones M0 to M8, order, dependencies and decide-by dates. |
| `docs/DECISIONS.md` | Decisions made, open questions, and proposed defaults. Claude Code appends to it. |
| `docs/milestones/M0-*.md` to `M8-*.md` | One file per milestone: scope, tasks, acceptance criteria. |

## Setup

1. Create an empty repo and copy this folder's contents into it, keeping the `docs/` folder and `CLAUDE.md` at the root.
2. Open Claude Code in the repo root.
3. Start with the first prompt below.

## Prompts

First session:

> Read CLAUDE.md, docs/SPEC.md, docs/CONFIG.md and docs/ROADMAP.md. Then read docs/milestones/M0-skeleton.md and, in plan mode, propose an ordered task list for M0. Do not write code until I approve the plan.

Starting each later milestone:

> Read docs/milestones/Mx-....md and check docs/DECISIONS.md for open items due by this milestone. List anything I must decide before you start, then propose an ordered task list. Wait for my approval.

Finishing a milestone:

> Check every acceptance criterion in the milestone file against the code and tests. Report which pass, which do not, and update the checklist and docs/DECISIONS.md.

## Working tips

- Keep one Claude Code session per milestone. Long sessions drift; the docs carry the context.
- Run M1 (the developer spike) before building the PM agent. It tests the riskiest assumption.
- When Claude Code proposes something that conflicts with the invariants in `CLAUDE.md`, ask it to explain why and record the outcome in `docs/DECISIONS.md`.
