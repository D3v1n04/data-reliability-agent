import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from backend.app.services.incident_memory import (
    build_embedding_input,
    build_incident_snapshot,
)


INCIDENT_ID = UUID("11111111-1111-1111-1111-111111111111")
RUN_ID = UUID("22222222-2222-2222-2222-222222222222")
PIPELINE_ID = UUID("33333333-3333-3333-3333-333333333333")


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
        description="The pipeline run violated reliability rules",
        severity="critical",
        status="open",
        detected_at=completed_at,
        resolved_at=None,
        details={
            "violations": [
                {
                    "code": "RUN_FAILED",
                    "severity": "critical",
                },
                {
                    "code": "DURATION_EXCEEDED",
                    "severity": "high",
                },
            ]
        },
    )

    return incident, pipeline_run, pipeline


def test_build_incident_snapshot_preserves_evidence() -> None:
    incident, pipeline_run, pipeline = make_context()

    snapshot = build_incident_snapshot(
        incident,
        pipeline_run,
        pipeline,
    )

    assert snapshot["schema_version"] == 1
    assert snapshot["incident"]["id"] == str(INCIDENT_ID)
    assert snapshot["pipeline"]["id"] == str(PIPELINE_ID)
    assert snapshot["run"]["id"] == str(RUN_ID)

    assert snapshot["observed"] == {
        "start_delay_seconds": 90.0,
        "duration_seconds": 420.0,
    }

    assert snapshot["incident"]["details"]["violations"][0][
        "code"
    ] == "RUN_FAILED"


def test_build_incident_snapshot_rejects_wrong_run() -> None:
    incident, pipeline_run, pipeline = make_context()
    incident.pipeline_run_id = uuid4()

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        build_incident_snapshot(
            incident,
            pipeline_run,
            pipeline,
        )


def test_build_incident_snapshot_rejects_wrong_pipeline() -> None:
    incident, pipeline_run, pipeline = make_context()
    pipeline_run.pipeline_id = uuid4()

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        build_incident_snapshot(
            incident,
            pipeline_run,
            pipeline,
        )


def test_embedding_input_contains_operational_evidence() -> None:
    incident, pipeline_run, pipeline = make_context()

    snapshot = build_incident_snapshot(
        incident,
        pipeline_run,
        pipeline,
    )
    embedding_input = build_embedding_input(snapshot)
    document = json.loads(embedding_input)

    assert document["pipeline"]["name"] == (
        "daily-customer-import"
    )
    assert document["run"]["duration_seconds"] == 420.0
    assert document["run"]["error_message"] == (
        "Source file validation failed"
    )
    assert document["incident"]["details"]["violations"][0][
        "code"
    ] == "RUN_FAILED"

    assert str(INCIDENT_ID) not in embedding_input
    assert str(RUN_ID) not in embedding_input
    assert str(PIPELINE_ID) not in embedding_input


def test_embedding_input_is_deterministic() -> None:
    incident, pipeline_run, pipeline = make_context()

    first_snapshot = build_incident_snapshot(
        incident,
        pipeline_run,
        pipeline,
    )
    second_snapshot = deepcopy(first_snapshot)

    first_snapshot["run"]["metrics"] = {
        "valid_rows": 250,
        "invalid_rows": 50,
    }
    second_snapshot["run"]["metrics"] = {
        "invalid_rows": 50,
        "valid_rows": 250,
    }

    assert build_embedding_input(
        first_snapshot
    ) == build_embedding_input(second_snapshot)