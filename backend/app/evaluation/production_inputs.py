"""Synthetic production-shaped inputs for offline diagnosis evaluation.

This adapter prepares inputs accepted by the production prompt builder. It
does not generate or evaluate diagnoses and does not call external services.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_OID, UUID, uuid5

from backend.app.evaluation.corpus import (
    DIAGNOSIS_EVALUATION_CORPUS,
    DiagnosisEvaluationScenario,
)
from backend.app.services.incident_memory_store import (
    SimilarIncidentMemory,
)


@dataclass(frozen=True)
class ScenarioProductionInput:
    """A synthetic snapshot and historical context for one scenario."""

    scenario_name: str
    incident_snapshot: dict[str, Any]
    similar_memories: tuple[SimilarIncidentMemory, ...]


_RULE_SEVERITY = {
    "RUN_FAILED": "critical",
    "START_DELAY_EXCEEDED": "medium",
    "DURATION_EXCEEDED": "high",
    "ROW_COUNT_BELOW_MINIMUM": "high",
    "QUALITY_CHECKS_FAILED": "high",
    "RUN_CANCELLED": "high",
}

_SEVERITY_RANK = {
    "medium": 0,
    "high": 1,
    "critical": 2,
}

_BASE_TIME = datetime(
    2026,
    1,
    1,
    12,
    0,
    tzinfo=timezone.utc,
)


def _synthetic_uuid(
    kind: str,
    scenario_index: int,
    item_index: int = 0,
) -> UUID:
    return uuid5(
        NAMESPACE_OID,
        f"phase-7-evaluation:{kind}:{scenario_index}:{item_index}",
    )


def _violation_entries(
    deterministic_facts: tuple[str, ...],
) -> list[dict[str, str]]:
    return [
        {
            "code": rule,
            "severity": _RULE_SEVERITY[rule],
        }
        for rule in deterministic_facts
    ]


def _build_snapshot(
    scenario: DiagnosisEvaluationScenario,
    scenario_index: int,
    *,
    incident_id: UUID,
    pipeline_id: UUID,
    run_id: UUID,
    evidence: tuple[str, ...],
) -> dict[str, Any]:
    facts = set(scenario.deterministic_facts)
    violations = _violation_entries(scenario.deterministic_facts)
    incident_severity = max(
        (violation["severity"] for violation in violations),
        key=_SEVERITY_RANK.__getitem__,
    )
    max_duration_seconds = 300
    max_start_delay_seconds = 60
    min_rows_processed = 1000
    start_delay_seconds = (
        max_start_delay_seconds + 30
        if "START_DELAY_EXCEEDED" in facts
        else 30
    )
    duration_seconds = (
        max_duration_seconds + 120
        if "DURATION_EXCEEDED" in facts
        else 180
    )
    rows_processed = (
        min_rows_processed - 250
        if "ROW_COUNT_BELOW_MINIMUM" in facts
        else min_rows_processed
    )
    quality_checks_failed = (
        2 if "QUALITY_CHECKS_FAILED" in facts else 0
    )
    run_status = "succeeded"
    if "RUN_FAILED" in facts:
        run_status = "failed"
    elif "RUN_CANCELLED" in facts:
        run_status = "cancelled"

    scheduled_at = _BASE_TIME + timedelta(days=scenario_index)
    started_at = scheduled_at + timedelta(seconds=start_delay_seconds)
    completed_at = started_at + timedelta(seconds=duration_seconds)
    logs = [
        {
            "level": "warning",
            "message": (
                f'Quoted untrusted evidence: "{entry}"'
            ),
        }
        for entry in evidence
    ]

    return {
        "schema_version": 1,
        "incident": {
            "id": str(incident_id),
            "pipeline_run_id": str(run_id),
            "source": "offline-synthetic-source",
            "title": f"Synthetic evaluation scenario {scenario_index}",
            "description": (
                "Synthetic production-shaped evidence for offline evaluation."
            ),
            "severity": incident_severity,
            "status": "open",
            "detected_at": scheduled_at.isoformat(),
            "resolved_at": None,
            "details": {
                "violations": violations,
            },
        },
        "pipeline": {
            "id": str(pipeline_id),
            "name": f"synthetic-evaluation-pipeline-{scenario_index}",
            "description": "Synthetic pipeline for offline evaluation.",
            "max_duration_seconds": max_duration_seconds,
            "min_rows_processed": min_rows_processed,
            "max_start_delay_seconds": max_start_delay_seconds,
            "enabled": True,
        },
        "run": {
            "id": str(run_id),
            "external_run_id": (
                f"synthetic-evaluation-run-{scenario_index}"
            ),
            "status": run_status,
            "scheduled_at": scheduled_at.isoformat(),
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "rows_processed": rows_processed,
            "quality_checks_failed": quality_checks_failed,
            "metrics": {
                "valid_rows": rows_processed,
                "invalid_rows": quality_checks_failed * 10,
            },
            "error_message": (
                "Synthetic run evidence reflects deterministic violations."
                if scenario.deterministic_facts
                else None
            ),
            "logs": logs,
        },
        "observed": {
            "start_delay_seconds": float(start_delay_seconds),
            "duration_seconds": float(duration_seconds),
        },
    }


def build_scenario_production_input(
    scenario: DiagnosisEvaluationScenario,
    scenario_index: int,
) -> ScenarioProductionInput:
    """Build one synthetic production-shaped scenario input."""
    incident_id = _synthetic_uuid("incident", scenario_index)
    pipeline_id = _synthetic_uuid("pipeline", scenario_index)
    run_id = _synthetic_uuid("run", scenario_index)
    snapshot = _build_snapshot(
        scenario,
        scenario_index,
        incident_id=incident_id,
        pipeline_id=pipeline_id,
        run_id=run_id,
        evidence=scenario.untrusted_evidence,
    )
    similar_memories = tuple(
        SimilarIncidentMemory(
            incident_id=_synthetic_uuid(
                "similar-incident",
                scenario_index,
                context_index,
            ),
            distance=0.2 + context_index * 0.1,
            similarity=0.8 - context_index * 0.1,
            incident_snapshot=_build_snapshot(
                scenario,
                scenario_index,
                incident_id=_synthetic_uuid(
                    "similar-incident",
                    scenario_index,
                    context_index,
                ),
                pipeline_id=_synthetic_uuid(
                    "similar-pipeline",
                    scenario_index,
                    context_index,
                ),
                run_id=_synthetic_uuid(
                    "similar-run",
                    scenario_index,
                    context_index,
                ),
                evidence=(context,),
            ),
        )
        for context_index, context in enumerate(
            scenario.similar_incident_context
        )
    )

    return ScenarioProductionInput(
        scenario_name=scenario.name,
        incident_snapshot=snapshot,
        similar_memories=similar_memories,
    )


def build_corpus_production_inputs() -> tuple[ScenarioProductionInput, ...]:
    """Build synthetic inputs in canonical corpus order."""
    return tuple(
        build_scenario_production_input(scenario, scenario_index)
        for scenario_index, scenario in enumerate(
            DIAGNOSIS_EVALUATION_CORPUS
        )
    )
