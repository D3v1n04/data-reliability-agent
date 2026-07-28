import json
from copy import deepcopy
from unittest.mock import Mock
from uuid import UUID

import pytest

from backend.app.services.bedrock import BedrockService
from backend.app.services.incident_diagnosis import (
    DIAGNOSIS_SYSTEM_PROMPT,
    DIAGNOSIS_TOOL_CONFIG,
    DIAGNOSIS_TOOL_NAME,
    IncidentDiagnosisGenerationError,
    build_diagnosis_prompt,
    generate_incident_diagnosis,
)
from backend.app.services.incident_memory_store import (
    SimilarIncidentMemory,
)


INCIDENT_ID = UUID("11111111-1111-1111-1111-111111111111")
PRIOR_INCIDENT_ID = UUID(
    "44444444-4444-4444-4444-444444444444"
)


def make_snapshot(
    incident_id: UUID = INCIDENT_ID,
    title: str = "Daily customer import failed",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "incident": {
            "id": str(incident_id),
            "pipeline_run_id": (
                "22222222-2222-2222-2222-222222222222"
            ),
            "source": "reliability-engine",
            "title": title,
            "description": "Reliability rules were violated",
            "severity": "critical",
            "status": "open",
            "detected_at": "2026-07-27T12:08:30+00:00",
            "resolved_at": None,
            "details": {
                "violations": [
                    {
                        "code": "RUN_FAILED",
                        "severity": "critical",
                    }
                ]
            },
        },
        "pipeline": {
            "id": "33333333-3333-3333-3333-333333333333",
            "name": "daily-customer-import",
            "description": "Imports validated customer records",
            "max_duration_seconds": 300,
            "min_rows_processed": 1000,
            "max_start_delay_seconds": 60,
            "enabled": True,
        },
        "run": {
            "id": "22222222-2222-2222-2222-222222222222",
            "external_run_id": "customer-import-2026-07-27",
            "status": "failed",
            "scheduled_at": "2026-07-27T12:00:00+00:00",
            "started_at": "2026-07-27T12:01:30+00:00",
            "completed_at": "2026-07-27T12:08:30+00:00",
            "rows_processed": 250,
            "quality_checks_failed": 2,
            "metrics": {
                "valid_rows": 250,
                "invalid_rows": 50,
            },
            "error_message": "Source file validation failed",
            "logs": [
                {
                    "level": "error",
                    "message": "Two source files were invalid",
                }
            ],
        },
        "observed": {
            "start_delay_seconds": 90.0,
            "duration_seconds": 420.0,
        },
    }


def make_similar_memory() -> SimilarIncidentMemory:
    prior_snapshot = deepcopy(make_snapshot())
    prior_snapshot["incident"]["id"] = str(
        PRIOR_INCIDENT_ID
    )
    prior_snapshot["incident"]["title"] = (
        "Previous customer import failure"
    )

    return SimilarIncidentMemory(
        incident_id=PRIOR_INCIDENT_ID,
        distance=0.12,
        similarity=0.88,
        incident_snapshot=prior_snapshot,
    )


def test_build_diagnosis_prompt_contains_grounded_context() -> None:
    prompt = build_diagnosis_prompt(
        make_snapshot(),
        [make_similar_memory()],
    )
    document = json.loads(prompt)

    assert document["current_incident"]["incident"]["title"] == (
        "Daily customer import failed"
    )
    assert document["similar_incidents"][0][
        "similarity"
    ] == pytest.approx(0.88)
    assert document["similar_incidents"][0][
        "incident"
    ]["incident"]["title"] == (
        "Previous customer import failure"
    )

    assert str(INCIDENT_ID) not in prompt
    assert str(PRIOR_INCIDENT_ID) not in prompt


def test_generates_valid_structured_diagnosis() -> None:
    bedrock_service = Mock(spec=BedrockService)
    bedrock_service.generate_structured_output.return_value = {
        "explanation": (
            "The import failed after source-file validation."
        ),
        "likely_causes": [
            "Invalid source file structure",
            "Unexpected source data values",
        ],
        "recommendations": [
            "Inspect the rejected source files",
            "Compare their schema with the expected contract",
        ],
        "confidence": 0.87,
    }

    result = generate_incident_diagnosis(
        incident_snapshot=make_snapshot(),
        similar_memories=[make_similar_memory()],
        bedrock_service=bedrock_service,
    )

    assert result.confidence == pytest.approx(0.87)
    assert len(result.likely_causes) == 2
    assert len(result.recommendations) == 2

    assert result.evidence["current_incident_id"] == (
        str(INCIDENT_ID)
    )
    assert result.evidence["deterministic_violations"][0][
        "code"
    ] == "RUN_FAILED"
    assert result.evidence["similar_incidents"][0][
        "incident_id"
    ] == str(PRIOR_INCIDENT_ID)

    request = (
        bedrock_service.generate_structured_output.call_args.kwargs
    )

    assert request["system_prompt"] == (
        DIAGNOSIS_SYSTEM_PROMPT
    )
    assert request["tool_name"] == DIAGNOSIS_TOOL_NAME
    assert request["tool_config"] == DIAGNOSIS_TOOL_CONFIG

    schema = request["tool_config"]["tools"][0]["toolSpec"][
        "inputSchema"
    ]["json"]
    assert schema["required"] == [
        "explanation",
        "likely_causes",
        "recommendations",
        "confidence",
    ]
    assert request["tool_config"]["toolChoice"] == {
        "tool": {"name": DIAGNOSIS_TOOL_NAME}
    }
    assert json.loads(request["prompt"])[
        "current_incident"
    ]["run"]["status"] == "failed"


def test_generates_diagnosis_without_prior_memories() -> None:
    bedrock_service = Mock(spec=BedrockService)
    bedrock_service.generate_structured_output.return_value = {
        "explanation": "The run failed validation.",
        "likely_causes": [
            "Invalid input data",
        ],
        "recommendations": [
            "Inspect validation errors",
        ],
        "confidence": 0.65,
    }

    result = generate_incident_diagnosis(
        incident_snapshot=make_snapshot(),
        similar_memories=[],
        bedrock_service=bedrock_service,
    )

    assert result.evidence["similar_incidents"] == []

    prompt = json.loads(
        bedrock_service.generate_structured_output.call_args.kwargs[
            "prompt"
        ]
    )
    assert prompt["similar_incidents"] == []


def test_rejects_non_object_structured_response() -> None:
    bedrock_service = Mock(spec=BedrockService)
    bedrock_service.generate_structured_output.return_value = []

    with pytest.raises(
        IncidentDiagnosisGenerationError,
        match="structured JSON object",
    ):
        generate_incident_diagnosis(
            incident_snapshot=make_snapshot(),
            similar_memories=[],
            bedrock_service=bedrock_service,
        )


def test_rejects_invalid_diagnosis_structure() -> None:
    bedrock_service = Mock(spec=BedrockService)
    bedrock_service.generate_structured_output.return_value = {
        "explanation": "The run failed validation.",
        "likely_causes": [
            "Invalid input data",
        ],
        "recommendations": [
            "Inspect validation errors",
        ],
        "confidence": 1.5,
        "unexpected_field": "not allowed",
    }

    with pytest.raises(
        IncidentDiagnosisGenerationError,
        match="invalid diagnosis structure",
    ):
        generate_incident_diagnosis(
            incident_snapshot=make_snapshot(),
            similar_memories=[],
            bedrock_service=bedrock_service,
        )
