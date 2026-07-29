import logging

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.app.api.incidents import router as incidents_router
from backend.app.api.pipeline_runs import router as pipeline_runs_router
from backend.app.api.pipelines import router as pipelines_router
from backend.app.core.config import get_settings
from backend.app.core.observability import (
    configure_logging,
    emit_dependency_failure,
    request_observability_middleware,
)
from backend.app.core.runtime_config import RuntimeConfigurationError
from backend.app.db.session import check_database_readiness


settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.middleware("http")(request_observability_middleware)

if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )


app.include_router(incidents_router)
app.include_router(pipelines_router)
app.include_router(pipeline_runs_router)


@app.get("/health", include_in_schema=False)
def health_check():
    """Return process liveness without calling dependencies."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


@app.get("/ready", include_in_schema=False)
def readiness_check():
    """Return readiness only when CockroachDB is reachable."""
    try:
        check_database_readiness()
    except (RuntimeConfigurationError, SQLAlchemyError):
        logger.error(
            "database_readiness_failed",
            extra={
                "event": "dependency_failure",
                "failure_category": "database",
            },
        )
        emit_dependency_failure("database", settings)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from None

    return {
        "status": "ready",
        "database": "ok",
    }
