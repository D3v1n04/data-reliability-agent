from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.models import (
    Incident,
    IncidentDiagnosis,
    Pipeline,
    PipelineRun,
)
from backend.app.services.bedrock import (
    BedrockService,
    BedrockServiceError,
)
from backend.app.services.incident_diagnosis import (
    IncidentDiagnosisGenerationError,
    generate_incident_diagnosis,
)
from backend.app.services.incident_memory_store import (
    IncidentMemoryInput,
    IncidentMemoryStoreError,
    build_incident_memory_input,
    find_similar_incident_memories,
    generate_incident_memory,
    load_incident_memory,
    persist_incident_memory,
)


class IncidentNotFoundError(LookupError):
    """Raised when the requested incident does not exist."""


class IncidentNotDiagnosableError(ValueError):
    """Raised when an incident has no pipeline-run evidence."""


class IncidentDiagnosisWorkflowError(RuntimeError):
    """Raised when the diagnosis workflow cannot complete."""

    def __init__(
        self,
        message: str,
        category: str = "diagnosis",
    ) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class IncidentDiagnosisWorkflowResult:
    """A persisted diagnosis and whether this request created it."""

    diagnosis: IncidentDiagnosis
    created: bool


def _find_existing_diagnosis(
    db: Session,
    incident_id: UUID,
) -> IncidentDiagnosis | None:
    """Retrieve an existing diagnosis safely."""
    query = select(IncidentDiagnosis).where(
        IncidentDiagnosis.incident_id == incident_id
    )

    try:
        return db.scalar(query)
    except SQLAlchemyError as exc:
        raise IncidentDiagnosisWorkflowError(
            "Unable to retrieve incident diagnosis",
            category="database",
        ) from exc


def _load_incident_context(
    db: Session,
    incident_id: UUID,
) -> tuple[Incident, PipelineRun, Pipeline]:
    """Load the deterministic records required for diagnosis."""
    try:
        incident = db.get(Incident, incident_id)
    except SQLAlchemyError as exc:
        raise IncidentDiagnosisWorkflowError(
            "Unable to retrieve incident",
            category="database",
        ) from exc

    if incident is None:
        raise IncidentNotFoundError("Incident was not found")

    if incident.pipeline_run_id is None:
        raise IncidentNotDiagnosableError(
            "Incident is not associated with a pipeline run"
        )

    try:
        pipeline_run = db.get(
            PipelineRun,
            incident.pipeline_run_id,
        )
    except SQLAlchemyError as exc:
        raise IncidentDiagnosisWorkflowError(
            "Unable to retrieve incident pipeline run",
            category="database",
        ) from exc

    if pipeline_run is None:
        raise IncidentDiagnosisWorkflowError(
            "Incident pipeline run was not found",
            category="database",
        )

    try:
        pipeline = db.get(
            Pipeline,
            pipeline_run.pipeline_id,
        )
    except SQLAlchemyError as exc:
        raise IncidentDiagnosisWorkflowError(
            "Unable to retrieve incident pipeline",
            category="database",
        ) from exc

    if pipeline is None:
        raise IncidentDiagnosisWorkflowError(
            "Incident pipeline was not found",
            category="database",
        )

    return incident, pipeline_run, pipeline


def _end_read_transaction(
    db: Session,
    failure_message: str,
) -> None:
    """Roll back a read transaction and return its pooled connection."""
    try:
        db.rollback()
    except SQLAlchemyError as exc:
        raise IncidentDiagnosisWorkflowError(
            failure_message,
            category="database",
        ) from exc


def get_or_create_incident_diagnosis(
    db: Session,
    incident_id: UUID,
    bedrock_service: BedrockService,
    settings: Settings | None = None,
) -> IncidentDiagnosisWorkflowResult:
    """Generate and persist one diagnosis per incident."""
    resolved_settings = settings or get_settings()

    existing_diagnosis = _find_existing_diagnosis(
        db,
        incident_id,
    )

    if existing_diagnosis is not None:
        return IncidentDiagnosisWorkflowResult(
            diagnosis=existing_diagnosis,
            created=False,
        )

    incident, pipeline_run, pipeline = _load_incident_context(
        db,
        incident_id,
    )

    incident_id_value = incident.id
    memory_input: IncidentMemoryInput | None = None

    try:
        prepared_memory = load_incident_memory(
            db=db,
            incident_id=incident_id_value,
        )

        if prepared_memory is None:
            memory_input = build_incident_memory_input(
                incident,
                pipeline_run,
                pipeline,
            )
    except IncidentMemoryStoreError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to prepare incident memory",
            category="database",
        ) from exc
    except ValueError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to prepare incident memory",
            category="diagnosis",
        ) from exc

    _end_read_transaction(
        db,
        "Unable to finish incident evidence retrieval",
    )

    try:
        if prepared_memory is None:
            if memory_input is None:
                raise ValueError("Incident memory input is unavailable")

            prepared_memory = generate_incident_memory(
                memory_input=memory_input,
                bedrock_service=bedrock_service,
                settings=resolved_settings,
            )
    except BedrockServiceError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to generate incident diagnosis",
            category="bedrock",
        ) from exc
    except ValueError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to generate incident diagnosis",
            category="diagnosis",
        ) from exc

    try:
        similar_memories = find_similar_incident_memories(
            db=db,
            embedding=prepared_memory.embedding,
            exclude_incident_id=incident_id_value,
            settings=resolved_settings,
        )
    except IncidentMemoryStoreError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to generate incident diagnosis",
            category="database",
        ) from exc
    except ValueError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to generate incident diagnosis",
            category="diagnosis",
        ) from exc

    _end_read_transaction(
        db,
        "Unable to finish similar incident retrieval",
    )

    try:
        generated_diagnosis = generate_incident_diagnosis(
            incident_snapshot=prepared_memory.incident_snapshot,
            similar_memories=similar_memories,
            bedrock_service=bedrock_service,
        )
    except BedrockServiceError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to generate incident diagnosis",
            category="bedrock",
        ) from exc
    except (IncidentDiagnosisGenerationError, ValueError) as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to generate incident diagnosis",
            category="diagnosis",
        ) from exc

    diagnosis = IncidentDiagnosis(
        incident_id=incident_id_value,
        explanation=generated_diagnosis.explanation,
        likely_causes=generated_diagnosis.likely_causes,
        recommendations=generated_diagnosis.recommendations,
        confidence=generated_diagnosis.confidence,
        evidence=generated_diagnosis.evidence,
        text_model_id=resolved_settings.bedrock_text_model_id,
    )

    concurrent_diagnosis = _find_existing_diagnosis(
        db,
        incident_id,
    )

    if concurrent_diagnosis is not None:
        try:
            db.rollback()
            db.refresh(concurrent_diagnosis)
        except SQLAlchemyError as exc:
            db.rollback()

            raise IncidentDiagnosisWorkflowError(
                "Unable to finalize concurrent diagnosis",
                category="database",
            ) from exc

        return IncidentDiagnosisWorkflowResult(
            diagnosis=concurrent_diagnosis,
            created=False,
        )

    try:
        if prepared_memory.needs_persistence:
            persist_incident_memory(
                db,
                prepared_memory,
            )
    except IncidentMemoryStoreError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to store incident memory",
            category="database",
        ) from exc

    try:
        with db.begin_nested():
            db.add(diagnosis)
            db.flush()
    except IntegrityError as exc:
        # A concurrent request may have stored the diagnosis
        # after the initial existence check.
        concurrent_diagnosis = _find_existing_diagnosis(
            db,
            incident_id,
        )

        if concurrent_diagnosis is None:
            db.rollback()

            raise IncidentDiagnosisWorkflowError(
                "Unable to recover concurrent diagnosis",
                category="database",
            ) from exc

        try:
            db.commit()
            db.refresh(concurrent_diagnosis)
        except SQLAlchemyError as commit_exc:
            db.rollback()

            raise IncidentDiagnosisWorkflowError(
                "Unable to finalize concurrent diagnosis",
                category="database",
            ) from commit_exc

        return IncidentDiagnosisWorkflowResult(
            diagnosis=concurrent_diagnosis,
            created=False,
        )
    except SQLAlchemyError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to store incident diagnosis",
            category="database",
        ) from exc

    try:
        db.commit()
        db.refresh(diagnosis)
    except SQLAlchemyError as exc:
        db.rollback()

        raise IncidentDiagnosisWorkflowError(
            "Unable to commit incident diagnosis",
            category="database",
        ) from exc

    return IncidentDiagnosisWorkflowResult(
        diagnosis=diagnosis,
        created=True,
    )
