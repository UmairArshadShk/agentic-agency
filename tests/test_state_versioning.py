import asyncio
import uuid
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import Engine

from agency.graphs.checkpointer import open_checkpointer
from agency.graphs.project_graph import build_graph, initial_state, thread_config
from agency.graphs.versioning import (
    MIGRATIONS,
    StateVersionError,
    migrate_state,
    resume_project,
)


def run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def old_state(pid: str, version: int = 0) -> dict[str, Any]:
    """State as an older build saved it: older version number and no `revisions` field yet."""
    state: dict[str, Any] = dict(initial_state(pid))
    state["graph_version"] = version
    del state["revisions"]
    return state


def add_revisions(values: Any) -> dict[str, Any]:
    return {"graph_version": 1, "revisions": 0}


async def pause_with(graph, state: dict[str, Any], pid: str):  # type: ignore[no-untyped-def]
    return await graph.ainvoke(state, thread_config(pid))


def test_no_migration_needed_when_versions_match() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    run(pause_with(graph, dict(initial_state(pid)), pid))
    assert run(migrate_state(graph, thread_config(pid), migrations={})) == (1, 1)


def test_old_state_is_migrated_then_resumes_to_the_end() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    run(pause_with(graph, old_state(pid), pid))
    assert run(graph.aget_state(thread_config(pid))).values["graph_version"] == 0

    result = run(
        resume_project(
            graph, thread_config(pid), {"decision": "approved"}, migrations={0: add_revisions}
        )
    )
    assert result["graph_version"] == 1
    assert result["revisions"] == 0
    assert result["stages"] == ["stub_a", "stub_b", "approval_gate", "stub_c"]


def test_migrated_state_is_saved_and_not_migrated_twice() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    run(pause_with(graph, old_state(pid), pid))
    config = thread_config(pid)
    assert run(migrate_state(graph, config, migrations={0: add_revisions})) == (0, 1)
    assert run(graph.aget_state(config)).values["graph_version"] == 1
    assert run(migrate_state(graph, config, migrations={0: add_revisions})) == (1, 1)


def test_migration_keeps_the_workflow_paused_at_the_gate() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    run(pause_with(graph, old_state(pid), pid))
    run(migrate_state(graph, thread_config(pid), migrations={0: add_revisions}))
    assert run(graph.aget_state(thread_config(pid))).next == ("approval_gate",)


def test_migration_after_a_changes_loop_still_resumes_at_the_gate() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    state = initial_state(pid)
    state["revisions"] = 0
    run(pause_with(graph, dict(state), pid))
    run(resume_project(graph, thread_config(pid), {"decision": "changes_requested"}))
    # Pretend the code deploys a new version while the project waits at the gate the second time.
    migrations = {1: lambda v: {"graph_version": 2}}
    run(migrate_state(graph, thread_config(pid), migrations=migrations, target_version=2))
    snapshot = run(graph.aget_state(thread_config(pid)))
    assert snapshot.values["graph_version"] == 2
    assert snapshot.next == ("approval_gate",)


def test_gap_in_the_migration_chain_is_an_error() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    run(pause_with(graph, old_state(pid, version=0), pid))
    with pytest.raises(StateVersionError, match="no migration from graph_version 0 to 1"):
        run(migrate_state(graph, thread_config(pid), migrations={}))


def test_migration_must_bump_the_version() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    run(pause_with(graph, old_state(pid), pid))
    with pytest.raises(StateVersionError, match="must set graph_version to 1"):
        run(migrate_state(graph, thread_config(pid), migrations={0: lambda v: {"revisions": 0}}))


def test_state_newer_than_the_code_is_refused() -> None:
    graph = build_graph(InMemorySaver())
    pid = str(uuid.uuid4())
    state = dict(initial_state(pid))
    state["graph_version"] = 99
    run(pause_with(graph, state, pid))
    with pytest.raises(StateVersionError, match="newer than this code"):
        run(migrate_state(graph, thread_config(pid), migrations={}))


def test_unknown_thread_is_an_error() -> None:
    graph = build_graph(InMemorySaver())
    with pytest.raises(StateVersionError, match="no saved state"):
        run(migrate_state(graph, thread_config(str(uuid.uuid4()))))


def test_shipped_migration_registry_covers_every_version_below_current() -> None:
    from agency.graphs.project_graph import GRAPH_VERSION

    assert all(v in MIGRATIONS for v in range(1, GRAPH_VERSION))


@pytest.mark.integration
def test_old_checkpoint_in_postgres_is_migrated_after_a_restart(migrated_engine: Engine) -> None:
    url = migrated_engine.url.render_as_string(hide_password=False)
    pid = str(uuid.uuid4())

    async def old_process() -> None:
        async with open_checkpointer(url) as saver:
            await pause_with(build_graph(saver), old_state(pid), pid)

    async def new_process() -> dict[str, Any]:
        async with open_checkpointer(url) as saver:
            return await resume_project(
                build_graph(saver),
                thread_config(pid),
                {"decision": "approved"},
                migrations={0: add_revisions},
            )

    run(old_process())
    result = run(new_process())
    assert result["graph_version"] == 1
    assert result["stages"][-1] == "stub_c"
