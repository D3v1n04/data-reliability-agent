from dataclasses import asdict, dataclass

from backend.app.models import Pipeline
from backend.app.schemas.incident import Severity
from backend.app.schemas.pipeline_run import (
    PipelineRunCreate,
    RuleCode,
)


@dataclass(frozen=True)
class RuleViolation:
    rule_code: RuleCode
    severity: Severity
    message: str
    actual: str | int | float | None = None
    threshold: str | int | float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


SEVERITY_RANK: dict[Severity, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def evaluate_pipeline_run(
    pipeline: Pipeline,
    run: PipelineRunCreate,
) -> list[RuleViolation]:
    """Evaluate one completed pipeline run using deterministic rules."""
    if not pipeline.enabled:
        return []

    violations: list[RuleViolation] = []

    if run.status == "failed":
        violations.append(
            RuleViolation(
                rule_code="RUN_FAILED",
                severity="critical",
                message="Pipeline reported a failed status",
                actual=run.status,
                threshold="succeeded",
            )
        )

    if run.status == "cancelled":
        violations.append(
            RuleViolation(
                rule_code="RUN_CANCELLED",
                severity="high",
                message="Pipeline run was cancelled",
                actual=run.status,
                threshold="succeeded",
            )
        )

    start_delay_seconds = (
        run.started_at - run.scheduled_at
    ).total_seconds()

    if (
        pipeline.max_start_delay_seconds is not None
        and start_delay_seconds > pipeline.max_start_delay_seconds
    ):
        violations.append(
            RuleViolation(
                rule_code="START_DELAY_EXCEEDED",
                severity="medium",
                message="Pipeline started later than its configured limit",
                actual=round(start_delay_seconds, 3),
                threshold=pipeline.max_start_delay_seconds,
            )
        )

    duration_seconds = (
        run.completed_at - run.started_at
    ).total_seconds()

    if (
        pipeline.max_duration_seconds is not None
        and duration_seconds > pipeline.max_duration_seconds
    ):
        violations.append(
            RuleViolation(
                rule_code="DURATION_EXCEEDED",
                severity="high",
                message="Pipeline runtime exceeded its configured limit",
                actual=round(duration_seconds, 3),
                threshold=pipeline.max_duration_seconds,
            )
        )

    if pipeline.min_rows_processed is not None:
        if run.rows_processed is None:
            violations.append(
                RuleViolation(
                    rule_code="ROW_COUNT_MISSING",
                    severity="high",
                    message="Pipeline did not report its processed row count",
                    threshold=pipeline.min_rows_processed,
                )
            )
        elif run.rows_processed < pipeline.min_rows_processed:
            violations.append(
                RuleViolation(
                    rule_code="ROW_COUNT_BELOW_MINIMUM",
                    severity="high",
                    message="Pipeline processed fewer rows than required",
                    actual=run.rows_processed,
                    threshold=pipeline.min_rows_processed,
                )
            )

    if run.quality_checks_failed > 0:
        violations.append(
            RuleViolation(
                rule_code="QUALITY_CHECKS_FAILED",
                severity="high",
                message="One or more pipeline quality checks failed",
                actual=run.quality_checks_failed,
                threshold=0,
            )
        )

    return violations


def highest_severity(
    violations: list[RuleViolation],
) -> Severity | None:
    """Return the most severe level found among the violations."""
    if not violations:
        return None

    return max(
        violations,
        key=lambda violation: SEVERITY_RANK[violation.severity],
    ).severity