from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


Severity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["open", "investigating", "resolved"]


class IncidentCreate(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    severity: Severity = "medium"
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("detected_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("detected_at must include a timezone")

        return value


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pipeline_run_id: UUID | None
    source: str
    title: str
    description: str | None
    severity: Severity
    status: IncidentStatus
    detected_at: datetime
    resolved_at: datetime | None
    details: dict[str, object]
    created_at: datetime
    updated_at: datetime


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus