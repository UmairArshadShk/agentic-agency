"""Per-run observability: cost logging always, Langfuse tracing when keys are in the env."""

import logging
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from sqlalchemy import Engine

from agency.config.schema import AgencyConfig, ResolvedAgent
from agency.llm.cost import CostLogger, price_for

log = logging.getLogger(__name__)


def tracing_enabled(env: Mapping[str, str]) -> bool:
    return bool(env.get("LANGFUSE_PUBLIC_KEY") and env.get("LANGFUSE_SECRET_KEY"))


@contextmanager
def observed_run(
    engine: Engine,
    cfg: AgencyConfig,
    agent: ResolvedAgent,
    *,
    project_id: UUID,
    config_version: int,
    ticket: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Iterator[list[BaseCallbackHandler]]:
    """Yield the callbacks to pass as `config={"callbacks": callbacks}` for every model call.

    With LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY set, the run is wrapped in a Langfuse trace
    (session = project) and its trace id is stored on each llm_calls row. Without them, tracing is
    off and only cost logging runs.
    """
    env = os.environ if env is None else env

    def cost_logger(trace_id: str | None) -> CostLogger:
        return CostLogger(
            engine,
            project_id=project_id,
            agent=agent.id,
            model=agent.model,
            config_version=config_version,
            price=price_for(cfg, agent.model),
            ticket=ticket,
            trace_id=trace_id,
        )

    if not tracing_enabled(env):
        yield [cost_logger(None)]
        return

    from langfuse import Langfuse, propagate_attributes
    from langfuse.langchain import CallbackHandler

    client = Langfuse(
        public_key=env["LANGFUSE_PUBLIC_KEY"],
        secret_key=env["LANGFUSE_SECRET_KEY"],
        host=env.get("LANGFUSE_HOST"),
    )
    metadata = {"agent": agent.id, "model": agent.model, "config_version": str(config_version)}
    if ticket:
        metadata["ticket"] = ticket
    try:
        with (
            client.start_as_current_observation(name=f"{agent.id}-run", as_type="span") as span,
            propagate_attributes(session_id=str(project_id), tags=[agent.role], metadata=metadata),
        ):
            yield [cost_logger(span.trace_id), CallbackHandler()]
    finally:
        client.flush()
