from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.api.pipeline_runs import get_pipeline_run
from backend.app.api.pipelines import (
    list_pipeline_runs,
    list_pipelines,
)
from backend.app.models import Pipeline, PipelineRun


PIPELINE_ID = UUID("11111111-1111-1111-1111-111111111111")
RUN_ID = UUID("22222222-2222-2222-2222-222222222222")


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


def make_pipeline_run() -> PipelineRun:
    return PipelineRun(
        id=RUN_ID,
        pipeline_id=PIPELINE_ID,
        external_run_id="customer-import-2026-07-28",
        status="failed",
        scheduled_at=datetime(
            2026,
            7,
            28,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        started_at=datetime(
            2026,
            7,
            28,
            12,
            8,
            tzinfo=timezone.utc,
        ),
        completed_at=datetime(
            2026,
            7,
            28,
            12,
            30,
            tzinfo=timezone.utc,
        ),
        rows_processed=450,
        quality_checks_failed=2,
        metrics={"rejected_rows": 550},
        error_message="Validation failed",
        logs=["Source file validation failed"],
    )


def test_lists_pipelines_in_query_order() -> None:
    pipeline = make_pipeline()
    db = MagicMock(spec=Session)
    db.scalars.return_value.all.return_value = [pipeline]

    result = list_pipelines(
        db=db,
        limit=25,
        offset=0,
    )

    assert result == [pipeline]
    statement = str(db.scalars.call_args.args[0])
    assert "ORDER BY pipelines.name ASC" in statement
    assert "LIMIT" in statement


def test_list_pipelines_returns_503_on_database_failure() -> None:
    db = MagicMock(spec=Session)
    db.scalars.side_effect = SQLAlchemyError(
        "database unavailable"
    )

    with pytest.raises(HTTPException) as exc_info:
        list_pipelines(
            db=db,
            limit=100,
            offset=0,
        )

    assert exc_info.value.status_code == (
        status.HTTP_503_SERVICE_UNAVAILABLE
    )
    assert exc_info.value.detail == "Unable to retrieve pipelines"


def test_lists_runs_for_existing_pipeline() -> None:
    pipeline = make_pipeline()
    pipeline_run = make_pipeline_run()
    db = MagicMock(spec=Session)
    db.get.return_value = pipeline
    db.scalars.return_value.all.return_value = [pipeline_run]

    result = list_pipeline_runs(
        pipeline_id=PIPELINE_ID,
        db=db,
        limit=50,
        offset=0,
    )

    assert result == [pipeline_run]
    statement = str(db.scalars.call_args.args[0])
    assert "pipeline_runs.pipeline_id" in statement
    assert "pipeline_runs.completed_at DESC" in statement


def test_list_runs_returns_404_for_missing_pipeline() -> None:
    db = MagicMock(spec=Session)
    db.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        list_pipeline_runs(
            pipeline_id=PIPELINE_ID,
            db=db,
            limit=50,
            offset=0,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "Pipeline not found"
    db.scalars.assert_not_called()


def test_gets_pipeline_run_by_id() -> None:
    pipeline_run = make_pipeline_run()
    db = MagicMock(spec=Session)
    db.get.return_value = pipeline_run

    result = get_pipeline_run(
        run_id=RUN_ID,
        db=db,
    )

    assert result is pipeline_run
    db.get.assert_called_once_with(PipelineRun, RUN_ID)


def test_get_pipeline_run_returns_404_when_missing() -> None:
    db = MagicMock(spec=Session)
    db.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_pipeline_run(
            run_id=RUN_ID,
            db=db,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "Pipeline run not found"
