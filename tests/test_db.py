import uuid
from decimal import Decimal

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from agency.db.models import Approval, Event, LlmCall, Project, ProjectConfigSnapshot

pytestmark = pytest.mark.integration


def _project(session: Session) -> Project:
    project = Project(name="demo", owner="owner")
    session.add(project)
    session.flush()
    return project


def test_expected_tables_exist(migrated_engine: Engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"projects", "project_config_snapshots", "llm_calls", "events", "approvals"} <= tables


def test_project_defaults(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        project = _project(session)
        session.commit()
        assert project.status == "created"
        assert project.graph_version == 1
        assert project.created_at is not None


def test_llm_call_records_cost_fields(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        project = _project(session)
        session.add(
            LlmCall(
                project_id=project.id,
                agent="pm",
                model="ollama:llama3.1:8b",
                tokens_in=10,
                tokens_out=5,
                cost=Decimal("0"),
                config_version=1,
            )
        )
        session.commit()
        row = session.query(LlmCall).filter_by(project_id=project.id).one()
        assert (row.agent, row.model, row.config_version) == ("pm", "ollama:llama3.1:8b", 1)


def test_rows_require_an_existing_project(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        session.add(Approval(project_id=uuid.uuid4(), gate="design", decision="approved"))
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize("statement", ["UPDATE events SET type = 'x'", "DELETE FROM events"])
def test_events_are_append_only(migrated_engine: Engine, statement: str) -> None:
    with Session(migrated_engine) as session:
        project = _project(session)
        session.add(Event(project_id=project.id, type="started", payload={}))
        session.commit()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))


@pytest.mark.parametrize(
    "statement",
    ["UPDATE project_config_snapshots SET reason = 'x'", "DELETE FROM project_config_snapshots"],
)
def test_snapshots_are_immutable(migrated_engine: Engine, statement: str) -> None:
    with Session(migrated_engine) as session:
        project = _project(session)
        session.add(
            ProjectConfigSnapshot(
                project_id=project.id,
                version=1,
                effective_config={"version": 1},
                applied_by="system",
                reason="project start",
            )
        )
        session.commit()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))


def test_snapshot_version_is_unique_per_project(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        project = _project(session)
        for _ in range(2):
            session.add(
                ProjectConfigSnapshot(
                    project_id=project.id,
                    version=1,
                    effective_config={},
                    applied_by="system",
                    reason="dup",
                )
            )
        with pytest.raises(IntegrityError):
            session.commit()
