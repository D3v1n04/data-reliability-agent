from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.session import get_db
from backend.app.models import Incident
from backend.app.schemas import (
    IncidentCreate,
    IncidentRead,
    IncidentStatusUpdate,
)
from backend.app.schemas.incident import IncidentStatus, Severity

from backend.app.services.incident_lifecycle import (
    IncidentLifecycleError,
    IncidentNotFoundError,
    InvalidIncidentTransitionError,
    update_incident_status,
)


router = APIRouter(
    prefix="/api/incidents",
    tags=["incidents"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


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
    except IncidentNotFoundError as exc:
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