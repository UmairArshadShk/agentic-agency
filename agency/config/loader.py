"""Load, merge and validate agency config.

Merge order (docs/CONFIG.md): defaults, then agents.<role>, then instances, then the per-project
override. The override file is deep-merged onto the base file before validation, so it can change
any value but cannot introduce unknown keys.
"""

import os
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from agency.agents.runtimes import INSTALLED_RUNTIMES
from agency.config.schema import AgencyConfig, AgentConfig, ResolvedAgent
from agency.tools.registry import KNOWN_TOOLS

SINGLETON_ROLES = ("pm", "designer", "architect")
INSTANCE_PREFIX = {
    "pm": "pm",
    "designer": "designer",
    "architect": "architect",
    "developer": "dev",
    "reviewer": "rev",
    "qa": "qa",
}


class ConfigError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("invalid config:\n" + "\n".join(f"- {e}" for e in errors))


def deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge mappings; any other value (including lists) is replaced."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ConfigError([f"{path}: top level must be a mapping"])
    return data  # type: ignore[return-value]


def instance_ids(role: str, agent: AgentConfig) -> list[str]:
    return [f"{INSTANCE_PREFIX[role]}-{n}" for n in range(1, agent.count + 1)]


def resolve_instances(cfg: AgencyConfig, role: str) -> list[ResolvedAgent]:
    """Merge defaults, the role entry and each instance override, one result per instance."""
    agent: AgentConfig = getattr(cfg.agents, role)
    overrides = {i.id: i for i in agent.instances}
    resolved: list[ResolvedAgent] = []
    for instance_id in instance_ids(role, agent):
        override = overrides.get(instance_id)
        append = agent.system_prompt_append
        if override and override.system_prompt_append is not None:
            append = override.system_prompt_append
        resolved.append(
            ResolvedAgent(
                id=instance_id,
                role=role,
                model=(override and override.model) or agent.model or cfg.defaults.model,
                temperature=(override and override.temperature) or cfg.defaults.temperature,
                max_tokens=(override and override.max_tokens) or cfg.defaults.max_tokens,
                system_prompt_file=agent.system_prompt_file,
                system_prompt_append=append,
                tools=list(agent.tools),
                limits=agent.limits,
                runtime=agent.runtime,
                sandbox=agent.sandbox,
            )
        )
    return resolved


def _all_model_refs(cfg: AgencyConfig) -> list[tuple[str, str]]:
    refs = [("defaults.model", cfg.defaults.model)]
    for role in INSTANCE_PREFIX:
        agent: AgentConfig = getattr(cfg.agents, role)
        if agent.model:
            refs.append((f"agents.{role}.model", agent.model))
        refs += [
            (f"agents.{role}.instances[{i.id}].model", i.model) for i in agent.instances if i.model
        ]
    return refs


def validate(
    cfg: AgencyConfig,
    *,
    env: Mapping[str, str],
    base_dir: Path,
    known_tools: Collection[str] = KNOWN_TOOLS,
    installed_runtimes: Collection[str] = INSTALLED_RUNTIMES,
) -> list[str]:
    """Semantic rules from docs/CONFIG.md that the schema alone cannot express."""
    errors: list[str] = []

    # 1. unknown tool names (unknown keys are rejected by the schema)
    for role in INSTANCE_PREFIX:
        agent: AgentConfig = getattr(cfg.agents, role)
        for tool in agent.tools:
            if tool not in known_tools:
                errors.append(f"agents.{role}.tools: unknown tool '{tool}'")

    # 2. singleton roles
    for role in SINGLETON_ROLES:
        count = getattr(cfg.agents, role).count
        if count != 1:
            errors.append(f"agents.{role}.count must be 1 (got {count})")

    # instance overrides must target an existing instance
    for role in INSTANCE_PREFIX:
        agent = getattr(cfg.agents, role)
        valid = set(instance_ids(role, agent))
        for instance in agent.instances:
            if instance.id not in valid:
                errors.append(
                    f"agents.{role}.instances: '{instance.id}' is not one of {sorted(valid)}"
                )

    # 8. model identifiers use provider:model and the provider is configured
    for where, model in _all_model_refs(cfg):
        provider, sep, name = model.partition(":")
        if not sep or not provider or not name:
            errors.append(f"{where}: '{model}' must be in provider:model form")
        elif provider not in cfg.providers:
            errors.append(f"{where}: provider '{provider}' is not configured under providers")

    # 11. every model on a paid provider has a price, so cost caps can be enforced
    for where, model in _all_model_refs(cfg):
        provider = model.partition(":")[0]
        configured = cfg.providers.get(provider)
        if configured and not configured.free and model not in cfg.pricing:
            errors.append(
                f"{where}: model '{model}' has no entry under pricing (provider is not free)"
            )

    # 3. reviewer model differs from every developer model (instance overrides included)
    if cfg.workflow.require_distinct_reviewer_model:
        dev_models = {a.model for a in resolve_instances(cfg, "developer")}
        for reviewer in resolve_instances(cfg, "reviewer"):
            if reviewer.model in dev_models:
                errors.append(
                    f"reviewer '{reviewer.id}' uses model '{reviewer.model}', which a developer "
                    "also uses (workflow.require_distinct_reviewer_model is true)"
                )

    # 4. referenced environment variables are set (names only, values are never logged)
    env_refs = [(f"providers.{n}.api_key_env", p.api_key_env) for n, p in cfg.providers.items()]
    if cfg.integrations.jira:
        env_refs.append(("integrations.jira.token_env", cfg.integrations.jira.token_env))
    if cfg.integrations.github:
        env_refs.append(("integrations.github.token_env", cfg.integrations.github.token_env))
    for where, var in env_refs:
        if var and not env.get(var):
            errors.append(f"{where}: environment variable {var} is not set")

    # 5. prompt files exist
    for role in INSTANCE_PREFIX:
        prompt = getattr(cfg.agents, role).system_prompt_file
        if not (base_dir / prompt).is_file():
            errors.append(f"agents.{role}.system_prompt_file: '{prompt}' does not exist")

    # 7. worst-case parallel spend fits the project budget
    dev_ticket_cap = cfg.agents.developer.limits.max_cost_usd_per_ticket or 0.0
    per_ticket = max(cfg.workflow.budgets.max_cost_usd_per_ticket, dev_ticket_cap)
    worst_case = cfg.workflow.max_parallel_tickets * per_ticket
    if worst_case > cfg.workflow.budgets.max_cost_usd_per_project:
        errors.append(
            f"workflow: {cfg.workflow.max_parallel_tickets} parallel tickets x ${per_ticket:.2f} = "
            f"${worst_case:.2f} exceeds budgets.max_cost_usd_per_project "
            f"(${cfg.workflow.budgets.max_cost_usd_per_project:.2f})"
        )

    # 10. runtime adapter installed; runtime and sandbox are developer-only
    for role in INSTANCE_PREFIX:
        agent = getattr(cfg.agents, role)
        if role != "developer" and (agent.runtime or agent.sandbox):
            errors.append(f"agents.{role}: runtime and sandbox are only valid for developer")
    runtime = cfg.agents.developer.runtime
    if runtime and runtime not in installed_runtimes:
        errors.append(f"agents.developer.runtime: adapter '{runtime}' is not installed")

    # 6 and 9 (counts and loop caps) are enforced by Field constraints in the schema.
    return errors


def load_config(
    path: str | Path,
    *,
    override_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    base_dir: str | Path | None = None,
    known_tools: Collection[str] = KNOWN_TOOLS,
    installed_runtimes: Collection[str] = INSTALLED_RUNTIMES,
) -> AgencyConfig:
    """Read the YAML (plus optional project override), validate, and return the config.

    Raises ConfigError listing every problem found.
    """
    path = Path(path)
    raw = _read_yaml(path)
    if override_path is not None and Path(override_path).is_file():
        raw = deep_merge(raw, _read_yaml(Path(override_path)))
    try:
        cfg = AgencyConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(
            [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        ) from exc
    errors = validate(
        cfg,
        env=os.environ if env is None else env,
        base_dir=Path(base_dir) if base_dir else path.resolve().parent.parent,
        known_tools=known_tools,
        installed_runtimes=installed_runtimes,
    )
    if errors:
        raise ConfigError(errors)
    return cfg
