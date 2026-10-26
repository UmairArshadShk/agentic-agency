"""A scripted chat model for tests. Unit tests never call a real LLM."""

from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr


class FakeChatModel(BaseChatModel):
    """Returns the scripted responses in order and records every prompt it receives.

    A string becomes a plain AIMessage; pass an AIMessage to script tool calls. Token usage is a
    word count, so cost-logging tests have non-zero numbers. Running out of responses raises, so a
    test that triggers an unexpected extra call fails loudly.
    """

    # Typed Any: pydantic's AIMessage validator chokes on a union with str.
    responses: Sequence[Any]
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    _next: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "fake-scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeChatModel":
        return self  # scripted tool calls come from the responses, not from the bound tools

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self._next >= len(self.responses):
            raise AssertionError(
                f"FakeChatModel received call #{self._next + 1} but only "
                f"{len(self.responses)} responses were scripted"
            )
        scripted = self.responses[self._next]
        self._next += 1
        self.calls.append(list(messages))

        message = (
            AIMessage(content=scripted) if isinstance(scripted, str) else scripted.model_copy()
        )
        tokens_in = sum(len(str(m.content).split()) for m in messages)
        tokens_out = len(str(message.content).split())
        message.usage_metadata = {
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "total_tokens": tokens_in + tokens_out,
        }
        return ChatResult(generations=[ChatGeneration(message=message)])
