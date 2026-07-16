from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models import Incident
from backend.app.services.incident_lifecycle import (
    IncidentLifecycleError,
    IncidentNotFoundError,
    InvalidIncidentTransitionError,
    update_incident_status,
)


def make_incident(status: str = "open") -> Incident:
    return Incident(
        id=uuid4(),
        pipeline_run_id=None,
        source="reliability-engine",
        title="Test reliability incident",
        description="Incident used for lifecycle testing",
        severity="high",
        status=status,
        detected_at=datetime.now(timezone.utc),
        resolved_at=None,
        details={},
    )


def make_session(incident: Incident | None) -> MagicMock:
    db = MagicMock(spec=Session)
    db.get.return_value = incident

    return db


def test_open_incident_can_move_to_investigating() -> None:
    incident = make_incident(status="open")
    db = make_session(incident)

    result = update_incident_status(
        db,
        incident.id,
        "investigating",
    )

    assert result is incident
    assert incident.status == "investigating"
    assert incident.resolved_at is None
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(incident)


def test_investigating_incident_can_be_resolved() -> None:
    incident = make_incident(status="investigating")
    db = make_session(incident)

    result = update_incident_status(
        db,
        incident.id,
        "resolved",
    )

    assert result is incident
    assert incident.status == "resolved"
    assert incident.resolved_at is not None
    assert incident.resolved_at.tzinfo is not None
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(incident)


def test_resolved_incident_cannot_move_backward() -> None:
    incident = make_incident(status="resolved")
    db = make_session(incident)

    with pytest.raises(
        InvalidIncidentTransitionError,
        match="resolved to investigating",
    ):
        update_incident_status(
            db,
            incident.id,
            "investigating",
        )

    db.commit.assert_not_called()


def test_repeating_current_status_is_idempotent() -> None:
    incident = make_incident(status="open")
    db = make_session(incident)

    result = update_incident_status(
        db,
        incident.id,
        "open",
    )

    assert result is incident
    db.commit.assert_not_called()
    db.refresh.assert_not_called()


def test_missing_incident_raises_not_found() -> None:
    db = make_session(None)

    with pytest.raises(IncidentNotFoundError):
        update_incident_status(
            db,
            uuid4(),
            "resolved",
        )

    db.commit.assert_not_called()


def test_database_failure_rolls_back_update() -> None:
    incident = make_incident(status="open")
    db = make_session(incident)
    db.commit.side_effect = SQLAlchemyError(
        "Database unavailable"
    )

    with pytest.raises(
        IncidentLifecycleError,
        match="Unable to update incident",
    ):
        update_incident_status(
            db,
            incident.id,
            "investigating",
        )

    db.rollback.assert_called_once()