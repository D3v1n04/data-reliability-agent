from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models import Pipeline
from backend.app.schemas import (
    PipelineCreate,
    PipelineRead,
    PipelineRunCreate,
    PipelineRunIngestResponse,
)

from backend.app.services.ingestion import (
    PipelineNotFoundError,
    PipelineRunIngestionError,
    ingest_pipeline_run,
)


router = APIRouter(
    prefix="/api/pipelines",
    tags=["pipelines"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=PipelineRead,
    status_code=status.HTTP_201_CREATED,
)
def create_pipeline(
    pipeline_data: PipelineCreate,
    db: DatabaseSession,
) -> Pipeline:
    pipeline = Pipeline(**pipeline_data.model_dump())

    try:
        db.add(pipeline)
        db.commit()
        db.refresh(pipeline)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pipeline with this name already exists",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to save pipeline",
        ) from exc

    return pipeline


@router.post(
    "/{pipeline_id}/runs",
    response_model=PipelineRunIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pipeline_run(
    pipeline_id: UUID,
    run_data: PipelineRunCreate,
    response: Response,
    db: DatabaseSession,
) -> dict[str, object]:
    try:
        result = ingest_pipeline_run(
            db,
            pipeline_id,
            run_data,
        )
    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found",
        ) from exc
    except PipelineRunIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to ingest pipeline run",
        ) from exc

    if result.duplicate:
        response.status_code = status.HTTP_200_OK

    return {
        "run": result.pipeline_run,
        "incident": result.incident,
        "violations": result.violations,
        "duplicate": result.duplicate,
    }


@router.get(
    "/{pipeline_id}",
    response_model=PipelineRead,
)
def get_pipeline(
    pipeline_id: UUID,
    db: DatabaseSession,
) -> Pipeline:
    try:
        pipeline = db.get(Pipeline, pipeline_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve pipeline",
        ) from exc

    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found",
        )

    return pipeline