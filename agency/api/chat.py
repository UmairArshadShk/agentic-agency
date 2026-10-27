"""Chat streaming over Server-Sent Events.

The reply comes from a stub responder until the PM agent exists (M2). The wire format is final:
`event: token` with {"text": ...} per chunk, then `event: done`. Swapping in a real agent only
changes where the chunks come from.
"""

import asyncio
import json
from collections.abc import AsyncIterator


def sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def stub_reply(message: str, status: str, pending_gate: bool) -> str:
    if pending_gate:
        hint = "The project is waiting at the approval gate. Use Approve or Request changes."
    elif status == "completed":
        hint = "The project has finished all stages."
    else:
        hint = f"The project status is {status}."
    return f"Received: {message.strip()}. {hint}"


async def stream_reply(text: str, *, delay: float) -> AsyncIterator[str]:
    for word in text.split(" "):
        yield sse("token", {"text": word + " "})
        await asyncio.sleep(delay)
    yield sse("done", {})
