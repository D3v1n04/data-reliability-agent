from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)

from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


if TYPE_CHECKING:
    from backend.app.models.pipeline import Pipeline


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    __table_args__ = (
        UniqueConstraint(
            "pipeline_id",
            "external_run_id",
            name="uq_pipeline_runs_pipeline_external_run",
        ),
        CheckConstraint(
            "status IN ('succeeded', 'failed', 'cancelled')",
            name="ck_pipeline_runs_status",
        ),
        CheckConstraint(
            "completed_at >= started_at",
            name="ck_pipeline_runs_valid_time_range",
        ),
        CheckConstraint(
            "rows_processed IS NULL OR rows_processed >= 0",
            name="ck_pipeline_runs_rows_nonnegative",
        ),
        CheckConstraint(
            "quality_checks_failed >= 0",
            name="ck_pipeline_runs_quality_checks_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    pipeline_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "pipelines.id",
            name="fk_pipeline_runs_pipeline_id_pipelines",
        ),
        nullable=False,
    )

    external_run_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    rows_processed: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    quality_checks_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    metrics: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::JSONB"),
    )

    error_message: Mapped[str | None] = mapped_column(
        String(),
        nullable=True,
    )

    logs: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::JSONB"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    pipeline: Mapped["Pipeline"] = relationship(
        back_populates="runs",
    )


Index(
    "ix_pipeline_runs_status",
    PipelineRun.status.asc().nulls_first(),
)

Index(
    "ix_pipeline_runs_completed_at",
    PipelineRun.completed_at.asc().nulls_first(),
)