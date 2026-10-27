import uuid
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agency.config import load_config
from agency.config.snapshot import create_snapshot
from agency.db.models import LlmCall, Project
from agency.db.scoped import ProjectNotFound, ProjectScope, list_projects

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parent.parent


def make_project(session: Session, name: str) -> Project:
    project = Project(name=name, owner="o")
    session.add(project)
    session.flush()
    return project


def populate(session: Session, project: Project) -> None:
    scope = ProjectScope(session, project.id)
    scope.add_event("started", {"who": project.name})
    scope.add_approval("design", "approved", f"ok from {project.name}")
    session.add(
        LlmCall(
            project_id=project.id,
            agent="pm-1",
            model="ollama:llama3.1:8b",
            config_version=1,
        )
    )
    cfg = load_config(ROOT / "config/agency.yaml", base_dir=ROOT, env={})
    create_snapshot(session, project.id, cfg, applied_by="system", reason=project.name)


def test_a_scope_only_sees_its_own_projects_rows(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        a, b = make_project(session, "iso-a"), make_project(session, "iso-b")
        populate(session, a)
        populate(session, b)
        session.commit()

        for owner, other in ((a, b), (b, a)):
            scope = ProjectScope(session, owner.id)
            started = [e for e in scope.events() if e.type == "started"]
            assert [e.payload["who"] for e in started] == [owner.name]
            assert [x.comment for x in scope.approvals()] == [f"ok from {owner.name}"]
            assert len(scope.llm_calls()) == 1
            assert [s.reason for s in scope.snapshots()] == [owner.name]
            everything = [
                *scope.events(),
                *scope.approvals(),
                *scope.llm_calls(),
                *scope.snapshots(),
            ]
            assert all(row.project_id == owner.id != other.id for row in everything)


def test_writes_through_a_scope_land_in_that_project_only(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        a, b = make_project(session, "w-a"), make_project(session, "w-b")
        ProjectScope(session, a.id).add_event("only-a")
        session.commit()
        assert [e.type for e in ProjectScope(session, a.id).events()] == ["only-a"]
        assert ProjectScope(session, b.id).events() == []


def test_unknown_project_is_not_found(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session, pytest.raises(ProjectNotFound):
        ProjectScope(session, uuid.uuid4()).project()


def test_list_projects_returns_all_projects(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        made = {make_project(session, "list-1").id, make_project(session, "list-2").id}
        session.commit()
        assert made <= {p.id for p in list_projects(session)}
