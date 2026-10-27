"""Project graph stub: three dummy stages and one human gate.

The workflow is deterministic code: this module decides which stage runs next, never an agent.
The gate uses LangGraph `interrupt`, so with the Postgres checkpointer a paused project survives a
server restart and resumes where it stopped. Real stages replace the stubs in later milestones.
"""

import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot, interrupt

GRAPH_VERSION = 1
DECISIONS = ("approved", "changes_requested")


class ProjectState(TypedDict):
    project_id: str
    graph_version: int
    stages: Annotated[list[str], operator.add]  # audit trail of stages that ran, in order
    revisions: int  # how many times the client asked for changes at the gate
    decision: str | None
    comment: str | None


def initial_state(project_id: str) -> ProjectState:
    return {
        "project_id": project_id,
        "graph_version": GRAPH_VERSION,
        "stages": [],
        "revisions": 0,
        "decision": None,
        "comment": None,
    }


def thread_config(project_id: str) -> RunnableConfig:
    """One graph thread per project."""
    return {"configurable": {"thread_id": f"project-{project_id}"}}


def stub_a(state: ProjectState) -> dict[str, Any]:
    return {"stages": ["stub_a"]}


def stub_b(state: ProjectState) -> dict[str, Any]:
    return {"stages": ["stub_b"]}


def approval_gate(state: ProjectState) -> dict[str, Any]:
    # On resume this node restarts from the top, so nothing with side effects goes before interrupt.
    answer = interrupt({"gate": "approval", "project_id": state["project_id"]})
    decision = answer.get("decision")
    if decision not in DECISIONS:
        raise ValueError(f"gate decision must be one of {DECISIONS}, got {decision!r}")
    update: dict[str, Any] = {
        "stages": ["approval_gate"],
        "decision": decision,
        "comment": answer.get("comment"),
    }
    if decision == "changes_requested":
        update["revisions"] = state["revisions"] + 1
    return update


def stub_c(state: ProjectState) -> dict[str, Any]:
    return {"stages": ["stub_c"]}


def after_gate(state: ProjectState) -> Literal["stub_b", "stub_c"]:
    return "stub_c" if state["decision"] == "approved" else "stub_b"


def build_graph(checkpointer: BaseCheckpointSaver[Any]) -> CompiledStateGraph[Any, Any, Any, Any]:
    builder = StateGraph(ProjectState)
    builder.add_node("stub_a", stub_a)
    builder.add_node("stub_b", stub_b)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("stub_c", stub_c)
    builder.add_edge(START, "stub_a")
    builder.add_edge("stub_a", "stub_b")
    builder.add_edge("stub_b", "approval_gate")
    builder.add_conditional_edges("approval_gate", after_gate)
    builder.add_edge("stub_c", END)
    return builder.compile(checkpointer=checkpointer)


def pending_interrupt(result: dict[str, Any]) -> dict[str, Any] | None:
    """The payload the workflow is waiting on, or None if it ran to the end."""
    interrupts = result.get("__interrupt__")
    return interrupts[0].value if interrupts else None


def pending_gate(snapshot: StateSnapshot) -> dict[str, Any] | None:
    """The gate payload a saved (paused) workflow is waiting on, or None."""
    return snapshot.interrupts[0].value if snapshot.interrupts else None
