import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from agency.config import ConfigError, load_config
from agency.config.loader import resolve_instances

ROOT = Path(__file__).resolve().parent.parent
ENV = {"OPENAI_API_KEY": "test-not-a-real-key"}


def base_config() -> dict[str, Any]:
    """A valid config fixture. Starts from the real starter file so the two cannot drift apart."""
    raw = yaml.safe_load((ROOT / "config/agency.yaml").read_text())
    raw["providers"]["openai"] = {"api_key_env": "OPENAI_API_KEY"}
    return raw


def write(tmp_path: Path, raw: dict[str, Any], name: str = "agency.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(raw))
    return path


def load(tmp_path: Path, raw: dict[str, Any], **kwargs: Any):
    return load_config(write(tmp_path, raw), base_dir=ROOT, env=kwargs.pop("env", ENV), **kwargs)


def expect_error(tmp_path: Path, raw: dict[str, Any], fragment: str, **kwargs: Any) -> None:
    with pytest.raises(ConfigError) as exc:
        load(tmp_path, raw, **kwargs)
    assert fragment in str(exc.value), str(exc.value)


def test_starter_config_is_valid() -> None:
    cfg = load_config(ROOT / "config/agency.yaml", base_dir=ROOT, env={})
    assert cfg.agents.developer.count == 2


def test_base_fixture_is_valid(tmp_path: Path) -> None:
    load(tmp_path, base_config())


# Rule 1: unknown keys and unknown tool names
def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["pm"]["colour"] = "blue"
    expect_error(tmp_path, raw, "colour")


def test_unknown_tool_is_rejected(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["pm"]["tools"].append("rm_rf")
    expect_error(tmp_path, raw, "unknown tool 'rm_rf'")


def test_jira_status_tool_is_not_available_to_agents(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["developer"]["tools"].append("jira_transition")
    expect_error(tmp_path, raw, "unknown tool 'jira_transition'")


# Rule 2: singleton roles
@pytest.mark.parametrize("role", ["pm", "designer", "architect"])
def test_singleton_role_with_count_above_one(tmp_path: Path, role: str) -> None:
    raw = base_config()
    raw["agents"][role]["count"] = 2
    expect_error(tmp_path, raw, f"agents.{role}.count must be 1")


# Rule 3: reviewer model differs from developers
def test_reviewer_and_developer_on_same_model(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["reviewer"]["model"] = raw["defaults"]["model"]
    expect_error(tmp_path, raw, "which a developer also uses")


def test_reviewer_matching_a_developer_instance_override(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["developer"]["instances"] = [{"id": "dev-2", "model": "ollama:qwen3:4b"}]
    expect_error(tmp_path, raw, "which a developer also uses")


def test_distinct_reviewer_rule_can_be_turned_off(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["reviewer"]["model"] = raw["defaults"]["model"]
    raw["workflow"]["require_distinct_reviewer_model"] = False
    load(tmp_path, raw)


# Rule 4: environment variables must be set
def test_missing_env_var(tmp_path: Path) -> None:
    expect_error(tmp_path, base_config(), "environment variable OPENAI_API_KEY is not set", env={})


def test_empty_env_var_counts_as_missing(tmp_path: Path) -> None:
    expect_error(tmp_path, base_config(), "OPENAI_API_KEY is not set", env={"OPENAI_API_KEY": ""})


def test_missing_env_error_never_shows_values(tmp_path: Path) -> None:
    secret = "sk-super-secret-value"
    raw = base_config()
    raw["integrations"] = {"github": {"org": "o", "token_env": "GITHUB_TOKEN"}}
    with pytest.raises(ConfigError) as exc:
        load(tmp_path, raw, env={"OPENAI_API_KEY": secret})
    assert secret not in str(exc.value)
    assert "GITHUB_TOKEN" in str(exc.value)


# Rule 5: prompt files exist
def test_missing_prompt_file(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["qa"]["system_prompt_file"] = "prompts/nope.md"
    expect_error(tmp_path, raw, "prompts/nope.md' does not exist")


# Rule 6: counts and parallelism at least 1
def test_developer_count_zero(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["developer"]["count"] = 0
    expect_error(tmp_path, raw, "agents.developer.count")


def test_max_parallel_tickets_zero(tmp_path: Path) -> None:
    raw = base_config()
    raw["workflow"]["max_parallel_tickets"] = 0
    expect_error(tmp_path, raw, "workflow.max_parallel_tickets")


# Rule 7: worst-case parallel spend fits the project budget
def test_over_budget_parallelism(tmp_path: Path) -> None:
    raw = base_config()
    raw["workflow"]["max_parallel_tickets"] = 20
    raw["workflow"]["budgets"]["max_cost_usd_per_project"] = 50
    expect_error(tmp_path, raw, "exceeds budgets.max_cost_usd_per_project")


def test_exactly_fitting_budget_is_allowed(tmp_path: Path) -> None:
    raw = base_config()
    raw["workflow"]["max_parallel_tickets"] = 10
    raw["workflow"]["budgets"]["max_cost_usd_per_project"] = 50
    load(tmp_path, raw)


# Rule 8: provider:model form and configured provider
@pytest.mark.parametrize("model", ["llama3", ":llama3", "ollama:"])
def test_malformed_model_identifier(tmp_path: Path, model: str) -> None:
    raw = base_config()
    raw["agents"]["pm"]["model"] = model
    expect_error(tmp_path, raw, "must be in provider:model form")


def test_unconfigured_provider(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["pm"]["model"] = "mistral:large"
    expect_error(tmp_path, raw, "provider 'mistral' is not configured")


def test_unconfigured_provider_in_instance_override(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["developer"]["instances"] = [{"id": "dev-1", "model": "mistral:large"}]
    expect_error(tmp_path, raw, "provider 'mistral' is not configured")


# Rule 9: loop caps between 1 and 10
@pytest.mark.parametrize("value", [0, 11])
def test_loop_cap_out_of_range(tmp_path: Path, value: int) -> None:
    raw = base_config()
    raw["workflow"]["loop_caps"]["review"] = value
    expect_error(tmp_path, raw, "workflow.loop_caps.review")


# Rule 10: claude_code runtime needs its adapter
def test_claude_code_runtime_without_adapter(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["developer"]["runtime"] = "claude_code"
    expect_error(tmp_path, raw, "adapter 'claude_code' is not installed")


def test_claude_code_runtime_with_adapter_installed(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["developer"]["runtime"] = "claude_code"
    load(tmp_path, raw, installed_runtimes={"deep_agent", "claude_code"})


def test_runtime_is_developer_only(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["pm"]["runtime"] = "deep_agent"
    expect_error(tmp_path, raw, "only valid for developer")


# Rule 11: models on paid providers need a price
def test_paid_model_without_pricing(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["pm"]["model"] = "openai:gpt-x"
    expect_error(tmp_path, raw, "model 'openai:gpt-x' has no entry under pricing")


def test_paid_model_with_pricing(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["pm"]["model"] = "openai:gpt-x"
    raw["pricing"] = {"openai:gpt-x": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}}
    load(tmp_path, raw)


def test_free_provider_needs_no_pricing(tmp_path: Path) -> None:
    load(tmp_path, base_config())


# Instances, merge order and project overrides
def test_instance_id_must_exist(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["developer"]["instances"] = [{"id": "dev-9", "model": "ollama:qwen3:4b"}]
    expect_error(tmp_path, raw, "'dev-9' is not one of")


def test_resolution_order_defaults_role_instance(tmp_path: Path) -> None:
    raw = base_config()
    raw["agents"]["developer"]["model"] = "ollama:qwen3:4b"
    raw["agents"]["reviewer"]["model"] = "ollama:llama3.1:8b"
    raw["agents"]["developer"]["instances"] = [{"id": "dev-2", "model": "openai:gpt-x"}]
    raw["pricing"] = {"openai:gpt-x": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}}
    cfg = load(tmp_path, raw)
    assert [a.model for a in resolve_instances(cfg, "developer")] == [
        "ollama:qwen3:4b",
        "openai:gpt-x",
    ]
    assert resolve_instances(cfg, "pm")[0].model == raw["defaults"]["model"]


def test_project_override_wins_and_leaves_base_untouched(tmp_path: Path) -> None:
    raw = base_config()
    base = write(tmp_path, raw)
    override = write(tmp_path, {"agents": {"pm": {"system_prompt_append": "Be brief."}}}, "o.yaml")
    with_override = load_config(base, override_path=override, base_dir=ROOT, env=ENV)
    without = load_config(base, base_dir=ROOT, env=ENV)
    assert with_override.agents.pm.system_prompt_append == "Be brief."
    assert without.agents.pm.system_prompt_append == ""


def test_project_override_cannot_add_unknown_keys(tmp_path: Path) -> None:
    base = write(tmp_path, base_config())
    override = write(tmp_path, {"agents": {"pm": {"bogus": 1}}}, "o.yaml")
    with pytest.raises(ConfigError, match="bogus"):
        load_config(base, override_path=override, base_dir=ROOT, env=ENV)


def test_project_override_is_validated_like_the_base(tmp_path: Path) -> None:
    base = write(tmp_path, base_config())
    override = write(tmp_path, {"agents": {"pm": {"count": 3}}}, "o.yaml")
    with pytest.raises(ConfigError, match="agents.pm.count must be 1"):
        load_config(base, override_path=override, base_dir=ROOT, env=ENV)


def test_all_errors_are_reported_together(tmp_path: Path) -> None:
    raw = copy.deepcopy(base_config())
    raw["agents"]["pm"]["count"] = 2
    raw["agents"]["qa"]["system_prompt_file"] = "prompts/nope.md"
    with pytest.raises(ConfigError) as exc:
        load(tmp_path, raw)
    assert len(exc.value.errors) == 2
