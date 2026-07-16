import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from backend.app.db.base import Base
import backend.app.models  # Registers all SQLAlchemy models


load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

migration_database_url = os.getenv("MIGRATION_DATABASE_URL")

if not migration_database_url:
    raise RuntimeError("MIGRATION_DATABASE_URL is not configured")

sqlalchemy_url = migration_database_url.replace(
    "postgresql://",
    "cockroachdb://",
    1,
)

# Alembic uses ConfigParser, where percent signs require escaping.
config.set_main_option(
    "sqlalchemy.url",
    sqlalchemy_url.replace("%", "%%"),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()