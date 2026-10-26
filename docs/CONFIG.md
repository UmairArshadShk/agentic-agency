# Configuration

All per-agent and per-workflow settings live in `config/agency.yaml`. An optional per-project file, `workspaces/<project>/agency.override.yaml`, can override any value for that project only.

Secrets are never stored in these files. API keys and tokens are referenced by environment variable name.

## Example

Model names are placeholders. Fill them in during M0 and M2.

```yaml
version: 1

providers:
  anthropic: { api_key_env: ANTHROPIC_API_KEY }
  openai:    { api_key_env: OPENAI_API_KEY }

defaults:
  model: "anthropic:<strong-model-id>"
  temperature: 0.2
  max_tokens: 8000

agents:
  pm:
    count: 1
    model: "anthropic:<strong-model-id>"
    system_prompt_file: prompts/pm.md
    system_prompt_append: ""
    tools: [ask_user, read_requirements, write_requirements, jira_read, jira_create_ticket, jira_comment]
    limits: { max_steps: 60, max_cost_usd_per_run: 3.00 }

  designer:
    count: 1
    model: "anthropic:<strong-model-id>"
    system_prompt_file: prompts/designer.md
    tools: [write_file, screenshot, preview_server]
    limits: { max_steps: 80, max_cost_usd_per_run: 4.00 }

  architect:
    count: 1
    model: "anthropic:<strong-model-id>"
    system_prompt_file: prompts/architect.md
    tools: [read_file, write_file, scaffold_repo]
    limits: { max_steps: 60, max_cost_usd_per_run: 3.00 }

  developer:
    count: 4
    runtime: deep_agent            # deep_agent | claude_code (decided by the M1 spike)
    model: "anthropic:<coding-model-id>"
    system_prompt_file: prompts/developer.md
    tools: [shell, edit_file, git, github, test_runner, jira_read, jira_comment]
    sandbox: { type: docker, cpus: 2, memory_gb: 4, network: allowlist }
    limits: { max_steps: 200, max_cost_usd_per_ticket: 5.00 }
    instances:
      - { id: dev-4, model: "openai:<other-model-id>" }

  reviewer:
    count: 1
    model: "openai:<other-model-id>"
    system_prompt_file: prompts/reviewer.md
    tools: [pr_diff, github_comment, dependency_check, jira_read, jira_comment]
    limits: { max_steps: 40, max_cost_usd_per_run: 1.00 }

  qa:
    count: 1
    model: "anthropic:<mid-model-id>"
    system_prompt_file: prompts/qa.md
    tools: [playwright, preview_env, staging_env, screenshot_diff, jira_read, jira_comment]
    limits: { max_steps: 80, max_cost_usd_per_run: 2.00 }

workflow:
  max_parallel_tickets: 4
  loop_caps: { review: 3, qa_pr: 3, qa_main: 3 }
  merge: { serialize: true, rebase_before_merge: true }
  on_qa_main_failure: revert       # revert | freeze_and_fix_forward
  unblock_dependents_at: done      # done | merged
  budgets: { max_cost_usd_per_ticket: 8.00, max_cost_usd_per_project: 200.00 }
  require_distinct_reviewer_model: true

integrations:
  jira:   { site: "<site>.atlassian.net", project_key: "<KEY>", token_env: JIRA_API_TOKEN }
  github: { org: "<org>", token_env: GITHUB_TOKEN }
  notifications: { channel: email, to: "<owner-email>" }
```

## Semantics

- **`count`** is the number of instances of a role. `developer.count: 4` creates four developers, each with its own sandbox, branch and scoped token. PM, designer and architect must be 1.
- **`instances`** (optional) overrides settings for one instance, for example to run one developer on a different model.
- **Effective parallelism** is `min(workflow.max_parallel_tickets, developer.count, tickets whose dependencies are met)`. Merges stay serialized.
- **`system_prompt_file`** points to a markdown file in `prompts/`. `system_prompt_append` adds project-specific instructions without editing the file.
- **`tools`** is an allowlist of registered tool names. Agents cannot use a tool that is not listed. Jira write tools for status changes are never available to agents.
- **`limits`** are enforced in code by the agent runner. Reaching one stops the run and escalates.

## Validation (run at load; each rule needs a failing-case test)

1. Unknown keys and unknown tool names are rejected.
2. `pm`, `designer` and `architect` must have `count: 1`.
3. `workflow.require_distinct_reviewer_model: true` requires the reviewer's model (including any instance override) to differ from every developer model.
4. Every referenced environment variable must be set (checked at startup, never logged).
5. Every `system_prompt_file` must exist.
6. `workflow.max_parallel_tickets` must be at least 1, and `developer.count` must be at least 1.
7. The worst-case cost of running `max_parallel_tickets` tickets at their per-ticket limit must not exceed `budgets.max_cost_usd_per_project`.
8. Model identifiers must use the `provider:model` form and the provider must be configured.
9. `loop_caps` values must be between 1 and 10.
10. A developer `runtime` of `claude_code` requires the matching runtime adapter to be installed.

## Lifecycle

- The loader merges `defaults`, then `agents.<role>`, then `instances`, then the per-project override, and validates the result with the Pydantic schema in `config/schema.py`.
- When a project starts, the effective config is saved as a versioned, immutable row in `project_config_snapshots`.
- Editing `agency.yaml` affects new projects only. Running projects keep their snapshot unless the owner explicitly applies a change. Applying a change creates a new snapshot version, records who applied it and why, and is logged in `events`.
- A change that reduces `developer.count` lets in-flight tickets finish and stops assigning new ones to the removed instances. A change that raises it takes effect at the next scheduling step.
- Every cost-log row records the config snapshot version that produced it, so model and prompt changes can be compared on the reference briefs.

## Implementation notes (M0)

- **Code:** schema in `agency/config/schema.py`, loader and validation in `agency/config/loader.py`, snapshots in `agency/config/snapshot.py`. The loader reports every problem at once in a `ConfigError`.
- **Providers:** each entry takes `api_key_env` (name of an env var; rule 4 requires it to be set and non-empty) and optional `base_url`. Local providers such as `ollama` need no key. Model strings split on the first colon, so `ollama:llama3.1:8b` is provider `ollama`, model `llama3.1:8b`.
- **Model fallback:** `agents.<role>.model` is optional and falls back to `defaults.model`.
- **Instance ids:** instances are numbered from 1 with a role prefix: `pm-1`, `designer-1`, `architect-1`, `dev-1..dev-N`, `rev-1..rev-N`, `qa-1..qa-N`. An `instances` entry must use one of these ids. Overridable per instance: `model`, `system_prompt_append`, `temperature`, `max_tokens`. `resolve_instances(cfg, role)` returns one fully merged `ResolvedAgent` per instance.
- **Tool names:** the allowlist of valid names is `agency/tools/registry.py`. Jira status tools are intentionally not in it.
- **Runtimes:** installed adapters are listed in `agency/agents/runtimes.py` (rule 10). `runtime` and `sandbox` are valid only on `developer`.
- **Integrations are optional.** Omit the block until M4; once `jira` or `github` is present, its `token_env` must be set.
- **Rule 7:** worst case is `workflow.max_parallel_tickets` times the larger of `workflow.budgets.max_cost_usd_per_ticket` and `agents.developer.limits.max_cost_usd_per_ticket`.
- **Cost caps and local models:** Ollama calls are logged with cost 0, so cost caps are inert for them; `max_steps` is the active limit.
- **Project override:** `workspaces/<project>/agency.override.yaml` is deep-merged onto `agency.yaml` (mappings merge, lists and scalars replace) and the result goes through the same validation.
- **Pricing and `free` (validation rule 11):** `providers.<name>.free: true` marks a local provider (Ollama) whose calls cost nothing. Every model on a non-free provider needs a `pricing` entry keyed by `provider:model` with `input_per_mtok` and `output_per_mtok` (USD per million tokens), so cost caps can be enforced. Prices live only in config. A paid call that returns no token usage fails the run instead of being logged as free.
- **Cost log and tracing:** `agency/llm/observe.py` `observed_run(...)` yields the callbacks to pass on every model call. `CostLogger` writes an `llm_calls` row (project, ticket, agent instance id, model, tokens, cost, config snapshot version, trace id). Langfuse tracing turns on when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set (`LANGFUSE_HOST` for the server URL); without them only cost logging runs.
