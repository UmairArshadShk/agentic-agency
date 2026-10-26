from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from agency.config import load_config
from agency.config.loader import resolve_instances
from agency.config.schema import ProviderConfig, ResolvedAgent
from agency.llm import FakeChatModel, ProviderError, get_model, register_provider

ROOT = Path(__file__).resolve().parent.parent


def agent(model: str) -> ResolvedAgent:
    cfg = load_config(ROOT / "config/agency.yaml", base_dir=ROOT, env={})
    resolved = resolve_instances(cfg, "pm")[0]
    return resolved.model_copy(update={"model": model})


PROVIDERS = {
    "ollama": ProviderConfig(base_url="http://localhost:11434"),
    "openai": ProviderConfig(api_key_env="OPENAI_API_KEY"),
}


def test_ollama_model_keeps_colons_in_the_model_name() -> None:
    model = get_model(agent("ollama:llama3.1:8b"), PROVIDERS, env={})
    assert isinstance(model, ChatOllama)
    assert model.model == "llama3.1:8b"
    assert model.num_predict == 8000
    assert model.temperature == 0.2


def test_openai_model_reads_its_key_from_the_named_env_var() -> None:
    model = get_model(agent("openai:some-model"), PROVIDERS, env={"OPENAI_API_KEY": "k-test"})
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "some-model"


def test_openai_without_key_fails_naming_the_variable_only() -> None:
    with pytest.raises(ProviderError, match="OPENAI_API_KEY is not set"):
        get_model(agent("openai:some-model"), PROVIDERS, env={})


def test_unconfigured_provider() -> None:
    with pytest.raises(ProviderError, match="not configured"):
        get_model(agent("mistral:large"), PROVIDERS, env={})


def test_configured_provider_without_adapter() -> None:
    providers = {**PROVIDERS, "mistral": ProviderConfig()}
    with pytest.raises(ProviderError, match="no adapter"):
        get_model(agent("mistral:large"), providers, env={})


@pytest.mark.parametrize("model", ["llama", ":x", "ollama:"])
def test_malformed_model_string(model: str) -> None:
    with pytest.raises(ProviderError, match="provider:model"):
        get_model(agent(model), PROVIDERS, env={})


def test_registered_provider_is_used_and_resolves_from_config() -> None:
    fake = FakeChatModel(responses=["hello"])
    register_provider("fake", lambda name, a, p, e: fake)
    model = get_model(agent("fake:scripted"), {"fake": ProviderConfig()}, env={})
    assert model is fake


def test_fake_model_replays_responses_in_order_and_records_calls() -> None:
    model = FakeChatModel(responses=["one", AIMessage(content="two")])
    assert model.invoke([HumanMessage(content="a b c")]).content == "one"
    reply = model.invoke([HumanMessage(content="x")])
    assert reply.content == "two"
    assert len(model.calls) == 2
    assert reply.usage_metadata is not None and reply.usage_metadata["output_tokens"] == 1


def test_fake_model_can_script_tool_calls() -> None:
    call = {"name": "ask_user", "args": {"question": "Who is it for?"}, "id": "c1"}
    model = FakeChatModel(responses=[AIMessage(content="", tool_calls=[call])])
    reply = model.bind_tools([]).invoke([HumanMessage(content="start")])
    assert isinstance(reply, AIMessage)
    assert reply.tool_calls[0]["name"] == "ask_user"


def test_fake_model_fails_loudly_when_script_runs_out() -> None:
    model = FakeChatModel(responses=["only"])
    model.invoke([HumanMessage(content="a")])
    with pytest.raises(AssertionError, match="only 1 responses were scripted"):
        model.invoke([HumanMessage(content="b")])
