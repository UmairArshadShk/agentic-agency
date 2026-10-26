"""Versioned, immutable per-project config snapshots (rows are protected by a DB trigger)."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agency.config.schema import AgencyConfig
from agency.db.models import Event, ProjectConfigSnapshot


def create_snapshot(
    session: Session,
    project_id: uuid.UUID,
    cfg: AgencyConfig,
    *,
    applied_by: str,
    reason: str,
) -> ProjectConfigSnapshot:
    """Save cfg as the next snapshot version for the project and log it in events."""
    current = session.scalar(
        select(func.max(ProjectConfigSnapshot.version)).where(
            ProjectConfigSnapshot.project_id == project_id
        )
    )
    snapshot = ProjectConfigSnapshot(
        project_id=project_id,
        version=(current or 0) + 1,
        effective_config=cfg.model_dump(mode="json"),
        applied_by=applied_by,
        reason=reason,
    )
    session.add(snapshot)
    session.add(
        Event(
            project_id=project_id,
            type="config_snapshot_created",
            payload={"version": snapshot.version, "applied_by": applied_by, "reason": reason},
        )
    )
    session.flush()
    return snapshot


def get_snapshot(
    session: Session, project_id: uuid.UUID, version: int | None = None
) -> ProjectConfigSnapshot | None:
    """The given version, or the latest when version is None. Always scoped by project_id."""
    query = select(ProjectConfigSnapshot).where(ProjectConfigSnapshot.project_id == project_id)
    if version is not None:
        query = query.where(ProjectConfigSnapshot.version == version)
    else:
        query = query.order_by(ProjectConfigSnapshot.version.desc()).limit(1)
    return session.scalars(query).first()


def snapshot_config(snapshot: ProjectConfigSnapshot) -> AgencyConfig:
    effective: dict[str, Any] = snapshot.effective_config
    return AgencyConfig.model_validate(effective)
