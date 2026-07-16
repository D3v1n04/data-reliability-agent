from datetime import datetime
from typing import Literal
from uuid import UUID

from backend.app.schemas.incident import IncidentRead, Severity

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


RunStatus = Literal[
    "succeeded",
    "failed",
    "cancelled",
]

RuleCode = Literal[
    "RUN_FAILED",
    "RUN_CANCELLED",
    "START_DELAY_EXCEEDED",
    "DURATION_EXCEEDED",
    "ROW_COUNT_BELOW_MINIMUM",
    "ROW_COUNT_MISSING",
    "QUALITY_CHECKS_FAILED",
]


class PipelineRunCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    external_run_id: str = Field(
        min_length=1,
        max_length=255,
    )
    status: RunStatus
    scheduled_at: datetime
    started_at: datetime
    completed_at: datetime
    rows_processed: int | None = Field(
        default=None,
        ge=0,
    )
    quality_checks_failed: int = Field(
        default=0,
        ge=0,
    )
    metrics: dict[str, object] = Field(
        default_factory=dict,
    )
    error_message: str | None = Field(
        default=None,
        max_length=10000,
    )
    logs: list[str] = Field(
        default_factory=list,
        max_length=100,
    )

    @field_validator(
        "scheduled_at",
        "started_at",
        "completed_at",
    )
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Pipeline run timestamps must include a timezone"
            )

        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> "PipelineRunCreate":
        if self.completed_at < self.started_at:
            raise ValueError(
                "completed_at cannot be earlier than started_at"
            )

        return self


class PipelineRunRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    pipeline_id: UUID
    external_run_id: str
    status: RunStatus
    scheduled_at: datetime
    started_at: datetime
    completed_at: datetime
    rows_processed: int | None
    quality_checks_failed: int
    metrics: dict[str, object]
    error_message: str | None
    logs: list[str]
    created_at: datetime

class RuleViolationRead(BaseModel):
    rule_code: RuleCode
    severity: Severity
    message: str
    actual: str | int | float | None = None
    threshold: str | int | float | None = None


class PipelineRunIngestResponse(BaseModel):
    run: PipelineRunRead
    incident: IncidentRead | None
    violations: list[RuleViolationRead]
    duplicate: bool