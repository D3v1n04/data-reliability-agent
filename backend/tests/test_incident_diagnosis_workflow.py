from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models import IncidentDiagnosis
from backend.app.services.bedrock import BedrockService
from backend.app.services.incident_diagnosis import (
    GeneratedIncidentDiagnosis,
    IncidentDiagnosisGenerationError,
)
from backend.app.services.incident_diagnosis_workflow import (
    IncidentDiagnosisWorkflowError,
    IncidentNotDiagnosableError,
    IncidentNotFoundError,
    get_or_create_incident_diagnosis,
)
from backend.app.services.incident_memory_store import (
    IncidentMemoryInput,
    PreparedIncidentMemory,
)


INCIDENT_ID = UUID("11111111-1111-1111-1111-111111111111")
RUN_ID = UUID("22222222-2222-2222-2222-222222222222")
PIPELINE_ID = UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=(
            "postgresql://user:password@example.com/database"
        ),
        bedrock_text_model_id="amazon.nova-lite-v1:0",
        bedrock_embedding_model_id=(
            "amazon.titan-embed-text-v2:0"
        ),
        bedrock_embedding_dimensions=256,
        similar_incident_limit=5,
    )


def make_context() -> tuple[
    SimpleNamespace,
    SimpleNamespace,
    SimpleNamespace,
]:
    incident = SimpleNamespace(
        id=INCIDENT_ID,
        pipeline_run_id=RUN_ID,
    )

    pipeline_run = SimpleNamespace(
        id=RUN_ID,
        pipeline_id=PIPELINE_ID,
    )

    pipeline = SimpleNamespace(
        id=PIPELINE_ID,
    )

    return incident, pipeline_run, pipeline


def make_existing_diagnosis() -> IncidentDiagnosis:
    return IncidentDiagnosis(
        incident_id=INCIDENT_ID,
        explanation="The pipeline failed validation.",
        likely_causes=[
            "Invalid source data",
        ],
        recommendations=[
            "Inspect the rejected records",
        ],
        confidence=0.8,
        evidence={
            "current_incident_id": str(INCIDENT_ID),
            "deterministic_violations": [],
            "similar_incidents": [],
        },
        text_model_id="amazon.nova-lite-v1:0",
    )


def make_generated_diagnosis() -> GeneratedIncidentDiagnosis:
    return GeneratedIncidentDiagnosis(
        explanation="The source data failed validation.",
        likely_causes=[
            "Invalid source file structure",
        ],
        recommendations=[
            "Inspect the rejected source files",
        ],
        confidence=0.87,
        evidence={
            "current_incident_id": str(INCIDENT_ID),
            "deterministic_violations": [
                {
                    "code": "RUN_FAILED",
                    "severity": "critical",
                }
            ],
            "similar_incidents": [],
        },
    )


def make_memory_input() -> IncidentMemoryInput:
    return IncidentMemoryInput(
        incident_id=INCIDENT_ID,
        incident_snapshot={"schema_version": 1},
        embedding_input="deterministic incident evidence",
    )


def make_prepared_memory(
    *,
    needs_persistence: bool = True,
) -> PreparedIncidentMemory:
    memory_input = make_memory_input()
    return PreparedIncidentMemory(
        incident_id=memory_input.incident_id,
        incident_snapshot=memory_input.incident_snapshot,
        embedding_input=memory_input.embedding_input,
        embedding=[0.0] * 255 + [1.0],
        embedding_model_id="amazon.titan-embed-text-v2:0",
        needs_persistence=needs_persistence,
    )


def configure_nested_transaction(
    db: Mock,
) -> MagicMock:
    transaction = MagicMock()
    db.begin_nested.return_value = transaction
    transaction.__enter__.return_value = transaction
    transaction.__exit__.return_value = False
    return transaction


def test_returns_existing_diagnosis_without_bedrock_call(
    settings: Settings,
) -> None:
    existing_diagnosis = make_existing_diagnosis()

    db = Mock(spec=Session)
    db.scalar.return_value = existing_diagnosis

    bedrock_service = Mock(spec=BedrockService)

    result = get_or_create_incident_diagnosis(
        db=db,
        incident_id=INCIDENT_ID,
        bedrock_service=bedrock_service,
        settings=settings,
    )

    assert result.diagnosis is existing_diagnosis
    assert result.created is False

    db.get.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()
    bedrock_service.generate_embedding.assert_not_called()
    bedrock_service.generate_text.assert_not_called()


def test_rejects_missing_incident(
    settings: Settings,
) -> None:
    db = Mock(spec=Session)
    db.scalar.return_value = None
    db.get.return_value = None

    bedrock_service = Mock(spec=BedrockService)

    with pytest.raises(
        IncidentNotFoundError,
        match="not found",
    ):
        get_or_create_incident_diagnosis(
            db=db,
            incident_id=INCIDENT_ID,
            bedrock_service=bedrock_service,
            settings=settings,
        )

    bedrock_service.generate_embedding.assert_not_called()
    bedrock_service.generate_text.assert_not_called()


def test_rejects_incident_without_pipeline_run(
    settings: Settings,
) -> None:
    incident = SimpleNamespace(
        id=INCIDENT_ID,
        pipeline_run_id=None,
    )

    db = Mock(spec=Session)
    db.scalar.return_value = None
    db.get.return_value = incident

    bedrock_service = Mock(spec=BedrockService)

    with pytest.raises(
        IncidentNotDiagnosableError,
        match="not associated",
    ):
        get_or_create_incident_diagnosis(
            db=db,
            incident_id=INCIDENT_ID,
            bedrock_service=bedrock_service,
            settings=settings,
        )

    bedrock_service.generate_embedding.assert_not_called()
    bedrock_service.generate_text.assert_not_called()


def test_creates_and_commits_diagnosis(
    settings: Settings,
) -> None:
    incident, pipeline_run, pipeline = make_context()

    db = Mock(spec=Session)
    db.scalar.return_value = None
    db.get.side_effect = [
        incident,
        pipeline_run,
        pipeline,
    ]
    configure_nested_transaction(db)

    bedrock_service = Mock(spec=BedrockService)

    memory_input = make_memory_input()
    prepared_memory = make_prepared_memory()
    generated_diagnosis = make_generated_diagnosis()

    with (
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "load_incident_memory"
            ),
            return_value=None,
        ) as load_memory,
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "build_incident_memory_input"
            ),
            return_value=memory_input,
        ) as build_memory_input,
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "generate_incident_memory"
            ),
            return_value=prepared_memory,
        ) as generate_memory,
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "find_similar_incident_memories"
            ),
            return_value=[],
        ) as find_similar,
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "generate_incident_diagnosis"
            ),
            return_value=generated_diagnosis,
        ) as generate_diagnosis,
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "persist_incident_memory"
            ),
        ) as persist_memory,
    ):
        result = get_or_create_incident_diagnosis(
            db=db,
            incident_id=INCIDENT_ID,
            bedrock_service=bedrock_service,
            settings=settings,
        )

    assert result.created is True
    assert result.diagnosis.incident_id == INCIDENT_ID
    assert result.diagnosis.explanation == (
        "The source data failed validation."
    )
    assert result.diagnosis.confidence == pytest.approx(0.87)
    assert result.diagnosis.text_model_id == (
        "amazon.nova-lite-v1:0"
    )

    load_memory.assert_called_once_with(
        db=db,
        incident_id=INCIDENT_ID,
    )
    build_memory_input.assert_called_once()
    generate_memory.assert_called_once_with(
        memory_input=memory_input,
        bedrock_service=bedrock_service,
        settings=settings,
    )
    find_similar.assert_called_once_with(
        db=db,
        embedding=prepared_memory.embedding,
        exclude_incident_id=INCIDENT_ID,
        settings=settings,
    )
    generate_diagnosis.assert_called_once_with(
        incident_snapshot=prepared_memory.incident_snapshot,
        similar_memories=[],
        bedrock_service=bedrock_service,
    )
    persist_memory.assert_called_once_with(
        db,
        prepared_memory,
    )

    db.add.assert_called_once_with(result.diagnosis)
    db.flush.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result.diagnosis)
    assert db.rollback.call_count == 2


def test_rolls_back_when_generation_fails(
    settings: Settings,
) -> None:
    incident, pipeline_run, pipeline = make_context()

    db = Mock(spec=Session)
    db.scalar.return_value = None
    db.get.side_effect = [
        incident,
        pipeline_run,
        pipeline,
    ]

    bedrock_service = Mock(spec=BedrockService)

    memory_input = make_memory_input()
    prepared_memory = make_prepared_memory()

    with (
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "load_incident_memory"
            ),
            return_value=None,
        ),
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "build_incident_memory_input"
            ),
            return_value=memory_input,
        ),
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "generate_incident_memory"
            ),
            return_value=prepared_memory,
        ),
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "find_similar_incident_memories"
            ),
            return_value=[],
        ),
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "generate_incident_diagnosis"
            ),
            side_effect=IncidentDiagnosisGenerationError(
                "Invalid Nova response"
            ),
        ),
    ):
        with pytest.raises(
            IncidentDiagnosisWorkflowError,
            match="Unable to generate",
        ):
            get_or_create_incident_diagnosis(
                db=db,
                incident_id=INCIDENT_ID,
                bedrock_service=bedrock_service,
                settings=settings,
            )

    assert db.rollback.call_count == 3
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_recovers_from_concurrent_duplicate_diagnosis(
    settings: Settings,
) -> None:
    incident, pipeline_run, pipeline = make_context()
    concurrent_diagnosis = make_existing_diagnosis()

    db = Mock(spec=Session)
    db.scalar.side_effect = [None, None, concurrent_diagnosis]
    db.get.side_effect = [
        incident,
        pipeline_run,
        pipeline,
    ]
    configure_nested_transaction(db)
    db.flush.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate incident_id"),
    )

    bedrock_service = Mock(spec=BedrockService)

    prepared_memory = make_prepared_memory(
        needs_persistence=False,
    )

    with (
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "load_incident_memory"
            ),
            return_value=prepared_memory,
        ),
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "find_similar_incident_memories"
            ),
            return_value=[],
        ),
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "generate_incident_diagnosis"
            ),
            return_value=make_generated_diagnosis(),
        ),
    ):
        result = get_or_create_incident_diagnosis(
            db=db,
            incident_id=INCIDENT_ID,
            bedrock_service=bedrock_service,
            settings=settings,
        )

    assert result.diagnosis is concurrent_diagnosis
    assert result.created is False
    assert db.scalar.call_count == 3
    db.commit.assert_called_once()
    assert db.rollback.call_count == 2
    db.refresh.assert_called_once_with(concurrent_diagnosis)


def test_returns_concurrent_diagnosis_found_before_final_write(
    settings: Settings,
) -> None:
    incident, pipeline_run, pipeline = make_context()
    concurrent_diagnosis = make_existing_diagnosis()
    prepared_memory = make_prepared_memory(
        needs_persistence=False,
    )
    db = Mock(spec=Session)
    db.scalar.side_effect = [None, concurrent_diagnosis]
    db.get.side_effect = [incident, pipeline_run, pipeline]
    bedrock_service = Mock(spec=BedrockService)

    with (
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "load_incident_memory"
            ),
            return_value=prepared_memory,
        ),
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "find_similar_incident_memories"
            ),
            return_value=[],
        ),
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "generate_incident_diagnosis"
            ),
            return_value=make_generated_diagnosis(),
        ) as generate_diagnosis,
        patch(
            (
                "backend.app.services."
                "incident_diagnosis_workflow."
                "persist_incident_memory"
            ),
        ) as persist_memory,
    ):
        result = get_or_create_incident_diagnosis(
            db=db,
            incident_id=INCIDENT_ID,
            bedrock_service=bedrock_service,
            settings=settings,
        )

    assert result.diagnosis is concurrent_diagnosis
    assert result.created is False
    generate_diagnosis.assert_called_once()
    persist_memory.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()
    assert db.rollback.call_count == 3
    db.refresh.assert_called_once_with(concurrent_diagnosis)
