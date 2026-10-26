"""The one place chat models are built. Every LLM call goes through get_model (invariant 6).

Model names, keys and limits come from the resolved agent config and the providers block, never
from code. Tracing and cost callbacks are attached by the agent runner, not here.
"""

import os
from collections.abc import Callable, Mapping

from langchain_core.language_models.chat_models import BaseChatModel

from agency.config.schema import ProviderConfig, ResolvedAgent

ProviderFactory = Callable[[str, ResolvedAgent, ProviderConfig, Mapping[str, str]], BaseChatModel]


class ProviderError(Exception):
    pass


def split_model(model: str) -> tuple[str, str]:
    """'ollama:llama3.1:8b' -> ('ollama', 'llama3.1:8b'). Splits on the first colon only."""
    provider, sep, name = model.partition(":")
    if not (sep and provider and name):
        raise ProviderError(f"model '{model}' must be in provider:model form")
    return provider, name


def _api_key(provider: str, cfg: ProviderConfig, env: Mapping[str, str]) -> str:
    if not cfg.api_key_env:
        raise ProviderError(f"provider '{provider}' needs api_key_env in config")
    key = env.get(cfg.api_key_env)
    if not key:
        raise ProviderError(f"environment variable {cfg.api_key_env} is not set")
    return key


def _ollama(
    name: str, agent: ResolvedAgent, cfg: ProviderConfig, env: Mapping[str, str]
) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=name,
        base_url=cfg.base_url,
        temperature=agent.temperature,
        num_predict=agent.max_tokens,
    )


def _openai(
    name: str, agent: ResolvedAgent, cfg: ProviderConfig, env: Mapping[str, str]
) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=name,
        api_key=_api_key("openai", cfg, env),  # type: ignore[arg-type]
        base_url=cfg.base_url,
        temperature=agent.temperature,
        max_completion_tokens=agent.max_tokens,
    )


_FACTORIES: dict[str, ProviderFactory] = {"ollama": _ollama, "openai": _openai}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Add a provider (tests register a fake one)."""
    _FACTORIES[name] = factory


def get_model(
    agent: ResolvedAgent,
    providers: Mapping[str, ProviderConfig],
    *,
    env: Mapping[str, str] | None = None,
) -> BaseChatModel:
    """Build the chat model for one resolved agent instance."""
    provider, name = split_model(agent.model)
    if provider not in providers:
        raise ProviderError(f"provider '{provider}' is not configured under providers")
    factory = _FACTORIES.get(provider)
    if factory is None:
        raise ProviderError(f"no adapter for provider '{provider}'")
    return factory(name, agent, providers[provider], os.environ if env is None else env)
