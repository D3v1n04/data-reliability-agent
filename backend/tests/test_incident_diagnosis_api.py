import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.api.incidents import (
    diagnose_incident,
    get_incident_diagnosis,
)
from backend.app.models import IncidentDiagnosis
from backend.app.services.bedrock import BedrockService
from backend.app.services.incident_diagnosis_workflow import (
    IncidentDiagnosisWorkflowError,
    IncidentNotDiagnosableError,
    IncidentNotFoundError,
)


INCIDENT_ID = UUID("11111111-1111-1111-1111-111111111111")
DIAGNOSIS_ID = UUID(
    "55555555-5555-5555-5555-555555555555"
)


def make_diagnosis() -> IncidentDiagnosis:
    diagnosis = IncidentDiagnosis(
        incident_id=INCIDENT_ID,
        explanation="The source data failed validation.",
        likely_causes=[
            "Invalid source file structure",
        ],
        recommendations=[
            "Inspect the rejected source files",
        ],
        confidence=0.87,
        evidence={
            "current_incident_id": str(INCIDENT_ID),
            "deterministic_violations": [
                {
                    "code": "RUN_FAILED",
                    "severity": "critical",
                }
            ],
            "similar_incidents": [],
        },
        text_model_id="amazon.nova-lite-v1:0",
    )

    diagnosis.id = DIAGNOSIS_ID
    diagnosis.created_at = datetime(
        2026,
        7,
        27,
        12,
        15,
        tzinfo=timezone.utc,
    )

    return diagnosis


def test_post_creates_incident_diagnosis() -> None:
    diagnosis = make_diagnosis()
    workflow_result = SimpleNamespace(
        diagnosis=diagnosis,
        created=True,
    )

    db = Mock(spec=Session)
    bedrock_service = Mock(spec=BedrockService)
    response = Response()

    with patch(
        (
            "backend.app.api.incidents."
            "get_or_create_incident_diagnosis"
        ),
        return_value=workflow_result,
    ) as workflow:
        result = diagnose_incident(
            incident_id=INCIDENT_ID,
            response=response,
            db=db,
            bedrock_service=bedrock_service,
        )

    assert result is diagnosis
    assert response.status_code == status.HTTP_201_CREATED

    workflow.assert_called_once_with(
        db=db,
        incident_id=INCIDENT_ID,
        bedrock_service=bedrock_service,
    )


def test_post_returns_existing_diagnosis() -> None:
    diagnosis = make_diagnosis()
    workflow_result = SimpleNamespace(
        diagnosis=diagnosis,
        created=False,
    )

    db = Mock(spec=Session)
    bedrock_service = Mock(spec=BedrockService)
    response = Response()

    with patch(
        (
            "backend.app.api.incidents."
            "get_or_create_incident_diagnosis"
        ),
        return_value=workflow_result,
    ):
        result = diagnose_incident(
            incident_id=INCIDENT_ID,
            response=response,
            db=db,
            bedrock_service=bedrock_service,
        )

    assert result is diagnosis
    assert response.status_code == status.HTTP_200_OK


def test_post_returns_404_for_missing_incident() -> None:
    db = Mock(spec=Session)
    bedrock_service = Mock(spec=BedrockService)
    response = Response()

    with patch(
        (
            "backend.app.api.incidents."
            "get_or_create_incident_diagnosis"
        ),
        side_effect=IncidentNotFoundError(
            "Incident was not found"
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            diagnose_incident(
                incident_id=INCIDENT_ID,
                response=response,
                db=db,
                bedrock_service=bedrock_service,
            )

    assert exc_info.value.status_code == (
        status.HTTP_404_NOT_FOUND
    )
    assert exc_info.value.detail == "Incident not found"


def test_post_returns_409_for_incident_without_run() -> None:
    db = Mock(spec=Session)
    bedrock_service = Mock(spec=BedrockService)
    response = Response()

    with patch(
        (
            "backend.app.api.incidents."
            "get_or_create_incident_diagnosis"
        ),
        side_effect=IncidentNotDiagnosableError(
            "Incident is not associated with a pipeline run"
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            diagnose_incident(
                incident_id=INCIDENT_ID,
                response=response,
                db=db,
                bedrock_service=bedrock_service,
            )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail == (
        "Incident is not associated with a pipeline run"
    )


def test_post_returns_503_and_logs_workflow_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    db = Mock(spec=Session)
    bedrock_service = Mock(spec=BedrockService)
    response = Response()
    underlying_error = ValueError("underlying failure")

    try:
        raise IncidentDiagnosisWorkflowError(
            "Unable to generate incident diagnosis"
        ) from underlying_error
    except IncidentDiagnosisWorkflowError as workflow_error:
        chained_error = workflow_error

    with (
        caplog.at_level(
            logging.ERROR,
            logger="backend.app.api.incidents",
        ),
        patch(
            (
                "backend.app.api.incidents."
                "get_or_create_incident_diagnosis"
            ),
            side_effect=chained_error,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            diagnose_incident(
                incident_id=INCIDENT_ID,
                response=response,
                db=db,
                bedrock_service=bedrock_service,
            )

    assert exc_info.value.status_code == (
        status.HTTP_503_SERVICE_UNAVAILABLE
    )
    assert exc_info.value.detail == "Unable to diagnose incident"
    assert len(caplog.records) == 1
    assert caplog.records[0].exc_info is not None
    assert str(INCIDENT_ID) in caplog.records[0].getMessage()


def test_get_returns_stored_diagnosis() -> None:
    diagnosis = make_diagnosis()

    db = Mock(spec=Session)
    db.scalar.return_value = diagnosis

    result = get_incident_diagnosis(
        incident_id=INCIDENT_ID,
        db=db,
    )

    assert result is diagnosis
    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]
    statement_text = str(statement)

    assert "incident_diagnoses.incident_id" in statement_text


def test_get_returns_404_when_diagnosis_is_missing() -> None:
    db = Mock(spec=Session)
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_incident_diagnosis(
            incident_id=INCIDENT_ID,
            db=db,
        )

    assert exc_info.value.status_code == (
        status.HTTP_404_NOT_FOUND
    )
    assert exc_info.value.detail == (
        "Incident diagnosis not found"
    )


def test_get_returns_503_when_database_fails() -> None:
    db = Mock(spec=Session)
    db.scalar.side_effect = SQLAlchemyError(
        "database unavailable"
    )

    with pytest.raises(HTTPException) as exc_info:
        get_incident_diagnosis(
            incident_id=INCIDENT_ID,
            db=db,
        )

    assert exc_info.value.status_code == (
        status.HTTP_503_SERVICE_UNAVAILABLE
    )
    assert exc_info.value.detail == (
        "Unable to retrieve incident diagnosis"
    )
