# M8: Release and hardening

**Goal:** finish the project lifecycle (release, handover, acceptance) and make the agency dependable: change requests, reconciliation, budgets, regression evals, security checks.

**Before starting:** decide the release scope (production hosting, domain, environment config, handover README) or declare production deploy out of scope for V1.

## Scope

- Release stage: when every ticket is Done, QA produces the requirement-coverage report from QA (Main) results; deploy to production if in scope; write the handover README (how to run, deploy, configure, and where secrets live).
- Final acceptance gate for the client.
- Change-request flow: the PM assesses impact, updates `requirements.md` (new version, statuses), creates or modifies tickets, and asks for owner approval. Done tickets are never edited silently; changes create new tickets referencing the same requirement IDs.
- Jira reconciliation job: scheduled, detects and reports drift, never overwrites Postgres from Jira without owner approval.
- Budgets: per-project budget enforced across all tickets and agents; clear spend summaries per ticket and per role.
- Config change controls: applying a config change to a running project creates a new snapshot version, records who and why, and is logged.
- Reliability: retries with backoff for LLM, GitHub and Jira calls; idempotent stages so a crash mid-stage can resume.
- Security pass: prompt-injection tests (malicious text in client content, web pages, package READMEs), secret scanning of logs and repos, sandbox escape tests, dependency policy checks.
- Regression evals: the reference briefs run on a schedule and on any change to prompts, models, or config; results are compared across config versions.
- Observability: dashboards for cost per ticket, loop counts, escalation rate, and success rate.

## Tasks

- [ ] Coverage report and release stage
- [ ] Production deploy (or documented out of scope) and handover README
- [ ] Final acceptance gate
- [ ] Change-request flow
- [ ] Scheduled reconciliation
- [ ] Project budget enforcement and spend summaries
- [ ] Config change application with audit trail
- [ ] Retries and idempotent stages
- [ ] Security tests
- [ ] Scheduled regression evals and comparison
- [ ] Dashboards

## Acceptance criteria

- [ ] A reference brief runs from first question to accepted project with only the defined gates needing the owner.
- [ ] The coverage report lists every requirement with its tickets and the QA (Main) evidence; a gap blocks release.
- [ ] A change request mid-project creates new tickets and leaves Done tickets unchanged.
- [ ] Killing the process at a random point in any stage and restarting finishes the run without duplicated PRs, tickets, or merges.
- [ ] Prompt-injection and secret-leak tests pass.
- [ ] The regression eval report compares at least two config versions on the same briefs.
- [ ] A project that hits its budget stops and escalates rather than overspending.

## Out of scope

Multi-tenant support, additional project types, a visual workflow editor.
