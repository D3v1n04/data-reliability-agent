from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from backend.app.core.aws import (
    create_aws_client_config,
    create_aws_session,
)
from backend.app.core.config import Settings, get_settings


class RuntimeConfigurationError(RuntimeError):
    """Raised when required runtime configuration cannot be loaded."""


def _validate_database_url(database_url: str) -> str:
    normalized_url = database_url.strip()

    if not normalized_url.startswith(
        ("postgresql://", "cockroachdb://")
    ):
        raise RuntimeConfigurationError(
            "Database URL must use PostgreSQL or CockroachDB"
        )

    if "sslmode=verify-full" not in normalized_url:
        raise RuntimeConfigurationError(
            "Database URL must require sslmode=verify-full"
        )

    return normalized_url


def resolve_database_url(
    settings: Settings | None = None,
    ssm_client: Any | None = None,
) -> str:
    """Resolve the database URL from local settings or SSM SecureString."""
    resolved_settings = settings or get_settings()

    if resolved_settings.database_url is not None:
        return _validate_database_url(
            resolved_settings.database_url.get_secret_value()
        )

    parameter_name = resolved_settings.database_url_ssm_parameter

    if not parameter_name:
        raise RuntimeConfigurationError(
            "Database configuration is unavailable"
        )

    if ssm_client is None:
        session = create_aws_session(resolved_settings)
        ssm_client = session.client(
            "ssm",
            config=create_aws_client_config(resolved_settings),
        )

    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=True,
        )
        value = response["Parameter"]["Value"]
    except (
        BotoCoreError,
        ClientError,
        KeyError,
        TypeError,
    ) as exc:
        raise RuntimeConfigurationError(
            "Database configuration could not be loaded"
        ) from exc

    if not isinstance(value, str):
        raise RuntimeConfigurationError(
            "Database configuration is invalid"
        )

    return _validate_database_url(value)
