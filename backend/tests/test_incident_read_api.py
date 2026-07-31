import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi.dependencies.utils import request_params_to_args
from fastapi.exception_handlers import (
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from sqlalchemy.sql import Select
from starlette.datastructures import QueryParams
from starlette.requests import Request

from backend.app.api.incidents import list_incidents, router
from backend.app.models import Incident


TARGET_RUN_ID = UUID("22222222-2222-2222-2222-222222222222")
OTHER_RUN_ID = UUID("33333333-3333-3333-3333-333333333333")
RUN_WITHOUT_INCIDENT_ID = UUID(
    "44444444-4444-4444-4444-444444444444"
)


def make_incident(
    index: int,
    *,
    pipeline_run_id: UUID,
    status: str = "open",
) -> Incident:
    detected_at = datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(
        minutes=index
    )
    incident = Incident(
        id=UUID(int=index + 1),
        pipeline_run_id=pipeline_run_id,
        source="reliability-engine",
        title=f"Reliability incident {index}",
        description=f"Deterministic failure {index}",
        severity="critical",
        status=status,
        detected_at=detected_at,
        resolved_at=None,
        details={"sequence": index},
    )
    incident.created_at = detected_at
    incident.updated_at = detected_at
    return incident


class IncidentQuerySession:
    def __init__(self, incidents: list[Incident]) -> None:
        self.incidents = incidents
        self.statements: list[Select[tuple[Incident]]] = []

    def scalars(self, statement: Select[tuple[Incident]]):
        self.statements.append(statement)
        params = statement.compile().params
        incidents = list(self.incidents)

        pipeline_run_id = next(
            (
                value
                for key, value in params.items()
                if key.startswith("pipeline_run_id_")
            ),
            None,
        )
        if pipeline_run_id is not None:
            incidents = [
                incident
                for incident in incidents
                if incident.pipeline_run_id == pipeline_run_id
            ]

        incident_status = next(
            (
                value
                for key, value in params.items()
                if key.startswith("status_")
            ),
            None,
        )
        if incident_status is not None:
            incidents = [
                incident
                for incident in incidents
                if incident.status == incident_status
            ]

        incidents.sort(
            key=lambda incident: (incident.detected_at, incident.id),
            reverse=True,
        )
        offset = statement._offset_clause.value
        limit = statement._limit_clause.value
        selected = incidents[offset : offset + limit]

        class ScalarResult:
            def all(self) -> list[Incident]:
                return selected

        return ScalarResult()


def query_incidents(
    incidents: list[Incident],
    *,
    pipeline_run_id: UUID | None = None,
    incident_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Incident], IncidentQuerySession]:
    db = IncidentQuerySession(incidents)
    result = list_incidents(
        db=db,
        incident_status=incident_status,
        severity=None,
        source=None,
        pipeline_run_id=pipeline_run_id,
        limit=limit,
        offset=offset,
    )
    return result, db


def representative_incidents() -> list[Incident]:
    target = make_incident(0, pipeline_run_id=TARGET_RUN_ID)
    newer = [
        make_incident(index, pipeline_run_id=UUID(int=index + 1000))
        for index in range(1, 102)
    ]
    other = make_incident(102, pipeline_run_id=OTHER_RUN_ID)
    return [target, *newer, other]


def test_pipeline_run_id_finds_incident_beyond_global_first_100() -> None:
    incidents = representative_incidents()

    unfiltered, _ = query_incidents(
        incidents,
    )
    filtered, db = query_incidents(
        incidents,
        pipeline_run_id=TARGET_RUN_ID,
    )

    assert len(unfiltered) == 100
    assert str(TARGET_RUN_ID) not in {
        str(incident.pipeline_run_id) for incident in unfiltered
    }

    assert [incident.pipeline_run_id for incident in filtered] == [
        TARGET_RUN_ID
    ]
    assert "incidents.pipeline_run_id" in str(db.statements[-1])


def test_pipeline_run_id_excludes_incidents_for_other_runs() -> None:
    result, _ = query_incidents(
        representative_incidents(),
        pipeline_run_id=OTHER_RUN_ID,
    )

    assert len(result) == 1
    assert result[0].pipeline_run_id == OTHER_RUN_ID


def test_pipeline_run_id_returns_empty_list_when_run_has_no_incident() -> None:
    result, _ = query_incidents(
        representative_incidents(),
        pipeline_run_id=RUN_WITHOUT_INCIDENT_ID,
    )

    assert result == []


def test_pipeline_run_id_rejects_invalid_uuid() -> None:
    list_route = next(
        route
        for route in router.routes
        if route.path == "/api/incidents" and "GET" in route.methods
    )
    values, errors = request_params_to_args(
        list_route.dependant.query_params,
        QueryParams("pipeline_run_id=not-a-uuid"),
    )

    assert "pipeline_run_id" not in values
    assert len(errors) == 1
    assert errors[0]["loc"] == ("query", "pipeline_run_id")
    assert errors[0]["type"] == "uuid_parsing"

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/incidents",
            "headers": [],
            "query_string": b"pipeline_run_id=not-a-uuid",
        }
    )
    response = asyncio.run(
        request_validation_exception_handler(
            request,
            RequestValidationError(errors),
        )
    )

    assert response.status_code == 422
    assert json.loads(response.body)["detail"][0]["loc"] == [
        "query",
        "pipeline_run_id",
    ]


def test_pipeline_run_id_combines_with_existing_status_filter() -> None:
    resolved_target = make_incident(
        0,
        pipeline_run_id=TARGET_RUN_ID,
        status="resolved",
    )
    open_other = make_incident(
        1,
        pipeline_run_id=OTHER_RUN_ID,
        status="open",
    )

    matching, _ = query_incidents(
        [resolved_target, open_other],
        pipeline_run_id=TARGET_RUN_ID,
        incident_status="resolved",
    )
    excluded, _ = query_incidents(
        [resolved_target, open_other],
        pipeline_run_id=TARGET_RUN_ID,
        incident_status="open",
    )

    assert len(matching) == 1
    assert excluded == []


def test_unfiltered_listing_preserves_order_limit_and_offset() -> None:
    incidents = representative_incidents()

    result, db = query_incidents(
        incidents,
        limit=2,
        offset=1,
    )

    assert [item.id for item in result] == [
        incidents[-2].id,
        incidents[-3].id,
    ]
    statement = str(db.statements[-1])
    assert "incidents.pipeline_run_id =" not in statement
    assert (
        "ORDER BY incidents.detected_at DESC, incidents.id DESC"
        in statement
    )
