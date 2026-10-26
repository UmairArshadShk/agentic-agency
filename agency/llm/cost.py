"""Writes one llm_calls row per model call, with the config snapshot version that produced it."""

import logging
import uuid
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agency.config.schema import AgencyConfig, ModelPrice
from agency.db.models import LlmCall

log = logging.getLogger(__name__)

_MILLION = Decimal(1_000_000)


def price_for(cfg: AgencyConfig, model: str) -> ModelPrice | None:
    """None means free (local provider). Config validation guarantees paid models have a price."""
    provider = model.partition(":")[0]
    if cfg.providers[provider].free:
        return None
    return cfg.pricing[model]


def calculate_cost(tokens_in: int, tokens_out: int, price: ModelPrice | None) -> Decimal:
    if price is None:
        return Decimal(0)
    return (
        Decimal(tokens_in) * Decimal(str(price.input_per_mtok))
        + Decimal(tokens_out) * Decimal(str(price.output_per_mtok))
    ) / _MILLION


def _usage(response: LLMResult) -> tuple[int, int] | None:
    for generations in response.generations:
        for generation in generations:
            usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
            if usage:
                return usage["input_tokens"], usage["output_tokens"]
    token_usage = (response.llm_output or {}).get("token_usage")
    if token_usage:
        return token_usage.get("prompt_tokens", 0), token_usage.get("completion_tokens", 0)
    return None


class CostLogger(BaseCallbackHandler):
    """Attach to every model call. A failed write fails the run: cost accounting is an invariant."""

    raise_error = True

    def __init__(
        self,
        engine: Engine,
        *,
        project_id: UUID,
        agent: str,
        model: str,
        config_version: int,
        price: ModelPrice | None,
        ticket: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.engine = engine
        self.project_id = project_id
        self.agent = agent
        self.model = model
        self.config_version = config_version
        self.price = price
        self.ticket = ticket
        self.trace_id = trace_id

    def on_llm_end(self, response: LLMResult, *, run_id: uuid.UUID, **kwargs: Any) -> None:
        usage = _usage(response)
        if usage is None:
            if self.price is not None:
                # A paid call with unknown usage would silently bypass budget caps.
                raise RuntimeError(f"model {self.model} returned no token usage; cost unknown")
            log.warning("model %s returned no token usage; logging zeros", self.model)
            usage = (0, 0)
        tokens_in, tokens_out = usage
        with Session(self.engine) as session:
            session.add(
                LlmCall(
                    project_id=self.project_id,
                    ticket=self.ticket,
                    agent=self.agent,
                    model=self.model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost=calculate_cost(tokens_in, tokens_out, self.price),
                    config_version=self.config_version,
                    trace_id=self.trace_id,
                )
            )
            session.commit()
