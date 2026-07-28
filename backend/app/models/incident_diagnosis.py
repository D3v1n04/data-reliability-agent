from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class IncidentDiagnosis(Base):
    __tablename__ = "incident_diagnoses"
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            name="uq_incident_diagnoses_incident_id",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_incident_diagnoses_confidence_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    incident_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("incidents.id"),
        nullable=False,
    )

    explanation: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    likely_causes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
    )

    recommendations: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    text_model_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
