"""Characterize the diagnosis workflow's current connection lifetime.

SQLite validates SQLAlchemy Session autobegin, transaction, and QueuePool
mechanics while the real diagnosis workflow runs. It does not model
CockroachDB latency, contention, isolation, retries, or vector execution.
These tests intentionally capture the current long checkout across mocked
Titan and Nova calls so a later transaction-boundary change has a deterministic
before-state.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from sqlalchemy import Engine, create_engine, event, func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from backend.app.core.config import Settings
from backend.app.models import (
    Incident,
    IncidentDiagnosis,
    IncidentMemory,
    Pipeline,
    PipelineRun,
)
from backend.app.services.bedrock import (
    BedrockService,
    BedrockServiceError,
)
from backend.app.services.incident_diagnosis_workflow import (
    IncidentDiagnosisWorkflowError,
    get_or_create_incident_diagnosis,
)


PIPELINE_ID = UUID("11111111-1111-1111-1111-111111111111")
RUN_ID = UUID("22222222-2222-2222-2222-222222222222")
INCIDENT_ID = UUID("33333333-3333-3333-3333-333333333333")
EXISTING_DIAGNOSIS_ID = UUID(
    "44444444-4444-4444-4444-444444444444"
)


SQLITE_SCHEMA = (
    """
    CREATE TABLE pipelines (
        id CHAR(32) PRIMARY KEY,
        name VARCHAR NOT NULL,
        description VARCHAR,
        max_duration_seconds INTEGER,
        min_rows_processed INTEGER,
        max_start_delay_seconds INTEGER,
        enabled BOOLEAN NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE pipeline_runs (
        id CHAR(32) PRIMARY KEY,
        pipeline_id CHAR(32) NOT NULL,
        external_run_id VARCHAR NOT NULL,
        status VARCHAR NOT NULL,
        scheduled_at DATETIME NOT NULL,
        started_at DATETIME NOT NULL,
        completed_at DATETIME NOT NULL,
        rows_processed INTEGER,
        quality_checks_failed INTEGER NOT NULL,
        metrics JSON NOT NULL,
        error_message VARCHAR,
        logs JSON NOT NULL,
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE incidents (
        id CHAR(32) PRIMARY KEY,
        pipeline_run_id CHAR(32) UNIQUE,
        source VARCHAR NOT NULL,
        title VARCHAR NOT NULL,
        description VARCHAR,
        severity VARCHAR NOT NULL,
        status VARCHAR NOT NULL,
        detected_at DATETIME NOT NULL,
        resolved_at DATETIME,
        details JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE incident_memories (
        id CHAR(32) PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        incident_id CHAR(32) NOT NULL UNIQUE,
        incident_snapshot JSON NOT NULL,
        embedding_input VARCHAR NOT NULL,
        embedding TEXT NOT NULL,
        embedding_model_id VARCHAR NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE incident_diagnoses (
        id CHAR(32) PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        incident_id CHAR(32) NOT NULL UNIQUE,
        explanation VARCHAR NOT NULL,
        likely_causes JSON NOT NULL,
        recommendations JSON NOT NULL,
        confidence FLOAT NOT NULL,
        evidence JSON NOT NULL,
        text_model_id VARCHAR NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)


@dataclass(frozen=True)
class StageObservation:
    name: str
    in_transaction: bool
    checked_out: int


@dataclass
class LifetimeHarness:
    engine: Engine
    session: Session
    settings: Settings
    timeline: list[str] = field(default_factory=list)
    stages: list[StageObservation] = field(default_factory=list)
    record_events: bool = True

    def observe(self, name: str) -> None:
        checked_out = self.engine.pool.checkedout()  # type: ignore[attr-defined]
        self.timeline.append(name)
        self.stages.append(
            StageObservation(
                name=name,
                in_transaction=self.session.in_transaction(),
                checked_out=checked_out,
            )
        )

    def stage(self, name: str) -> StageObservation:
        return next(stage for stage in self.stages if stage.name == name)

    def stop_recording(self) -> None:
        self.record_events = False


def _create_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        for statement in SQLITE_SCHEMA:
            connection.exec_driver_sql(statement)


def _enable_sqlite_transaction_control(engine: Engine) -> None:
    """Disable SQLite legacy mode so SAVEPOINT belongs to outer BEGIN."""

    def disable_driver_transaction_control(
        dbapi_connection: object,
        _connection_record: object,
    ) -> None:
        dbapi_connection.isolation_level = None  # type: ignore[attr-defined]

    def emit_explicit_begin(connection: object) -> None:
        connection.exec_driver_sql("BEGIN")  # type: ignore[attr-defined]

    event.listen(
        engine,
        "connect",
        disable_driver_transaction_control,
    )
    event.listen(engine, "begin", emit_explicit_begin)


def _seed_incident_context(engine: Engine) -> None:
    scheduled_at = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
    started_at = scheduled_at + timedelta(seconds=90)
    completed_at = started_at + timedelta(seconds=420)

    with Session(engine, expire_on_commit=False) as session:
        session.add_all(
            [
                Pipeline(
                    id=PIPELINE_ID,
                    name="daily-customer-import",
                    description="Imports validated customer records",
                    max_duration_seconds=300,
                    min_rows_processed=1000,
                    max_start_delay_seconds=60,
                    enabled=True,
                    created_at=scheduled_at,
                    updated_at=scheduled_at,
                ),
                PipelineRun(
                    id=RUN_ID,
                    pipeline_id=PIPELINE_ID,
                    external_run_id="customer-import-2026-07-31",
                    status="failed",
                    scheduled_at=scheduled_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    rows_processed=250,
                    quality_checks_failed=2,
                    metrics={"invalid_rows": 50},
                    error_message="Source file validation failed",
                    logs=["Two source files were invalid"],
                    created_at=completed_at,
                ),
                Incident(
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
                                "rule_code": "RUN_FAILED",
                                "severity": "critical",
                                "message": "Pipeline reported failure",
                            }
                        ]
                    },
                    created_at=completed_at,
                    updated_at=completed_at,
                ),
            ]
        )
        session.commit()


@pytest.fixture
def lifetime_harness() -> LifetimeHarness:
    engine = create_engine(
        "sqlite://",
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
    )
    _enable_sqlite_transaction_control(engine)
    _create_schema(engine)
    _seed_incident_context(engine)

    harness = LifetimeHarness(
        engine=engine,
        session=Session(engine, expire_on_commit=False),
        settings=Settings(
            database_url=(
                "postgresql://unused:unused@example.invalid/database"
            ),
            bedrock_embedding_dimensions=256,
            similar_incident_limit=5,
        ),
    )

    def record_checkout(*_args: object) -> None:
        if harness.record_events:
            harness.timeline.append("pool_checkout")

    def record_checkin(*_args: object) -> None:
        if harness.record_events:
            harness.timeline.append("pool_checkin")

    def record_sql(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if harness.record_events:
            operation = statement.lstrip().split(None, 1)[0].lower()
            harness.observe(f"sql_{operation}")

    event.listen(engine, "checkout", record_checkout)
    event.listen(engine, "checkin", record_checkin)
    event.listen(engine, "before_cursor_execute", record_sql)

    try:
        yield harness
    finally:
        harness.session.close()
        engine.dispose()


def _mock_bedrock(
    harness: LifetimeHarness,
    *,
    nova_error: Exception | None = None,
) -> Mock:
    bedrock_service = Mock(spec=BedrockService)

    def generate_embedding(_input_text: str) -> list[float]:
        harness.observe("during_titan")
        return [0.0] * 255 + [1.0]

    def generate_structured_output(**_kwargs: object) -> dict[str, object]:
        harness.observe("during_nova")
        if nova_error is not None:
            raise nova_error

        return {
            "explanation": "RUN_FAILED was observed in the current run.",
            "likely_causes": ["Source data validation failed."],
            "recommendations": ["Inspect the rejected source records."],
            "confidence": 0.5,
        }

    bedrock_service.generate_embedding.side_effect = generate_embedding
    bedrock_service.generate_structured_output.side_effect = (
        generate_structured_output
    )
    return bedrock_service


def _find_no_similar_memories(
    harness: LifetimeHarness,
):
    def find_similar_memories(*, db: Session, **_kwargs: object) -> list:
        harness.observe("before_similar_select")
        db.execute(text("SELECT 1")).all()
        harness.observe("after_similar_select")
        return []

    return find_similar_memories


def _stored_counts(engine: Engine) -> tuple[int, int]:
    with Session(engine) as session:
        memory_count = session.scalar(
            select(func.count()).select_from(IncidentMemory)
        )
        diagnosis_count = session.scalar(
            select(func.count()).select_from(IncidentDiagnosis)
        )

    return int(memory_count or 0), int(diagnosis_count or 0)


def test_success_holds_checkout_across_titan_and_nova_then_refreshes(
    lifetime_harness: LifetimeHarness,
) -> None:
    harness = lifetime_harness
    bedrock_service = _mock_bedrock(harness)

    with patch(
        (
            "backend.app.services.incident_diagnosis_workflow."
            "find_similar_incident_memories"
        ),
        side_effect=_find_no_similar_memories(harness),
    ):
        result = get_or_create_incident_diagnosis(
            db=harness.session,
            incident_id=INCIDENT_ID,
            bedrock_service=bedrock_service,
            settings=harness.settings,
        )

    harness.observe("workflow_returned")

    assert result.created is True
    assert harness.timeline[0:3] == [
        "pool_checkout",
        "sql_begin",
        "sql_select",
    ]
    assert harness.stage("sql_select") == StageObservation(
        name="sql_select",
        in_transaction=True,
        checked_out=1,
    )
    assert harness.stage("during_titan") == StageObservation(
        name="during_titan",
        in_transaction=True,
        checked_out=1,
    )
    assert harness.stage("during_nova") == StageObservation(
        name="during_nova",
        in_transaction=True,
        checked_out=1,
    )

    first_checkin = harness.timeline.index("pool_checkin")
    second_checkout = harness.timeline.index("pool_checkout", 1)
    assert harness.timeline.index("during_nova") < first_checkin
    assert first_checkin < second_checkout
    assert harness.timeline[
        second_checkout : second_checkout + 3
    ] == [
        "pool_checkout",
        "sql_begin",
        "sql_select",
    ]
    assert second_checkout < harness.timeline.index("workflow_returned")
    assert harness.stage("workflow_returned") == StageObservation(
        name="workflow_returned",
        in_transaction=True,
        checked_out=1,
    )

    harness.session.close()
    harness.observe("after_session_close")

    assert harness.timeline.count("pool_checkout") == 2
    assert harness.timeline.count("pool_checkin") == 2
    assert harness.stage("after_session_close") == StageObservation(
        name="after_session_close",
        in_transaction=False,
        checked_out=0,
    )

    harness.stop_recording()
    assert _stored_counts(harness.engine) == (1, 1)


def test_nova_failure_rolls_back_memory_and_returns_checkout(
    lifetime_harness: LifetimeHarness,
) -> None:
    harness = lifetime_harness
    bedrock_service = _mock_bedrock(
        harness,
        nova_error=BedrockServiceError("mocked Nova failure"),
    )

    with (
        patch(
            (
                "backend.app.services.incident_diagnosis_workflow."
                "find_similar_incident_memories"
            ),
            side_effect=_find_no_similar_memories(harness),
        ),
        pytest.raises(
            IncidentDiagnosisWorkflowError,
            match="Unable to generate incident diagnosis",
        ),
    ):
        get_or_create_incident_diagnosis(
            db=harness.session,
            incident_id=INCIDENT_ID,
            bedrock_service=bedrock_service,
            settings=harness.settings,
        )

    harness.observe("after_workflow_rollback")

    assert harness.stage("during_titan").in_transaction is True
    assert harness.stage("during_titan").checked_out == 1
    assert harness.stage("during_nova").in_transaction is True
    assert harness.stage("during_nova").checked_out == 1
    assert harness.timeline.index("during_nova") < harness.timeline.index(
        "pool_checkin"
    )
    assert harness.timeline.count("pool_checkout") == 1
    assert harness.timeline.count("pool_checkin") == 1
    assert harness.stage("after_workflow_rollback") == StageObservation(
        name="after_workflow_rollback",
        in_transaction=False,
        checked_out=0,
    )

    harness.stop_recording()
    assert _stored_counts(harness.engine) == (0, 0)


def test_existing_diagnosis_skips_titan_and_nova(
    lifetime_harness: LifetimeHarness,
) -> None:
    harness = lifetime_harness
    harness.stop_recording()

    with Session(harness.engine) as session:
        session.add(
            IncidentDiagnosis(
                id=EXISTING_DIAGNOSIS_ID,
                incident_id=INCIDENT_ID,
                explanation="A stored bounded diagnosis.",
                likely_causes=["Previously stored hypothesis."],
                recommendations=["Review the existing evidence."],
                confidence=0.5,
                evidence={"current_incident_id": str(INCIDENT_ID)},
                text_model_id="amazon.nova-lite-v1:0",
            )
        )
        session.commit()

    harness.timeline.clear()
    harness.stages.clear()
    harness.record_events = True
    bedrock_service = _mock_bedrock(harness)

    result = get_or_create_incident_diagnosis(
        db=harness.session,
        incident_id=INCIDENT_ID,
        bedrock_service=bedrock_service,
        settings=harness.settings,
    )

    assert result.created is False
    assert result.diagnosis.id == EXISTING_DIAGNOSIS_ID
    bedrock_service.generate_embedding.assert_not_called()
    bedrock_service.generate_structured_output.assert_not_called()

    harness.session.close()
    assert harness.timeline.count("pool_checkout") == 1
    assert harness.timeline.count("pool_checkin") == 1
