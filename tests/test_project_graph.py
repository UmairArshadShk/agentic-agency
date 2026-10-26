import asyncio
import uuid

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import Engine

from agency.graphs.checkpointer import libpq_url, open_checkpointer
from agency.graphs.project_graph import (
    GRAPH_VERSION,
    build_graph,
    initial_state,
    pending_interrupt,
    thread_config,
)


def run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


async def start_and_pause(graph, project_id: str):  # type: ignore[no-untyped-def]
    return await graph.ainvoke(initial_state(project_id), thread_config(project_id))


def test_runs_stages_in_order_and_pauses_at_the_gate() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    result = run(start_and_pause(graph, pid))
    assert result["stages"] == ["stub_a", "stub_b"]  # stub_c has not run
    assert pending_interrupt(result) == {"gate": "approval", "project_id": pid}
    assert result["graph_version"] == GRAPH_VERSION


def test_approval_resumes_to_the_end() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    run(start_and_pause(graph, pid))
    result = run(graph.ainvoke(Command(resume={"decision": "approved"}), thread_config(pid)))
    assert result["stages"] == ["stub_a", "stub_b", "approval_gate", "stub_c"]
    assert pending_interrupt(result) is None
    assert result["decision"] == "approved"


def test_changes_requested_loops_back_and_pauses_again() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    run(start_and_pause(graph, pid))
    result = run(
        graph.ainvoke(
            Command(resume={"decision": "changes_requested", "comment": "bigger logo"}),
            thread_config(pid),
        )
    )
    assert result["stages"] == ["stub_a", "stub_b", "approval_gate", "stub_b"]
    assert result["revisions"] == 1
    assert result["comment"] == "bigger logo"
    assert pending_interrupt(result) is not None  # waiting at the gate again

    result = run(graph.ainvoke(Command(resume={"decision": "approved"}), thread_config(pid)))
    assert result["stages"][-1] == "stub_c"


def test_invalid_decision_is_rejected() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    run(start_and_pause(graph, pid))
    with pytest.raises(ValueError, match="gate decision must be one of"):
        run(graph.ainvoke(Command(resume={"decision": "maybe"}), thread_config(pid)))


def test_projects_have_separate_threads() -> None:
    graph = build_graph(InMemorySaver())
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    run(start_and_pause(graph, a))
    run(start_and_pause(graph, b))
    run(graph.ainvoke(Command(resume={"decision": "approved"}), thread_config(a)))
    state_b = run(graph.aget_state(thread_config(b)))
    assert state_b.next == ("approval_gate",)  # b is still paused


def test_libpq_url_strips_the_driver_suffix() -> None:
    assert libpq_url("postgresql+psycopg://u:p@h:5/d") == "postgresql://u:p@h:5/d"
    assert libpq_url("postgresql://u:p@h:5/d") == "postgresql://u:p@h:5/d"


@pytest.mark.integration
def test_pause_survives_a_restart_with_the_postgres_checkpointer(migrated_engine: Engine) -> None:
    url = migrated_engine.url.render_as_string(hide_password=False)
    pid = str(uuid.uuid4())

    async def first_process() -> None:
        async with open_checkpointer(url) as saver:
            result = await start_and_pause(build_graph(saver), pid)
            assert pending_interrupt(result) is not None

    async def second_process() -> dict:  # type: ignore[type-arg]
        # New pool, new saver, new compiled graph: nothing is carried over in memory.
        async with open_checkpointer(url) as saver:
            graph = build_graph(saver)
            state = await graph.aget_state(thread_config(pid))
            assert state.next == ("approval_gate",)
            return await graph.ainvoke(Command(resume={"decision": "approved"}), thread_config(pid))

    run(first_process())
    result = run(second_process())
    # stub_a and stub_b ran once, in the first process, and were not repeated after the restart.
    assert result["stages"] == ["stub_a", "stub_b", "approval_gate", "stub_c"]
    assert result["decision"] == "approved"
