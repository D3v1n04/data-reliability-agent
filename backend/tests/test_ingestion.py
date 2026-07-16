from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models import Incident, Pipeline, PipelineRun
from backend.app.schemas import PipelineRunCreate
from backend.app.services.ingestion import (
    PipelineNotFoundError,
    PipelineRunIngestionError,
    ingest_pipeline_run,
)


PIPELINE_ID = uuid4()
RUN_ID = uuid4()
INCIDENT_ID = uuid4()


def make_pipeline() -> Pipeline:
    return Pipeline(
        id=PIPELINE_ID,
        name="daily-customer-import",
        description="Imports customer data",
        max_duration_seconds=900,
        min_rows_processed=1000,
        max_start_delay_seconds=300,
        enabled=True,
    )


def make_run(**overrides: object) -> PipelineRunCreate:
    data: dict[str, object] = {
        "external_run_id": "customer-import-test-001",
        "status": "succeeded",
        "scheduled_at": datetime(
            2026,
            7,
            16,
            20,
            0,
            tzinfo=timezone.utc,
        ),
        "started_at": datetime(
            2026,
            7,
            16,
            20,
            2,
            tzinfo=timezone.utc,
        ),
        "completed_at": datetime(
            2026,
            7,
            16,
            20,
            12,
            tzinfo=timezone.utc,
        ),
        "rows_processed": 1250,
        "quality_checks_failed": 0,
        "metrics": {},
        "logs": [],
    }
    data.update(overrides)

    return PipelineRunCreate(**data)


def make_session() -> MagicMock:
    db = MagicMock(spec=Session)
    db.get.return_value = make_pipeline()
    db.scalar.return_value = None

    def assign_run_id() -> None:
        for call in db.add.call_args_list:
            record = call.args[0]

            if isinstance(record, PipelineRun):
                record.id = RUN_ID
                break

    db.flush.side_effect = assign_run_id

    return db


def make_existing_run() -> PipelineRun:
    return PipelineRun(
        id=RUN_ID,
        pipeline_id=PIPELINE_ID,
        external_run_id="customer-import-test-001",
        status="failed",
        scheduled_at=datetime(
            2026,
            7,
            16,
            20,
            0,
            tzinfo=timezone.utc,
        ),
        started_at=datetime(
            2026,
            7,
            16,
            20,
            10,
            tzinfo=timezone.utc,
        ),
        completed_at=datetime(
            2026,
            7,
            16,
            20,
            35,
            tzinfo=timezone.utc,
        ),
        rows_processed=450,
        quality_checks_failed=2,
        metrics={},
        error_message="Validation failed",
        logs=[],
    )


def make_existing_incident() -> Incident:
    return Incident(
        id=INCIDENT_ID,
        pipeline_run_id=RUN_ID,
        source="reliability-engine",
        title="Reliability failure: daily-customer-import",
        description="Detected reliability failures",
        severity="critical",
        status="open",
        detected_at=datetime.now(timezone.utc),
        resolved_at=None,
        details={
            "violations": [
                {
                    "rule_code": "RUN_FAILED",
                    "severity": "critical",
                    "message": "Pipeline reported a failed status",
                    "actual": "failed",
                    "threshold": "succeeded",
                }
            ]
        },
    )


def test_healthy_run_is_stored_without_incident() -> None:
    db = make_session()

    result = ingest_pipeline_run(
        db,
        PIPELINE_ID,
        make_run(),
    )

    assert result.pipeline_run.id == RUN_ID
    assert result.incident is None
    assert result.violations == []
    assert result.duplicate is False
    assert db.add.call_count == 1
    db.commit.assert_called_once()


def test_unhealthy_run_creates_one_incident() -> None:
    db = make_session()
    run = make_run(
        status="failed",
        completed_at=datetime(
            2026,
            7,
            16,
            20,
            25,
            tzinfo=timezone.utc,
        ),
        rows_processed=500,
        quality_checks_failed=2,
    )

    result = ingest_pipeline_run(
        db,
        PIPELINE_ID,
        run,
    )

    assert result.incident is not None
    assert result.incident.pipeline_run_id == RUN_ID
    assert result.incident.source == "reliability-engine"
    assert result.incident.severity == "critical"
    assert result.incident.status == "open"
    assert len(result.violations) == 4
    assert db.add.call_count == 2
    db.commit.assert_called_once()


def test_existing_run_returns_duplicate_result() -> None:
    db = make_session()
    existing_run = make_existing_run()
    existing_incident = make_existing_incident()
    db.scalar.side_effect = [
        existing_run,
        existing_incident,
    ]

    result = ingest_pipeline_run(
        db,
        PIPELINE_ID,
        make_run(),
    )

    assert result.pipeline_run is existing_run
    assert result.incident is existing_incident
    assert result.duplicate is True
    assert len(result.violations) == 1
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_concurrent_duplicate_recovers_existing_result() -> None:
    db = make_session()
    existing_run = make_existing_run()
    existing_incident = make_existing_incident()

    db.scalar.side_effect = [
        None,
        existing_run,
        existing_incident,
    ]
    db.flush.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate run"),
    )

    result = ingest_pipeline_run(
        db,
        PIPELINE_ID,
        make_run(),
    )

    assert result.pipeline_run is existing_run
    assert result.incident is existing_incident
    assert result.duplicate is True
    db.rollback.assert_called_once()


def test_missing_pipeline_raises_not_found() -> None:
    db = make_session()
    db.get.return_value = None

    with pytest.raises(PipelineNotFoundError):
        ingest_pipeline_run(
            db,
            uuid4(),
            make_run(),
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_database_failure_rolls_back_ingestion() -> None:
    db = make_session()
    db.commit.side_effect = SQLAlchemyError(
        "Database unavailable"
    )

    with pytest.raises(
        PipelineRunIngestionError,
        match="Unable to store pipeline run",
    ):
        ingest_pipeline_run(
            db,
            PIPELINE_ID,
            make_run(),
        )

    db.rollback.assert_called_once()