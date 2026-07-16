from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models import Incident, Pipeline, PipelineRun
from backend.app.schemas import PipelineRunCreate
from backend.app.services.reliability import (
    evaluate_pipeline_run,
    highest_severity,
)


class PipelineNotFoundError(Exception):
    pass


class PipelineRunIngestionError(Exception):
    pass


@dataclass(frozen=True)
class PipelineRunIngestionResult:
    pipeline_run: PipelineRun
    incident: Incident | None
    violations: list[dict[str, object]]
    duplicate: bool


def find_existing_run(
    db: Session,
    pipeline_id: UUID,
    external_run_id: str,
) -> PipelineRun | None:
    statement = select(PipelineRun).where(
        PipelineRun.pipeline_id == pipeline_id,
        PipelineRun.external_run_id == external_run_id,
    )

    return db.scalar(statement)


def find_run_incident(
    db: Session,
    pipeline_run_id: UUID,
) -> Incident | None:
    statement = select(Incident).where(
        Incident.pipeline_run_id == pipeline_run_id
    )

    return db.scalar(statement)


def stored_violations(
    incident: Incident | None,
) -> list[dict[str, object]]:
    if incident is None:
        return []

    value = incident.details.get("violations")

    if not isinstance(value, list):
        return []

    return [
        item
        for item in value
        if isinstance(item, dict)
    ]


def ingest_pipeline_run(
    db: Session,
    pipeline_id: UUID,
    run_data: PipelineRunCreate,
) -> PipelineRunIngestionResult:
    """Store a completed run and create one incident when rules fail."""
    try:
        pipeline = db.get(Pipeline, pipeline_id)

        if pipeline is None:
            raise PipelineNotFoundError

        existing_run = find_existing_run(
            db,
            pipeline_id,
            run_data.external_run_id,
        )

        if existing_run is not None:
            incident = find_run_incident(db, existing_run.id)

            return PipelineRunIngestionResult(
                pipeline_run=existing_run,
                incident=incident,
                violations=stored_violations(incident),
                duplicate=True,
            )

        violations = evaluate_pipeline_run(
            pipeline,
            run_data,
        )
        violation_details = [
            violation.to_dict()
            for violation in violations
        ]

        pipeline_run = PipelineRun(
            pipeline_id=pipeline_id,
            **run_data.model_dump(),
        )
        db.add(pipeline_run)
        db.flush()

        incident: Incident | None = None

        if violations:
            severity = highest_severity(violations)

            if severity is None:
                raise PipelineRunIngestionError(
                    "Unable to determine incident severity"
                )

            incident = Incident(
                pipeline_run_id=pipeline_run.id,
                source="reliability-engine",
                title=f"Reliability failure: {pipeline.name}",
                description=(
                    "Deterministic reliability rules detected "
                    f"{len(violations)} violation(s)"
                ),
                severity=severity,
                status="open",
                detected_at=run_data.completed_at,
                details={
                    "pipeline_id": str(pipeline.id),
                    "pipeline_name": pipeline.name,
                    "pipeline_run_id": str(pipeline_run.id),
                    "external_run_id": run_data.external_run_id,
                    "violations": violation_details,
                },
            )
            db.add(incident)

        db.commit()
        db.refresh(pipeline_run)

        if incident is not None:
            db.refresh(incident)

        return PipelineRunIngestionResult(
            pipeline_run=pipeline_run,
            incident=incident,
            violations=violation_details,
            duplicate=False,
        )

    except IntegrityError as exc:
        db.rollback()

        try:
            existing_run = find_existing_run(
                db,
                pipeline_id,
                run_data.external_run_id,
            )

            if existing_run is not None:
                incident = find_run_incident(db, existing_run.id)

                return PipelineRunIngestionResult(
                    pipeline_run=existing_run,
                    incident=incident,
                    violations=stored_violations(incident),
                    duplicate=True,
                )
        except SQLAlchemyError as lookup_exc:
            db.rollback()
            raise PipelineRunIngestionError(
                "Unable to retrieve the existing pipeline run"
            ) from lookup_exc

        raise PipelineRunIngestionError(
            "Unable to store pipeline run"
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        raise PipelineRunIngestionError(
            "Unable to store pipeline run"
        ) from exc