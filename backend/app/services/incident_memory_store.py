import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.models import (
    Incident,
    IncidentMemory,
    Pipeline,
    PipelineRun,
)
from backend.app.services.bedrock import BedrockService
from backend.app.services.incident_memory import (
    build_embedding_input,
    build_incident_snapshot,
)


class IncidentMemoryStoreError(RuntimeError):
    """Raised when incident memory cannot be stored or retrieved."""


@dataclass(frozen=True)
class SimilarIncidentMemory:
    """A prior incident memory ranked by semantic similarity."""

    incident_id: UUID
    distance: float
    similarity: float
    incident_snapshot: dict[str, Any]


def _validate_embedding(
    embedding: list[float],
    expected_dimensions: int,
) -> None:
    """Validate an embedding before database use."""
    if len(embedding) != expected_dimensions:
        raise ValueError(
            "Embedding dimensions do not match configuration"
        )

    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in embedding
    ):
        raise ValueError("Embedding contains invalid values")


def get_or_create_incident_memory(
    db: Session,
    incident: Incident,
    pipeline_run: PipelineRun,
    pipeline: Pipeline,
    bedrock_service: BedrockService,
    settings: Settings | None = None,
) -> IncidentMemory:
    """Create immutable incident memory once per incident."""
    resolved_settings = settings or get_settings()

    existing_query = select(IncidentMemory).where(
        IncidentMemory.incident_id == incident.id
    )

    try:
        existing_memory = db.scalar(existing_query)
    except SQLAlchemyError as exc:
        raise IncidentMemoryStoreError(
            "Unable to retrieve existing incident memory"
        ) from exc

    if existing_memory is not None:
        return existing_memory

    snapshot = build_incident_snapshot(
        incident,
        pipeline_run,
        pipeline,
    )
    embedding_input = build_embedding_input(snapshot)

    embedding = bedrock_service.generate_embedding(
        embedding_input
    )

    _validate_embedding(
        embedding,
        resolved_settings.bedrock_embedding_dimensions,
    )

    memory = IncidentMemory(
        incident_id=incident.id,
        incident_snapshot=snapshot,
        embedding_input=embedding_input,
        embedding=embedding,
        embedding_model_id=(
            resolved_settings.bedrock_embedding_model_id
        ),
    )

    try:
        with db.begin_nested():
            db.add(memory)
            db.flush()
    except IntegrityError as exc:
        # Another request may have created the same memory
        # after our initial existence check.
        try:
            existing_memory = db.scalar(existing_query)
        except SQLAlchemyError as retrieval_exc:
            raise IncidentMemoryStoreError(
                "Unable to recover concurrent incident memory"
            ) from retrieval_exc

        if existing_memory is not None:
            return existing_memory

        raise IncidentMemoryStoreError(
            "Unable to create incident memory"
        ) from exc
    except SQLAlchemyError as exc:
        raise IncidentMemoryStoreError(
            "Unable to create incident memory"
        ) from exc

    return memory


def find_similar_incident_memories(
    db: Session,
    embedding: list[float],
    exclude_incident_id: UUID,
    limit: int | None = None,
    settings: Settings | None = None,
) -> list[SimilarIncidentMemory]:
    """Retrieve prior memories using cosine distance."""
    resolved_settings = settings or get_settings()
    resolved_limit = (
        limit
        if limit is not None
        else resolved_settings.similar_incident_limit
    )

    if not 1 <= resolved_limit <= 20:
        raise ValueError(
            "Similar incident limit must be between 1 and 20"
        )

    _validate_embedding(
        embedding,
        resolved_settings.bedrock_embedding_dimensions,
    )

    distance = IncidentMemory.embedding.cosine_distance(
        embedding
    ).label("distance")

    query = (
        select(
            IncidentMemory,
            distance,
        )
        .where(
            IncidentMemory.incident_id != exclude_incident_id
        )
        .order_by(distance)
        .limit(resolved_limit)
    )

    try:
        rows = db.execute(query).all()
    except SQLAlchemyError as exc:
        raise IncidentMemoryStoreError(
            "Unable to retrieve similar incident memories"
        ) from exc

    similar_memories: list[SimilarIncidentMemory] = []

    for memory, raw_distance in rows:
        distance_value = float(raw_distance)

        similar_memories.append(
            SimilarIncidentMemory(
                incident_id=memory.incident_id,
                distance=distance_value,
                similarity=1.0 - distance_value,
                incident_snapshot=memory.incident_snapshot,
            )
        )

    return similar_memories
