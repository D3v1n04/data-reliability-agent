import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.session import get_db
from backend.app.models import Incident, IncidentDiagnosis
from backend.app.schemas import (
    IncidentCreate,
    IncidentDiagnosisRead,
    IncidentRead,
    IncidentStatusUpdate,
)
from backend.app.schemas.incident import IncidentStatus, Severity

from backend.app.services.incident_lifecycle import (
    IncidentLifecycleError,
    IncidentNotFoundError as IncidentLifecycleNotFoundError,
    InvalidIncidentTransitionError,
    update_incident_status,
)

from backend.app.services.bedrock import (
    BedrockService,
    get_bedrock_service,
)
from backend.app.core.observability import emit_dependency_failure
from backend.app.services.incident_diagnosis_workflow import (
    IncidentDiagnosisWorkflowError,
    IncidentNotDiagnosableError,
    IncidentNotFoundError as DiagnosisIncidentNotFoundError,
    get_or_create_incident_diagnosis,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/incidents",
    tags=["incidents"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]
BedrockServiceDependency = Annotated[
    BedrockService,
    Depends(get_bedrock_service),
]


@router.post(
    "",
    response_model=IncidentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_incident(
    incident_data: IncidentCreate,
    db: DatabaseSession,
) -> Incident:
    incident = Incident(**incident_data.model_dump())

    try:
        db.add(incident)
        db.commit()
        db.refresh(incident)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to save incident",
        ) from exc

    return incident


@router.get(
    "",
    response_model=list[IncidentRead],
)
def list_incidents(
    db: DatabaseSession,
    incident_status: Annotated[
        IncidentStatus | None,
        Query(alias="status"),
    ] = None,
    severity: Severity | None = None,
    source: Annotated[
        str | None,
        Query(min_length=1, max_length=100),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> list[Incident]:
    statement = select(Incident)

    if incident_status is not None:
        statement = statement.where(
            Incident.status == incident_status
        )

    if severity is not None:
        statement = statement.where(
            Incident.severity == severity
        )

    if source is not None:
        statement = statement.where(
            Incident.source == source
        )

    statement = (
        statement
        .order_by(
            Incident.detected_at.desc(),
            Incident.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    try:
        incidents = db.scalars(statement).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve incidents",
        ) from exc

    return list(incidents)


@router.patch(
    "/{incident_id}/status",
    response_model=IncidentRead,
)
def change_incident_status(
    incident_id: UUID,
    status_data: IncidentStatusUpdate,
    db: DatabaseSession,
) -> Incident:
    try:
        return update_incident_status(
            db,
            incident_id,
            status_data.status,
        )
    except IncidentLifecycleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        ) from exc
    except InvalidIncidentTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IncidentLifecycleError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to update incident",
        ) from exc


@router.post(
    "/{incident_id}/diagnosis",
    response_model=IncidentDiagnosisRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": IncidentDiagnosisRead,
            "description": "Existing incident diagnosis",
        },
    },
)
def diagnose_incident(
    incident_id: UUID,
    response: Response,
    db: DatabaseSession,
    bedrock_service: BedrockServiceDependency,
) -> IncidentDiagnosis:
    try:
        result = get_or_create_incident_diagnosis(
            db=db,
            incident_id=incident_id,
            bedrock_service=bedrock_service,
        )
    except DiagnosisIncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        ) from exc
    except IncidentNotDiagnosableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IncidentDiagnosisWorkflowError as exc:
        failure_category = (
            exc.category
            if exc.category in {"bedrock", "database", "diagnosis"}
            else "diagnosis"
        )
        logger.error(
            "incident_diagnosis_failed",
            extra={
                "event": "dependency_failure",
                "failure_category": failure_category,
            },
        )
        emit_dependency_failure(failure_category)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to diagnose incident",
        ) from None

    response.status_code = (
        status.HTTP_201_CREATED
        if result.created
        else status.HTTP_200_OK
    )

    return result.diagnosis


@router.get(
    "/{incident_id}/diagnosis",
    response_model=IncidentDiagnosisRead,
)
def get_incident_diagnosis(
    incident_id: UUID,
    db: DatabaseSession,
) -> IncidentDiagnosis:
    statement = select(IncidentDiagnosis).where(
        IncidentDiagnosis.incident_id == incident_id
    )

    try:
        diagnosis = db.scalar(statement)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve incident diagnosis",
        ) from exc

    if diagnosis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident diagnosis not found",
        )

    return diagnosis


@router.get(
    "/{incident_id}",
    response_model=IncidentRead,
)
def get_incident(
    incident_id: UUID,
    db: DatabaseSession,
) -> Incident:
    try:
        incident = db.get(Incident, incident_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve incident",
        ) from exc

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return incident
