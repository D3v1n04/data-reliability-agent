from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models import PipelineRun
from backend.app.schemas import PipelineRunRead


router = APIRouter(
    prefix="/api/pipeline-runs",
    tags=["pipeline-runs"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/{run_id}",
    response_model=PipelineRunRead,
)
def get_pipeline_run(
    run_id: UUID,
    db: DatabaseSession,
) -> PipelineRun:
    try:
        pipeline_run = db.get(PipelineRun, run_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve pipeline run",
        ) from exc

    if pipeline_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run not found",
        )

    return pipeline_run
