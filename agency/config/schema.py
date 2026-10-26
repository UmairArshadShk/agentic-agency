"""Pydantic schema for config/agency.yaml. Unknown keys are rejected everywhere."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderConfig(_Strict):
    api_key_env: str | None = None  # name of an env var, never the key itself
    base_url: str | None = None
    free: bool = False  # local provider: calls cost nothing, no pricing entry needed


class ModelPrice(_Strict):
    """USD per million tokens."""

    input_per_mtok: float = Field(ge=0)
    output_per_mtok: float = Field(ge=0)


class Defaults(_Strict):
    model: str
    temperature: float = 0.2
    max_tokens: int = Field(default=8000, ge=1)


class Limits(_Strict):
    max_steps: int = Field(ge=1)
    max_cost_usd_per_run: float | None = Field(default=None, ge=0)
    max_cost_usd_per_ticket: float | None = Field(default=None, ge=0)


class Sandbox(_Strict):
    type: Literal["docker"] = "docker"
    cpus: float = Field(default=2, gt=0)
    memory_gb: float = Field(default=4, gt=0)
    network: Literal["allowlist", "none"] = "allowlist"


class Instance(_Strict):
    """Per-instance override. `id` is `<prefix>-<n>` with n in 1..count."""

    id: str
    model: str | None = None
    system_prompt_append: str | None = None
    temperature: float | None = None
    max_tokens: int | None = Field(default=None, ge=1)


class AgentConfig(_Strict):
    count: int = Field(default=1, ge=1)
    model: str | None = None  # falls back to defaults.model
    system_prompt_file: str
    system_prompt_append: str = ""
    tools: list[str] = []
    limits: Limits
    instances: list[Instance] = []
    runtime: Literal["deep_agent", "claude_code"] | None = None  # developer only
    sandbox: Sandbox | None = None  # developer only


class Agents(_Strict):
    pm: AgentConfig
    designer: AgentConfig
    architect: AgentConfig
    developer: AgentConfig
    reviewer: AgentConfig
    qa: AgentConfig


class LoopCaps(_Strict):
    review: int = Field(default=3, ge=1, le=10)
    qa_pr: int = Field(default=3, ge=1, le=10)
    qa_main: int = Field(default=3, ge=1, le=10)


class Merge(_Strict):
    serialize: bool = True
    rebase_before_merge: bool = True


class Budgets(_Strict):
    max_cost_usd_per_ticket: float = Field(ge=0)
    max_cost_usd_per_project: float = Field(ge=0)


class Workflow(_Strict):
    max_parallel_tickets: int = Field(ge=1)
    loop_caps: LoopCaps = LoopCaps()
    merge: Merge = Merge()
    on_qa_main_failure: Literal["revert", "freeze_and_fix_forward"] = "revert"
    unblock_dependents_at: Literal["done", "merged"] = "done"
    budgets: Budgets
    require_distinct_reviewer_model: bool = True


class JiraIntegration(_Strict):
    site: str
    project_key: str
    token_env: str


class GithubIntegration(_Strict):
    org: str
    token_env: str


class Notifications(_Strict):
    channel: Literal["email", "slack", "push"]
    to: str


class Integrations(_Strict):
    jira: JiraIntegration | None = None
    github: GithubIntegration | None = None
    notifications: Notifications | None = None


class AgencyConfig(_Strict):
    version: int
    providers: dict[str, ProviderConfig]
    defaults: Defaults
    agents: Agents
    workflow: Workflow
    pricing: dict[str, ModelPrice] = {}  # keyed by provider:model; needed for non-free providers
    integrations: Integrations = Integrations()


class ResolvedAgent(BaseModel):
    """One agent instance after merging defaults, the role entry and its instance override."""

    id: str
    role: str
    model: str
    temperature: float
    max_tokens: int
    system_prompt_file: str
    system_prompt_append: str
    tools: list[str]
    limits: Limits
    runtime: str | None = None
    sandbox: Sandbox | None = None
