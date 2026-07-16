from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PipelineCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    name: str = Field(
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )
    max_duration_seconds: int | None = Field(
        default=None,
        gt=0,
    )
    min_rows_processed: int | None = Field(
        default=None,
        ge=0,
    )
    max_start_delay_seconds: int | None = Field(
        default=None,
        ge=0,
    )
    enabled: bool = True


class PipelineRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    name: str
    description: str | None
    max_duration_seconds: int | None
    min_rows_processed: int | None
    max_start_delay_seconds: int | None
    enabled: bool
    created_at: datetime
    updated_at: datetime