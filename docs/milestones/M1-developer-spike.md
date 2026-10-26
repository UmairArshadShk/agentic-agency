# M1: Developer spike

**Goal:** find out, with evidence, whether a developer agent can reliably turn a ticket into a working PR inside a sandbox, and choose the runtime. This is the riskiest assumption, so it runs before the front half of the pipeline is built.

**Before starting:** decide how agents run code (local Docker or a remote sandbox), the egress allowlist, and scoped-token approach. Create a throwaway GitHub repo and a scoped token.

## Scope

- A `DeveloperRuntime` interface: `run(ticket, workspace, config) -> DevResult` (branch, PR URL, test results, cost, steps, transcript path).
- Two adapters behind that interface: a Deep Agent with a sandboxed shell backend, and a wrapped coding agent (Claude Agent SDK or Claude Code in headless mode).
- Docker sandbox: CPU and memory limits, egress allowlist (package registries and the git host only), no host mounts except the workspace, per-run scoped GitHub token, secrets never inside the container image.
- A target repo from a minimal stack template, with CI and a test runner.
- A set of at least 6 hand-written tickets of rising difficulty (config tweak, new component, new API route, form with validation, a refactor, a bug fix with a failing test).
- A harness that runs each ticket on each runtime and records outcome, cost, wall time, steps, and failure mode.
- Configuration of the developer through `agency.yaml` (`runtime`, `model`, `sandbox`, `limits`).

## Tasks

- [ ] Define `DeveloperRuntime` and `DevResult`
- [ ] Docker sandbox with egress allowlist and resource limits
- [ ] GitHub tool: branch, push, open PR with a scoped token
- [ ] Deep Agent adapter
- [ ] Coding-agent adapter
- [ ] Ticket set and harness
- [ ] Run both runtimes on all tickets; write `docs/spikes/M1-developer-runtime.md`
- [ ] Record the runtime decision in `docs/DECISIONS.md`

## Acceptance criteria

- [ ] At least one runtime opens a PR with passing CI for most of the tickets (report the actual rate).
- [ ] The report compares both runtimes on success rate, cost per ticket, time, and the main failure modes, with transcripts linked.
- [ ] The sandbox blocks a request to a non-allowlisted host and cannot read the host filesystem (tests prove both).
- [ ] The scoped token cannot touch any repo other than the target.
- [ ] `docs/DECISIONS.md` records the chosen default runtime and what would change the choice.

## Out of scope

Jira, review, QA, multi-developer scheduling, merge queue.
