from datetime import datetime, timezone

from backend.app.models import Pipeline
from backend.app.schemas import PipelineRunCreate
from backend.app.services.reliability import (
    evaluate_pipeline_run,
    highest_severity,
)


SCHEDULED_AT = datetime(
    2026,
    7,
    16,
    20,
    0,
    tzinfo=timezone.utc,
)


def make_pipeline(**overrides: object) -> Pipeline:
    data: dict[str, object] = {
        "name": "daily-customer-import",
        "description": "Imports customer data",
        "max_duration_seconds": 900,
        "min_rows_processed": 1000,
        "max_start_delay_seconds": 300,
        "enabled": True,
    }
    data.update(overrides)

    return Pipeline(**data)


def make_run(**overrides: object) -> PipelineRunCreate:
    data: dict[str, object] = {
        "external_run_id": "customer-import-2026-07-16",
        "status": "succeeded",
        "scheduled_at": SCHEDULED_AT,
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
        "metrics": {
            "source_files": 4,
        },
        "logs": [
            "Customer import started",
            "Customer import completed",
        ],
    }
    data.update(overrides)

    return PipelineRunCreate(**data)


def test_healthy_run_has_no_violations() -> None:
    pipeline = make_pipeline()
    run = make_run()

    violations = evaluate_pipeline_run(pipeline, run)

    assert violations == []
    assert highest_severity(violations) is None


def test_failed_run_is_critical() -> None:
    pipeline = make_pipeline()
    run = make_run(
        status="failed",
        error_message="Source database connection failed",
    )

    violations = evaluate_pipeline_run(pipeline, run)

    assert [violation.rule_code for violation in violations] == [
        "RUN_FAILED"
    ]
    assert highest_severity(violations) == "critical"


def test_late_run_is_detected() -> None:
    pipeline = make_pipeline()
    run = make_run(
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
            20,
            tzinfo=timezone.utc,
        ),
    )

    violations = evaluate_pipeline_run(pipeline, run)

    assert [violation.rule_code for violation in violations] == [
        "START_DELAY_EXCEEDED"
    ]
    assert violations[0].actual == 600
    assert violations[0].threshold == 300


def test_missing_row_count_is_detected() -> None:
    pipeline = make_pipeline()
    run = make_run(rows_processed=None)

    violations = evaluate_pipeline_run(pipeline, run)

    assert [violation.rule_code for violation in violations] == [
        "ROW_COUNT_MISSING"
    ]


def test_multiple_failures_are_combined() -> None:
    pipeline = make_pipeline()
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
        error_message="Two validation checks failed",
    )

    violations = evaluate_pipeline_run(pipeline, run)
    rule_codes = {
        violation.rule_code
        for violation in violations
    }

    assert rule_codes == {
        "RUN_FAILED",
        "DURATION_EXCEEDED",
        "ROW_COUNT_BELOW_MINIMUM",
        "QUALITY_CHECKS_FAILED",
    }
    assert highest_severity(violations) == "critical"


def test_cancelled_run_is_high_severity() -> None:
    pipeline = make_pipeline()
    run = make_run(status="cancelled")

    violations = evaluate_pipeline_run(pipeline, run)

    assert [violation.rule_code for violation in violations] == [
        "RUN_CANCELLED"
    ]
    assert highest_severity(violations) == "high"


def test_disabled_pipeline_skips_detection() -> None:
    pipeline = make_pipeline(enabled=False)
    run = make_run(
        status="failed",
        rows_processed=0,
        quality_checks_failed=3,
    )

    violations = evaluate_pipeline_run(pipeline, run)

    assert violations == []