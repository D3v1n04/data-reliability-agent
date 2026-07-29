from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings
from backend.app.core.runtime_config import resolve_database_url


@lru_cache
def get_engine() -> Engine:
    """Create one bounded connection pool per process or Lambda sandbox."""
    settings = get_settings()
    database_url = resolve_database_url(settings)
    sqlalchemy_url = database_url.replace(
        "postgresql://",
        "cockroachdb://",
        1,
    )

    return create_engine(
        sqlalchemy_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
        connect_args={
            "connect_timeout": (
                settings.database_connect_timeout_seconds
            ),
            "options": (
                "-c statement_timeout="
                f"{settings.database_statement_timeout_ms}"
            ),
        },
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()

    try:
        yield db
    finally:
        db.close()


def check_database_readiness() -> None:
    """Run the smallest possible database readiness query."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
