from pathlib import Path

import pytest
import yaml
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from agency.config import load_config
from agency.config.snapshot import create_snapshot, get_snapshot, snapshot_config
from agency.db.models import Event, Project

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parent.parent


def test_editing_agency_yaml_does_not_change_a_started_project(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    path = tmp_path / "agency.yaml"
    raw = yaml.safe_load((ROOT / "config/agency.yaml").read_text())
    path.write_text(yaml.safe_dump(raw))
    original = load_config(path, base_dir=ROOT, env={})

    with Session(migrated_engine) as session:
        project = Project(name="p", owner="o")
        session.add(project)
        session.flush()
        create_snapshot(session, project.id, original, applied_by="system", reason="project start")
        session.commit()
        project_id = project.id

    # The owner edits agency.yaml after the project started.
    raw["agents"]["pm"]["model"] = "ollama:qwen3:4b"
    raw["agents"]["pm"]["system_prompt_append"] = "changed"
    path.write_text(yaml.safe_dump(raw))
    edited = load_config(path, base_dir=ROOT, env={})
    assert edited.agents.pm.model == "ollama:qwen3:4b"

    with Session(migrated_engine) as session:
        snapshot = get_snapshot(session, project_id)
        assert snapshot is not None
        effective = snapshot_config(snapshot)
        assert effective.agents.pm.model is None  # still inherits defaults.model
        assert effective.agents.pm.system_prompt_append == ""
        assert effective == original


def test_applying_a_change_creates_a_new_version_and_logs_an_event(
    migrated_engine: Engine,
) -> None:
    cfg = load_config(ROOT / "config/agency.yaml", base_dir=ROOT, env={})
    with Session(migrated_engine) as session:
        project = Project(name="p2", owner="o")
        session.add(project)
        session.flush()
        first = create_snapshot(session, project.id, cfg, applied_by="system", reason="start")
        second = create_snapshot(session, project.id, cfg, applied_by="owner", reason="tuning")
        session.commit()
        assert (first.version, second.version) == (1, 2)
        latest = get_snapshot(session, project.id)
        assert latest is not None and latest.version == 2
        old = get_snapshot(session, project.id, version=1)
        assert old is not None and old.reason == "start"
        events = session.scalars(
            select(Event).where(
                Event.project_id == project.id, Event.type == "config_snapshot_created"
            )
        ).all()
        assert [e.payload["version"] for e in events] == [1, 2]


def test_snapshots_are_scoped_to_their_project(migrated_engine: Engine) -> None:
    cfg = load_config(ROOT / "config/agency.yaml", base_dir=ROOT, env={})
    with Session(migrated_engine) as session:
        a, b = Project(name="a", owner="o"), Project(name="b", owner="o")
        session.add_all([a, b])
        session.flush()
        create_snapshot(session, a.id, cfg, applied_by="system", reason="start")
        session.commit()
        assert get_snapshot(session, b.id) is None
