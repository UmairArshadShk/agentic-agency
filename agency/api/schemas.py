import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    graph_version: int
    created_at: datetime
    stages: list[str] = []
    revisions: int = 0
    pending_gate: dict[str, Any] | None = None


class ApprovalIn(BaseModel):
    decision: Literal["approved", "changes_requested"]
    comment: str | None = Field(default=None, max_length=4000)


class ApprovalOut(BaseModel):
    id: int
    gate: str
    decision: str
    comment: str | None
    decided_at: datetime


class EventOut(BaseModel):
    id: int
    type: str
    payload: dict[str, Any]
    created_at: datetime


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
