"""State versioning: upgrade a paused project's saved state before it resumes.

Every checkpoint stores `graph_version`. When the code's GRAPH_VERSION moves on (a field added,
a stage renamed), each step in MIGRATIONS upgrades saved state from version N to N+1. Resuming
runs the chain first, so projects paused under old code keep working after a deploy.
"""

from collections.abc import Callable, Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from agency.graphs.project_graph import GRAPH_VERSION

# A migration takes the saved state values and returns the keys to change. It must set
# "graph_version" to the next version. Fields with a reducer (e.g. `stages`) are appended to.
Migration = Callable[[Mapping[str, Any]], dict[str, Any]]

MIGRATIONS: dict[int, Migration] = {}


class StateVersionError(Exception):
    pass


async def migrate_state(
    graph: CompiledStateGraph[Any, Any, Any, Any],
    config: RunnableConfig,
    *,
    migrations: Mapping[int, Migration] | None = None,
    target_version: int = GRAPH_VERSION,
) -> tuple[int, int]:
    """Bring the saved state to target_version. Returns (version before, version after)."""
    registry = MIGRATIONS if migrations is None else migrations
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise StateVersionError("no saved state for this thread")

    values = dict(snapshot.values)
    start = version = values.get("graph_version", 0)
    if version > target_version:
        raise StateVersionError(
            f"saved state is version {version}, newer than this code (version {target_version})"
        )

    merged = dict(values)
    update: dict[str, Any] = {}
    while version < target_version:
        step = registry.get(version)
        if step is None:
            raise StateVersionError(f"no migration from graph_version {version} to {version + 1}")
        changes = step(merged)
        if changes.get("graph_version") != version + 1:
            raise StateVersionError(f"migration {version} must set graph_version to {version + 1}")
        merged.update(changes)
        update.update(changes)
        version += 1

    if update:
        await graph.aupdate_state(config, update)
    return start, version


async def resume_project(
    graph: CompiledStateGraph[Any, Any, Any, Any],
    config: RunnableConfig,
    resume_value: Any,
    **migrate_kwargs: Any,
) -> dict[str, Any]:
    """Migrate the saved state if needed, then resume the paused workflow with the answer."""
    await migrate_state(graph, config, **migrate_kwargs)
    return await graph.ainvoke(Command(resume=resume_value), config)
