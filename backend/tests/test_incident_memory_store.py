from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models import IncidentMemory
from backend.app.services.bedrock import BedrockService
from backend.app.services.incident_memory_store import (
    find_similar_incident_memories,
    get_or_create_incident_memory,
)


INCIDENT_ID = UUID("11111111-1111-1111-1111-111111111111")
RUN_ID = UUID("22222222-2222-2222-2222-222222222222")
PIPELINE_ID = UUID("33333333-3333-3333-3333-333333333333")
PRIOR_INCIDENT_ID = UUID(
    "44444444-4444-4444-4444-444444444444"
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=(
            "postgresql://user:password@example.com/database"
        ),
        bedrock_embedding_dimensions=256,
        bedrock_embedding_model_id=(
            "amazon.titan-embed-text-v2:0"
        ),
        similar_incident_limit=5,
    )


def make_context() -> tuple[
    SimpleNamespace,
    SimpleNamespace,
    SimpleNamespace,
]:
    scheduled_at = datetime(
        2026,
        7,
        27,
        12,
        0,
        tzinfo=timezone.utc,
    )
    started_at = scheduled_at + timedelta(seconds=90)
    completed_at = started_at + timedelta(seconds=420)

    pipeline = SimpleNamespace(
        id=PIPELINE_ID,
        name="daily-customer-import",
        description="Imports validated customer records",
        max_duration_seconds=300,
        min_rows_processed=1000,
        max_start_delay_seconds=60,
        enabled=True,
    )

    pipeline_run = SimpleNamespace(
        id=RUN_ID,
        pipeline_id=PIPELINE_ID,
        external_run_id="customer-import-2026-07-27",
        status="failed",
        scheduled_at=scheduled_at,
        started_at=started_at,
        completed_at=completed_at,
        rows_processed=250,
        quality_checks_failed=2,
        metrics={
            "valid_rows": 250,
            "invalid_rows": 50,
        },
        error_message="Source file validation failed",
        logs=[
            {
                "level": "error",
                "message": "Two source files were invalid",
            }
        ],
    )

    incident = SimpleNamespace(
        id=INCIDENT_ID,
        pipeline_run_id=RUN_ID,
        source="reliability-engine",
        title="Daily customer import failed",
        description="Reliability rules were violated",
        severity="critical",
        status="open",
        detected_at=completed_at,
        resolved_at=None,
        details={
            "violations": [
                {
                    "code": "RUN_FAILED",
                    "severity": "critical",
                }
            ]
        },
    )

    return incident, pipeline_run, pipeline


def make_existing_memory() -> IncidentMemory:
    return IncidentMemory(
        incident_id=PRIOR_INCIDENT_ID,
        incident_snapshot={
            "incident": {
                "title": "Previous customer import failure",
            }
        },
        embedding_input="previous failure",
        embedding=[0.0] * 255 + [1.0],
        embedding_model_id="amazon.titan-embed-text-v2:0",
    )


def configure_nested_transaction(
    db: Mock,
) -> MagicMock:
    transaction = MagicMock()
    db.begin_nested.return_value = transaction
    transaction.__enter__.return_value = transaction
    transaction.__exit__.return_value = False
    return transaction


def test_creates_incident_memory(
    settings: Settings,
) -> None:
    incident, pipeline_run, pipeline = make_context()

    db = Mock(spec=Session)
    db.scalar.return_value = None
    configure_nested_transaction(db)

    bedrock_service = Mock(spec=BedrockService)
    bedrock_service.generate_embedding.return_value = (
        [0.0] * 255 + [1.0]
    )

    result = get_or_create_incident_memory(
        db=db,
        incident=incident,
        pipeline_run=pipeline_run,
        pipeline=pipeline,
        bedrock_service=bedrock_service,
        settings=settings,
    )

    assert result.incident_id == INCIDENT_ID
    assert len(result.embedding) == 256
    assert result.embedding_model_id == (
        "amazon.titan-embed-text-v2:0"
    )
    assert result.incident_snapshot["schema_version"] == 1

    bedrock_service.generate_embedding.assert_called_once()
    db.add.assert_called_once_with(result)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


def test_returns_existing_memory_without_bedrock_call(
    settings: Settings,
) -> None:
    incident, pipeline_run, pipeline = make_context()

    existing_memory = make_existing_memory()
    existing_memory.incident_id = INCIDENT_ID

    db = Mock(spec=Session)
    db.scalar.return_value = existing_memory

    bedrock_service = Mock(spec=BedrockService)

    result = get_or_create_incident_memory(
        db=db,
        incident=incident,
        pipeline_run=pipeline_run,
        pipeline=pipeline,
        bedrock_service=bedrock_service,
        settings=settings,
    )

    assert result is existing_memory
    bedrock_service.generate_embedding.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_recovers_from_concurrent_duplicate(
    settings: Settings,
) -> None:
    incident, pipeline_run, pipeline = make_context()

    concurrent_memory = make_existing_memory()
    concurrent_memory.incident_id = INCIDENT_ID

    db = Mock(spec=Session)
    db.scalar.side_effect = [
        None,
        concurrent_memory,
    ]
    configure_nested_transaction(db)
    db.flush.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate incident_id"),
    )

    bedrock_service = Mock(spec=BedrockService)
    bedrock_service.generate_embedding.return_value = (
        [0.0] * 255 + [1.0]
    )

    result = get_or_create_incident_memory(
        db=db,
        incident=incident,
        pipeline_run=pipeline_run,
        pipeline=pipeline,
        bedrock_service=bedrock_service,
        settings=settings,
    )

    assert result is concurrent_memory
    assert db.scalar.call_count == 2


def test_finds_similar_memories_by_cosine_distance(
    settings: Settings,
) -> None:
    db = Mock(spec=Session)
    previous_memory = make_existing_memory()

    db.execute.return_value.all.return_value = [
        (
            previous_memory,
            0.12,
        )
    ]

    results = find_similar_incident_memories(
        db=db,
        embedding=[0.0] * 255 + [1.0],
        exclude_incident_id=INCIDENT_ID,
        limit=3,
        settings=settings,
    )

    assert len(results) == 1
    assert results[0].incident_id == PRIOR_INCIDENT_ID
    assert results[0].distance == pytest.approx(0.12)
    assert results[0].similarity == pytest.approx(0.88)
    assert results[0].incident_snapshot == (
        previous_memory.incident_snapshot
    )

    statement = db.execute.call_args.args[0]
    statement_text = str(statement)

    assert "<=>" in statement_text
    assert "incident_memories.incident_id !=" in statement_text


def test_rejects_embedding_with_wrong_dimensions(
    settings: Settings,
) -> None:
    db = Mock(spec=Session)

    with pytest.raises(
        ValueError,
        match="dimensions",
    ):
        find_similar_incident_memories(
            db=db,
            embedding=[0.0] * 255,
            exclude_incident_id=INCIDENT_ID,
            settings=settings,
        )

    db.execute.assert_not_called()


def test_rejects_invalid_similarity_limit(
    settings: Settings,
) -> None:
    db = Mock(spec=Session)

    with pytest.raises(
        ValueError,
        match="between 1 and 20",
    ):
        find_similar_incident_memories(
            db=db,
            embedding=[0.0] * 255 + [1.0],
            exclude_incident_id=INCIDENT_ID,
            limit=21,
            settings=settings,
        )

    db.execute.assert_not_called()
