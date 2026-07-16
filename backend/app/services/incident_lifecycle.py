from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models import Incident
from backend.app.schemas.incident import IncidentStatus


class IncidentNotFoundError(Exception):
    pass


class InvalidIncidentTransitionError(Exception):
    pass


class IncidentLifecycleError(Exception):
    pass


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {
        "investigating",
        "resolved",
    },
    "investigating": {
        "resolved",
    },
    "resolved": set(),
}


def update_incident_status(
    db: Session,
    incident_id: UUID,
    new_status: IncidentStatus,
) -> Incident:
    """Apply a controlled lifecycle transition to an incident."""
    try:
        incident = db.get(Incident, incident_id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise IncidentLifecycleError(
            "Unable to retrieve incident"
        ) from exc

    if incident is None:
        raise IncidentNotFoundError

    if incident.status == new_status:
        return incident

    allowed_statuses = ALLOWED_TRANSITIONS.get(
        incident.status,
        set(),
    )

    if new_status not in allowed_statuses:
        raise InvalidIncidentTransitionError(
            f"Cannot transition incident from "
            f"{incident.status} to {new_status}"
        )

    incident.status = new_status

    if new_status == "resolved":
        incident.resolved_at = datetime.now(timezone.utc)
    else:
        incident.resolved_at = None

    try:
        db.commit()
        db.refresh(incident)
    except SQLAlchemyError as exc:
        db.rollback()
        raise IncidentLifecycleError(
            "Unable to update incident"
        ) from exc

    return incident