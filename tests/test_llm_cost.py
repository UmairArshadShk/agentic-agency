from decimal import Decimal
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from agency.config import load_config
from agency.config.loader import resolve_instances
from agency.config.schema import ModelPrice
from agency.db.models import LlmCall, Project
from agency.llm import FakeChatModel
from agency.llm.cost import CostLogger, calculate_cost, price_for
from agency.llm.observe import observed_run, tracing_enabled

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parent.parent
PRICE = ModelPrice(input_per_mtok=1.0, output_per_mtok=2.0)


@pytest.fixture
def project_id(migrated_engine: Engine):
    with Session(migrated_engine) as session:
        project = Project(name="cost", owner="o")
        session.add(project)
        session.commit()
        return project.id


def rows(engine: Engine, project_id) -> list[LlmCall]:
    with Session(engine) as session:
        return list(session.scalars(select(LlmCall).where(LlmCall.project_id == project_id)))


def test_calculate_cost() -> None:
    assert calculate_cost(1_000_000, 500_000, PRICE) == Decimal("2.0")
    assert calculate_cost(1000, 1000, None) == Decimal(0)


def test_fake_model_run_writes_an_llm_calls_row(migrated_engine: Engine, project_id) -> None:
    cfg = load_config(ROOT / "config/agency.yaml", base_dir=ROOT, env={})
    pm = resolve_instances(cfg, "pm")[0]
    model = FakeChatModel(responses=["two words"])
    with observed_run(
        migrated_engine, cfg, pm, project_id=project_id, config_version=3, ticket="T-1", env={}
    ) as callbacks:
        assert len(callbacks) == 1  # tracing is off without Langfuse keys
        model.invoke([HumanMessage(content="one two three")], config={"callbacks": callbacks})

    (row,) = rows(migrated_engine, project_id)
    assert (row.agent, row.model, row.config_version, row.ticket) == (
        "pm-1",
        "ollama:llama3.1:8b",
        3,
        "T-1",
    )
    assert (row.tokens_in, row.tokens_out) == (3, 2)
    assert row.cost == Decimal(0)  # free local provider
    assert row.trace_id is None


def test_paid_model_cost_is_computed_from_config_pricing(
    migrated_engine: Engine, project_id
) -> None:
    logger = CostLogger(
        migrated_engine,
        project_id=project_id,
        agent="dev-1",
        model="openai:gpt-x",
        config_version=1,
        price=PRICE,
    )
    FakeChatModel(responses=["a b"]).invoke(
        [HumanMessage(content="x " * 1000)], config={"callbacks": [logger]}
    )
    (row,) = rows(migrated_engine, project_id)
    assert row.cost == Decimal("0.001004")  # 1000 in at $1/M plus 2 out at $2/M


def test_paid_call_without_usage_fails_instead_of_logging_free(
    migrated_engine: Engine, project_id
) -> None:
    class NoUsage(FakeChatModel):
        def _generate(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            result = super()._generate(*args, **kwargs)
            result.generations[0].message.usage_metadata = None  # type: ignore[attr-defined]
            return result

    logger = CostLogger(
        migrated_engine,
        project_id=project_id,
        agent="dev-1",
        model="openai:gpt-x",
        config_version=1,
        price=PRICE,
    )
    with pytest.raises(RuntimeError, match="no token usage"):
        NoUsage(responses=["x"]).invoke([HumanMessage(content="y")], config={"callbacks": [logger]})
    assert rows(migrated_engine, project_id) == []


def test_every_call_gets_its_own_row(migrated_engine: Engine, project_id) -> None:
    cfg = load_config(ROOT / "config/agency.yaml", base_dir=ROOT, env={})
    pm = resolve_instances(cfg, "pm")[0]
    model = FakeChatModel(responses=["a", AIMessage(content="b"), "c"])
    with observed_run(
        migrated_engine, cfg, pm, project_id=project_id, config_version=1, env={}
    ) as cb:
        for _ in range(3):
            model.invoke([HumanMessage(content="hi")], config={"callbacks": cb})
    assert len(rows(migrated_engine, project_id)) == 3


def test_price_for_free_and_paid_providers() -> None:
    cfg = load_config(ROOT / "config/agency.yaml", base_dir=ROOT, env={})
    assert price_for(cfg, "ollama:llama3.1:8b") is None


def test_tracing_needs_both_keys() -> None:
    assert not tracing_enabled({})
    assert not tracing_enabled({"LANGFUSE_PUBLIC_KEY": "pk"})
    assert tracing_enabled({"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"})
