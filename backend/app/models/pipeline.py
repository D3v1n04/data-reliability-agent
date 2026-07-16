from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

from typing import TYPE_CHECKING


class Pipeline(Base):
    __tablename__ = "pipelines"
    
    if TYPE_CHECKING:
        from backend.app.models.pipeline_run import PipelineRun

    __table_args__ = (
        UniqueConstraint(
            "name",
            name="uq_pipelines_name",
        ),
        CheckConstraint(
            "max_duration_seconds IS NULL "
            "OR max_duration_seconds > 0",
            name="ck_pipelines_max_duration_positive",
        ),
        CheckConstraint(
            "min_rows_processed IS NULL "
            "OR min_rows_processed >= 0",
            name="ck_pipelines_min_rows_nonnegative",
        ),
        CheckConstraint(
            "max_start_delay_seconds IS NULL "
            "OR max_start_delay_seconds >= 0",
            name="ck_pipelines_max_start_delay_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(),
        nullable=True,
    )

    max_duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    min_rows_processed: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    max_start_delay_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    runs: Mapped[list["PipelineRun"]] = relationship(
        back_populates="pipeline",
    )