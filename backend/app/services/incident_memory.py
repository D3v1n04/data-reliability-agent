import json
from copy import deepcopy
from datetime import datetime
from typing import Any

from backend.app.models import Incident, Pipeline, PipelineRun


def _isoformat(value: datetime | None) -> str | None:
    """Convert an optional timestamp into a stable ISO string."""
    if value is None:
        return None

    return value.isoformat()


def _elapsed_seconds(
    later: datetime | None,
    earlier: datetime | None,
) -> float | None:
    """Calculate elapsed seconds when both timestamps exist."""
    if later is None or earlier is None:
        return None

    return (later - earlier).total_seconds()


def build_incident_snapshot(
    incident: Incident,
    pipeline_run: PipelineRun,
    pipeline: Pipeline,
) -> dict[str, Any]:
    """Build immutable evidence from deterministic incident data."""
    if incident.pipeline_run_id != pipeline_run.id:
        raise ValueError(
            "Incident does not belong to the supplied pipeline run"
        )

    if pipeline_run.pipeline_id != pipeline.id:
        raise ValueError(
            "Pipeline run does not belong to the supplied pipeline"
        )

    return {
        "schema_version": 1,
        "incident": {
            "id": str(incident.id),
            "pipeline_run_id": str(incident.pipeline_run_id),
            "source": incident.source,
            "title": incident.title,
            "description": incident.description,
            "severity": incident.severity,
            "status": incident.status,
            "detected_at": _isoformat(incident.detected_at),
            "resolved_at": _isoformat(incident.resolved_at),
            "details": deepcopy(incident.details),
        },
        "pipeline": {
            "id": str(pipeline.id),
            "name": pipeline.name,
            "description": pipeline.description,
            "max_duration_seconds": (
                pipeline.max_duration_seconds
            ),
            "min_rows_processed": pipeline.min_rows_processed,
            "max_start_delay_seconds": (
                pipeline.max_start_delay_seconds
            ),
            "enabled": pipeline.enabled,
        },
        "run": {
            "id": str(pipeline_run.id),
            "external_run_id": pipeline_run.external_run_id,
            "status": pipeline_run.status,
            "scheduled_at": _isoformat(
                pipeline_run.scheduled_at
            ),
            "started_at": _isoformat(pipeline_run.started_at),
            "completed_at": _isoformat(
                pipeline_run.completed_at
            ),
            "rows_processed": pipeline_run.rows_processed,
            "quality_checks_failed": (
                pipeline_run.quality_checks_failed
            ),
            "metrics": deepcopy(pipeline_run.metrics),
            "error_message": pipeline_run.error_message,
            "logs": deepcopy(pipeline_run.logs),
        },
        "observed": {
            "start_delay_seconds": _elapsed_seconds(
                pipeline_run.started_at,
                pipeline_run.scheduled_at,
            ),
            "duration_seconds": _elapsed_seconds(
                pipeline_run.completed_at,
                pipeline_run.started_at,
            ),
        },
    }


def build_embedding_input(
    snapshot: dict[str, Any],
) -> str:
    """Build stable semantic input without unique identifiers."""
    incident = snapshot["incident"]
    pipeline = snapshot["pipeline"]
    pipeline_run = snapshot["run"]
    observed = snapshot["observed"]

    embedding_document = {
        "pipeline": {
            "name": pipeline["name"],
            "description": pipeline["description"],
            "max_duration_seconds": (
                pipeline["max_duration_seconds"]
            ),
            "min_rows_processed": (
                pipeline["min_rows_processed"]
            ),
            "max_start_delay_seconds": (
                pipeline["max_start_delay_seconds"]
            ),
        },
        "incident": {
            "source": incident["source"],
            "title": incident["title"],
            "description": incident["description"],
            "severity": incident["severity"],
            "details": incident["details"],
        },
        "run": {
            "status": pipeline_run["status"],
            "rows_processed": pipeline_run["rows_processed"],
            "quality_checks_failed": (
                pipeline_run["quality_checks_failed"]
            ),
            "metrics": pipeline_run["metrics"],
            "error_message": pipeline_run["error_message"],
            "logs": pipeline_run["logs"],
            "start_delay_seconds": (
                observed["start_delay_seconds"]
            ),
            "duration_seconds": observed["duration_seconds"],
        },
    }

    return json.dumps(
        embedding_document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )