"""Every project-owned query goes through ProjectScope, which fixes the project_id once.

Methods never take a project_id argument, so code holding a scope for project A has no way to
read or write project B's rows. (There is no login in M0; this scoping is the isolation.)
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from agency.db.models import Approval, Event, LlmCall, Project, ProjectConfigSnapshot


class ProjectNotFound(Exception):
    pass


def list_projects(session: Session) -> list[Project]:
    """All projects (single owner). Everything inside a project goes through ProjectScope."""
    return list(session.scalars(select(Project).order_by(Project.created_at, Project.id)))


class ProjectScope:
    def __init__(self, session: Session, project_id: uuid.UUID) -> None:
        self.session = session
        self.project_id = project_id

    def project(self) -> Project:
        project = self.session.get(Project, self.project_id)
        if project is None:
            raise ProjectNotFound(str(self.project_id))
        return project

    def add_event(self, type: str, payload: dict[str, Any] | None = None) -> Event:
        event = Event(project_id=self.project_id, type=type, payload=payload or {})
        self.session.add(event)
        self.session.flush()
        return event

    def events(self) -> list[Event]:
        return list(
            self.session.scalars(
                select(Event).where(Event.project_id == self.project_id).order_by(Event.id)
            )
        )

    def add_approval(self, gate: str, decision: str, comment: str | None = None) -> Approval:
        approval = Approval(
            project_id=self.project_id, gate=gate, decision=decision, comment=comment
        )
        self.session.add(approval)
        self.session.flush()
        return approval

    def approvals(self) -> list[Approval]:
        return list(
            self.session.scalars(
                select(Approval).where(Approval.project_id == self.project_id).order_by(Approval.id)
            )
        )

    def llm_calls(self) -> list[LlmCall]:
        return list(
            self.session.scalars(
                select(LlmCall).where(LlmCall.project_id == self.project_id).order_by(LlmCall.id)
            )
        )

    def snapshots(self) -> list[ProjectConfigSnapshot]:
        return list(
            self.session.scalars(
                select(ProjectConfigSnapshot)
                .where(ProjectConfigSnapshot.project_id == self.project_id)
                .order_by(ProjectConfigSnapshot.version)
            )
        )
