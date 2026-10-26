"""One workspace directory per project: workspaces/<project-uuid>/.

Agents and tools get paths only through resolve_in_workspace, which refuses anything that would
land outside that project's directory (absolute paths, `..`, symlinks pointing elsewhere).
"""

import os
import uuid
from pathlib import Path

OVERRIDE_FILE = "agency.override.yaml"


class WorkspaceError(ValueError):
    pass


def workspaces_root() -> Path:
    return Path(os.environ.get("AGENCY_WORKSPACES_DIR", "workspaces")).resolve()


def _parse_id(project_id: uuid.UUID | str) -> uuid.UUID:
    try:
        return project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(project_id)
    except ValueError as exc:
        raise WorkspaceError(f"invalid project id {project_id!r}") from exc


def workspace_path(project_id: uuid.UUID | str, *, root: Path | None = None) -> Path:
    """The project's directory, created if missing. The id must be a UUID (no path injection)."""
    path = (root or workspaces_root()) / str(_parse_id(project_id))
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_in_workspace(
    project_id: uuid.UUID | str, relative: str, *, root: Path | None = None
) -> Path:
    """Resolve `relative` inside the project's workspace, or raise WorkspaceError."""
    base = workspace_path(project_id, root=root).resolve()
    if Path(relative).is_absolute():
        raise WorkspaceError(f"absolute paths are not allowed: {relative!r}")
    target = (base / relative).resolve()  # resolves symlinks, so a link out of the dir is caught
    if not target.is_relative_to(base):
        raise WorkspaceError(f"path escapes the project workspace: {relative!r}")
    return target


def override_path(project_id: uuid.UUID | str, *, root: Path | None = None) -> Path:
    """Where a project's agency.override.yaml lives (the file may not exist)."""
    return workspace_path(project_id, root=root) / OVERRIDE_FILE
