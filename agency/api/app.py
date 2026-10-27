"""FastAPI app: projects, approvals, audit trail and chat streaming.

No login in M0 (docs/DECISIONS.md): every route is scoped by the project id in its path and goes
through ProjectScope, and the server binds to localhost by default.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from agency.api.chat import stream_reply, stub_reply
from agency.api.schemas import (
    ApprovalIn,
    ApprovalOut,
    ChatIn,
    EventOut,
    ProjectCreate,
    ProjectOut,
)
from agency.api.settings import Settings, load_settings
from agency.config import ConfigError, load_config
from agency.config.snapshot import create_snapshot
from agency.db.models import Project
from agency.db.scoped import ProjectNotFound, ProjectScope, list_projects
from agency.db.session import make_engine
from agency.graphs.checkpointer import open_checkpointer
from agency.graphs.project_graph import (
    GRAPH_VERSION,
    build_graph,
    initial_state,
    pending_gate,
    thread_config,
)
from agency.graphs.versioning import resume_project
from agency.workspaces import workspace_path

log = logging.getLogger(__name__)

OWNER = "owner"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Fail fast: refuse to start on an invalid config (invariant 3).
        load_config(settings.config_path, env=settings.env, base_dir=settings.base_dir)
        engine = make_engine(settings.database_url)
        async with open_checkpointer(settings.database_url) as saver:
            app.state.engine = engine
            app.state.graph = build_graph(saver)
            app.state.locks = {}
            yield
        engine.dispose()

    app = FastAPI(title="AI Agents Agency", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def engine_of(request: Request) -> Engine:
        return request.app.state.engine

    def graph_of(request: Request) -> CompiledStateGraph[Any, Any, Any, Any]:
        return request.app.state.graph

    def lock_for(request: Request, project_id: uuid.UUID) -> asyncio.Lock:
        # One resume at a time per project, so two clicks cannot resume the same gate twice.
        return request.app.state.locks.setdefault(project_id, asyncio.Lock())

    def require_project(session: Session, project_id: uuid.UUID) -> Project:
        try:
            return ProjectScope(session, project_id).project()
        except ProjectNotFound:
            raise HTTPException(404, "project not found") from None

    async def project_out(request: Request, project: Project) -> ProjectOut:
        snapshot = await graph_of(request).aget_state(thread_config(str(project.id)))
        values = snapshot.values or {}
        return ProjectOut(
            id=project.id,
            name=project.name,
            status=project.status,
            graph_version=project.graph_version,
            created_at=project.created_at,
            stages=values.get("stages", []),
            revisions=values.get("revisions", 0),
            pending_gate=pending_gate(snapshot),
        )

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        try:
            with engine_of(request).connect() as conn:
                conn.execute(text("select 1"))
        except Exception:
            raise HTTPException(503, "database unavailable") from None
        return {"status": "ok", "graph_version": GRAPH_VERSION}

    @app.post("/projects", status_code=201)
    async def create_project(body: ProjectCreate, request: Request) -> ProjectOut:
        try:
            cfg = load_config(settings.config_path, env=settings.env, base_dir=settings.base_dir)
        except ConfigError as exc:
            raise HTTPException(500, {"message": "invalid config", "errors": exc.errors}) from exc

        engine = engine_of(request)
        with Session(engine) as session:
            project = Project(name=body.name, owner=OWNER, graph_version=GRAPH_VERSION)
            session.add(project)
            session.flush()
            scope = ProjectScope(session, project.id)
            workspace_path(project.id, root=settings.workspaces_root)
            scope.add_event("project_created", {"name": body.name})
            create_snapshot(session, project.id, cfg, applied_by=OWNER, reason="project start")
            session.commit()
            project_id = project.id

        try:
            result = await graph_of(request).ainvoke(
                initial_state(str(project_id)), thread_config(str(project_id))
            )
        except Exception as exc:
            log.exception("workflow failed to start for project %s", project_id)
            with Session(engine) as session:
                ProjectScope(session, project_id).add_event("workflow_error", {"error": str(exc)})
                require_project(session, project_id).status = "error"
                session.commit()
            raise HTTPException(500, "workflow failed to start") from exc

        with Session(engine) as session:
            project = require_project(session, project_id)
            project.status = "awaiting_approval" if result.get("__interrupt__") else "completed"
            ProjectScope(session, project_id).add_event(
                "workflow_paused" if result.get("__interrupt__") else "workflow_completed",
                {"stages": result["stages"]},
            )
            session.commit()
            session.refresh(project)
            return await project_out(request, project)

    @app.get("/projects")
    async def get_projects(request: Request) -> list[ProjectOut]:
        with Session(engine_of(request)) as session:
            return [await project_out(request, p) for p in list_projects(session)]

    @app.get("/projects/{project_id}")
    async def get_project(project_id: uuid.UUID, request: Request) -> ProjectOut:
        with Session(engine_of(request)) as session:
            return await project_out(request, require_project(session, project_id))

    @app.get("/projects/{project_id}/events")
    def get_events(project_id: uuid.UUID, request: Request) -> list[EventOut]:
        with Session(engine_of(request)) as session:
            require_project(session, project_id)
            return [
                EventOut(id=e.id, type=e.type, payload=e.payload, created_at=e.created_at)
                for e in ProjectScope(session, project_id).events()
            ]

    @app.get("/projects/{project_id}/approvals")
    def get_approvals(project_id: uuid.UUID, request: Request) -> list[ApprovalOut]:
        with Session(engine_of(request)) as session:
            require_project(session, project_id)
            return [
                ApprovalOut(
                    id=a.id,
                    gate=a.gate,
                    decision=a.decision,
                    comment=a.comment,
                    decided_at=a.decided_at,
                )
                for a in ProjectScope(session, project_id).approvals()
            ]

    @app.post("/projects/{project_id}/approvals", status_code=201)
    async def decide(project_id: uuid.UUID, body: ApprovalIn, request: Request) -> ProjectOut:
        engine = engine_of(request)
        graph = graph_of(request)
        config = thread_config(str(project_id))
        with Session(engine) as session:
            require_project(session, project_id)

        async with lock_for(request, project_id):
            gate = pending_gate(await graph.aget_state(config))
            if gate is None:
                raise HTTPException(409, "project is not waiting at a gate")

            migrated: list[tuple[int, int]] = []
            result = await resume_project(
                graph,
                config,
                {"decision": body.decision, "comment": body.comment},
                on_migrate=lambda before, after: migrated.append((before, after)),
            )

            with Session(engine) as session:
                project = require_project(session, project_id)
                scope = ProjectScope(session, project_id)
                for before, after in migrated:
                    scope.add_event("state_migrated", {"from": before, "to": after})
                    project.graph_version = after
                scope.add_approval(gate["gate"], body.decision, body.comment)
                scope.add_event("gate_decision", {"gate": gate["gate"], "decision": body.decision})
                waiting = bool(result.get("__interrupt__"))
                project.status = "awaiting_approval" if waiting else "completed"
                scope.add_event(
                    "workflow_paused" if waiting else "workflow_completed",
                    {"stages": result["stages"]},
                )
                session.commit()
                session.refresh(project)
                return await project_out(request, project)

    @app.post("/projects/{project_id}/chat")
    async def chat(project_id: uuid.UUID, body: ChatIn, request: Request) -> StreamingResponse:
        with Session(engine_of(request)) as session:
            project = require_project(session, project_id)
            out = await project_out(request, project)
        text_reply = stub_reply(body.message, out.status, out.pending_gate is not None)
        return StreamingResponse(
            stream_reply(text_reply, delay=settings.chat_token_delay),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
