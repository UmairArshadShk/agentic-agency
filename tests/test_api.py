import json
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agency.api.app import create_app
from agency.api.settings import Settings
from agency.config import ConfigError
from agency.config.snapshot import get_snapshot

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parent.parent


def settings_for(engine: Engine, tmp_path: Path, **overrides) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        config_path=ROOT / "config/agency.yaml",
        env={},
        workspaces_root=tmp_path,
        chat_token_delay=0,
        **overrides,
    )


@pytest.fixture
def client(migrated_engine: Engine, tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(settings_for(migrated_engine, tmp_path))) as c:
        yield c


def new_project(client: TestClient, name: str = "demo") -> dict:  # type: ignore[type-arg]
    response = client.post("/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def decide(client: TestClient, pid: str, decision: str, comment: str | None = None):  # type: ignore[no-untyped-def]
    return client.post(
        f"/projects/{pid}/approvals", json={"decision": decision, "comment": comment}
    )


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "graph_version": 1}


def test_create_project_runs_to_the_gate(
    client: TestClient, migrated_engine: Engine, tmp_path: Path
) -> None:
    project = new_project(client, "alpha")
    assert project["status"] == "awaiting_approval"
    assert project["stages"] == ["stub_a", "stub_b"]
    assert project["pending_gate"]["gate"] == "approval"
    assert (tmp_path / project["id"]).is_dir()

    with Session(migrated_engine) as session:
        snapshot = get_snapshot(session, uuid.UUID(project["id"]))
        assert snapshot is not None and snapshot.version == 1

    types = [e["type"] for e in client.get(f"/projects/{project['id']}/events").json()]
    assert types == ["project_created", "config_snapshot_created", "workflow_paused"]


def test_approving_completes_the_workflow(client: TestClient) -> None:
    pid = new_project(client)["id"]
    response = decide(client, pid, "approved", "looks good")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["stages"] == ["stub_a", "stub_b", "approval_gate", "stub_c"]
    assert body["pending_gate"] is None

    (approval,) = client.get(f"/projects/{pid}/approvals").json()
    assert (approval["gate"], approval["decision"], approval["comment"]) == (
        "approval",
        "approved",
        "looks good",
    )
    types = [e["type"] for e in client.get(f"/projects/{pid}/events").json()]
    assert types[-2:] == ["gate_decision", "workflow_completed"]


def test_request_changes_loops_then_approve_completes(client: TestClient) -> None:
    pid = new_project(client)["id"]
    body = decide(client, pid, "changes_requested", "bigger logo").json()
    assert body["status"] == "awaiting_approval"
    assert body["revisions"] == 1
    assert body["pending_gate"] is not None
    assert decide(client, pid, "approved").json()["status"] == "completed"
    decisions = [a["decision"] for a in client.get(f"/projects/{pid}/approvals").json()]
    assert decisions == ["changes_requested", "approved"]


def test_decision_when_not_at_a_gate_is_rejected(client: TestClient) -> None:
    pid = new_project(client)["id"]
    assert decide(client, pid, "approved").status_code == 201
    assert decide(client, pid, "approved").status_code == 409


def test_bad_requests(client: TestClient) -> None:
    pid = new_project(client)["id"]
    assert decide(client, pid, "maybe").status_code == 422
    assert decide(client, str(uuid.uuid4()), "approved").status_code == 404
    assert client.get(f"/projects/{uuid.uuid4()}").status_code == 404
    assert client.get("/projects/not-a-uuid").status_code == 422
    assert client.post("/projects", json={"name": ""}).status_code == 422


def test_two_simultaneous_approvals_only_resume_once(client: TestClient) -> None:
    pid = new_project(client)["id"]
    codes: list[int] = []

    def click() -> None:
        codes.append(decide(client, pid, "approved").status_code)

    threads = [threading.Thread(target=click) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [201, 409]
    assert len(client.get(f"/projects/{pid}/approvals").json()) == 1


def test_projects_are_isolated_from_each_other(client: TestClient, tmp_path: Path) -> None:
    a = new_project(client, "iso-a")["id"]
    b = new_project(client, "iso-b")["id"]
    assert a != b and (tmp_path / a).is_dir() and (tmp_path / b).is_dir()

    decide(client, a, "approved", "only for a")

    # Deciding on A did not touch B's workflow, events or approvals.
    state_b = client.get(f"/projects/{b}").json()
    assert state_b["status"] == "awaiting_approval" and state_b["pending_gate"] is not None
    assert client.get(f"/projects/{b}/approvals").json() == []
    events_b = client.get(f"/projects/{b}/events").json()
    assert all(e["type"] != "gate_decision" for e in events_b)
    events_a = client.get(f"/projects/{a}/events").json()
    assert all(e["payload"].get("name") != "iso-b" for e in events_a)
    (approval_a,) = client.get(f"/projects/{a}/approvals").json()
    assert approval_a["comment"] == "only for a"

    # B can still be decided independently.
    assert decide(client, b, "approved").json()["status"] == "completed"


def test_ids_that_look_like_paths_are_not_projects(client: TestClient) -> None:
    for bad in ("..", "%2e%2e%2fetc", "..%2F..%2Fetc%2Fpasswd"):
        assert client.get(f"/projects/{bad}").status_code in (404, 422)
    assert client.get("/projects/../../etc/passwd").status_code == 404


def test_list_projects(client: TestClient) -> None:
    pid = new_project(client, "listed")["id"]
    assert pid in [p["id"] for p in client.get("/projects").json()]


def parse_sse(raw: str) -> list[tuple[str, dict]]:  # type: ignore[type-arg]
    events = []
    for block in raw.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_chat_streams_tokens_then_done(client: TestClient) -> None:
    pid = new_project(client)["id"]
    with client.stream("POST", f"/projects/{pid}/chat", json={"message": "hello there"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = parse_sse("".join(r.iter_text()))
    assert events[-1] == ("done", {})
    tokens = [data["text"] for name, data in events if name == "token"]
    assert len(tokens) > 3  # streamed in pieces, not one blob
    full = "".join(tokens)
    assert "hello there" in full and "approval gate" in full


def test_chat_validation_and_unknown_project(client: TestClient) -> None:
    pid = new_project(client)["id"]
    assert client.post(f"/projects/{pid}/chat", json={"message": ""}).status_code == 422
    assert client.post(f"/projects/{uuid.uuid4()}/chat", json={"message": "hi"}).status_code == 404


def test_paused_project_resumes_after_the_server_restarts(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    settings = settings_for(migrated_engine, tmp_path)
    with TestClient(create_app(settings)) as first:
        pid = new_project(first, "restart")["id"]
    # The first app, its connection pool and its compiled graph are gone.
    with TestClient(create_app(settings)) as second:
        state = second.get(f"/projects/{pid}").json()
        assert state["status"] == "awaiting_approval" and state["pending_gate"] is not None
        body = decide(second, pid, "approved").json()
    assert body["status"] == "completed"
    assert body["stages"] == ["stub_a", "stub_b", "approval_gate", "stub_c"]


def test_server_refuses_to_start_with_an_invalid_config(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    bad = tmp_path / "agency.yaml"
    bad.write_text((ROOT / "config/agency.yaml").read_text().replace("count: 1", "count: 2", 1))
    settings = Settings(
        database_url=migrated_engine.url.render_as_string(hide_password=False),
        config_path=bad,
        env={},
        workspaces_root=tmp_path,
    )
    with (
        pytest.raises(ConfigError, match="agents.pm.count must be 1"),
        TestClient(create_app(settings)),
    ):
        pass
