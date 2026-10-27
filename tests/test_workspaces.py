import uuid
from pathlib import Path

import pytest

from agency.workspaces import (
    WorkspaceError,
    override_path,
    resolve_in_workspace,
    workspace_path,
)


def test_each_project_gets_its_own_directory(tmp_path: Path) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    pa, pb = workspace_path(a, root=tmp_path), workspace_path(b, root=tmp_path)
    assert pa != pb and pa.is_dir() and pb.is_dir()
    assert pa.parent == pb.parent == tmp_path


def test_normal_relative_paths_resolve_inside_the_workspace(tmp_path: Path) -> None:
    pid = uuid.uuid4()
    path = resolve_in_workspace(pid, "designs/home.html", root=tmp_path)
    assert path == (workspace_path(pid, root=tmp_path) / "designs/home.html").resolve()


@pytest.mark.parametrize("relative", ["../x", "a/../../x", "..", "a/../.."])
def test_dotdot_escapes_are_refused(tmp_path: Path, relative: str) -> None:
    with pytest.raises(WorkspaceError, match="escapes"):
        resolve_in_workspace(uuid.uuid4(), relative, root=tmp_path)


def test_absolute_paths_are_refused(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="absolute"):
        resolve_in_workspace(uuid.uuid4(), "/etc/passwd", root=tmp_path)


def test_another_projects_directory_is_unreachable(tmp_path: Path) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    (workspace_path(b, root=tmp_path) / "requirements.md").write_text("secret of b")
    with pytest.raises(WorkspaceError, match="escapes"):
        resolve_in_workspace(a, f"../{b}/requirements.md", root=tmp_path)


def test_symlink_pointing_outside_is_refused(tmp_path: Path) -> None:
    pid = uuid.uuid4()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file.txt").write_text("host file")
    (workspace_path(pid, root=tmp_path) / "link").symlink_to(outside)
    with pytest.raises(WorkspaceError, match="escapes"):
        resolve_in_workspace(pid, "link/file.txt", root=tmp_path)


@pytest.mark.parametrize("bad_id", ["../x", "not-a-uuid", "", "a/b"])
def test_project_ids_must_be_uuids(tmp_path: Path, bad_id: str) -> None:
    with pytest.raises(WorkspaceError, match="invalid project id"):
        workspace_path(bad_id, root=tmp_path)


def test_override_file_lives_in_the_project_workspace(tmp_path: Path) -> None:
    pid = uuid.uuid4()
    assert override_path(pid, root=tmp_path) == workspace_path(pid, root=tmp_path) / (
        "agency.override.yaml"
    )
