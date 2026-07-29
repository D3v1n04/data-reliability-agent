import json
import logging
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError

from backend.app.core.aws import create_aws_session
from backend.app.core.config import Settings
from backend.app.core.observability import (
    JsonFormatter,
    emit_dependency_failure,
)
from backend.app.core.runtime_config import (
    RuntimeConfigurationError,
    resolve_database_url,
)
from backend.app.db import session as database_session


SECURE_DATABASE_URL = (
    "postgresql://dra_app:secret@example.com:26257/"
    "data_reliability?sslmode=verify-full"
)


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "database_url": SECURE_DATABASE_URL,
        "aws_profile": "data-reliability-agent",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_local_aws_session_uses_named_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.delenv("AWS_EXECUTION_ENV", raising=False)

    with patch("backend.app.core.aws.boto3.Session") as session:
        create_aws_session(make_settings())

    session.assert_called_once_with(
        region_name="us-east-1",
        profile_name="data-reliability-agent",
    )


def test_lambda_aws_session_uses_execution_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "phase-8-backend")

    with patch("backend.app.core.aws.boto3.Session") as session:
        create_aws_session(make_settings())

    session.assert_called_once_with(region_name="us-east-1")


def test_database_url_loads_secure_string_from_ssm() -> None:
    ssm_client = Mock()
    ssm_client.get_parameter.return_value = {
        "Parameter": {
            "Value": SECURE_DATABASE_URL,
        }
    }
    settings = make_settings(
        database_url=None,
        database_url_ssm_parameter=(
            "/data-reliability-agent/test/database-url"
        ),
    )

    result = resolve_database_url(
        settings=settings,
        ssm_client=ssm_client,
    )

    assert result == SECURE_DATABASE_URL
    ssm_client.get_parameter.assert_called_once_with(
        Name="/data-reliability-agent/test/database-url",
        WithDecryption=True,
    )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://dra_app:secret@example.com/database",
        "https://example.com/database?sslmode=verify-full",
    ],
)
def test_database_url_requires_verified_tls(
    database_url: str,
) -> None:
    settings = make_settings(
        database_url=SecretStr(database_url),
    )

    with pytest.raises(RuntimeConfigurationError):
        resolve_database_url(settings=settings)


def test_database_engine_uses_bounded_pool_and_timeouts() -> None:
    settings = make_settings()

    with (
        patch(
            "backend.app.db.session.get_settings",
            return_value=settings,
        ),
        patch(
            "backend.app.db.session.resolve_database_url",
            return_value=SECURE_DATABASE_URL,
        ),
        patch(
            "backend.app.db.session.create_engine",
        ) as create_engine,
    ):
        database_session.get_engine.cache_clear()
        database_session.get_engine()
        database_session.get_engine.cache_clear()

    _, kwargs = create_engine.call_args
    assert kwargs["pool_size"] == 1
    assert kwargs["max_overflow"] == 0
    assert kwargs["pool_timeout"] == 5
    assert kwargs["connect_args"] == {
        "connect_timeout": 5,
        "options": "-c statement_timeout=10000",
    }


def test_json_formatter_omits_exception_and_secret_details() -> None:
    try:
        raise ValueError(
            "postgresql://dra_app:do-not-log@example.com/database"
        )
    except ValueError:
        record = logging.LogRecord(
            name="backend.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="database_operation_failed",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )

    rendered = JsonFormatter().format(record)

    assert "database_operation_failed" in rendered
    assert "do-not-log" not in rendered
    assert "ValueError" not in rendered


def test_dependency_metric_contains_only_bounded_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    emit_dependency_failure("bedrock", make_settings())

    payload = json.loads(capsys.readouterr().out)
    assert payload["Environment"] == "test"
    assert payload["BedrockFailures"] == 1
    assert set(payload) == {
        "_aws",
        "Environment",
        "BedrockFailures",
    }


def test_liveness_does_not_call_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app import main

    readiness = Mock()
    monkeypatch.setattr(main, "check_database_readiness", readiness)

    response = main.health_check()

    assert response["status"] == "ok"
    readiness.assert_not_called()


def test_readiness_returns_503_without_error_details(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    from backend.app import main

    secret = "do-not-log-database-password"
    monkeypatch.setattr(
        main,
        "check_database_readiness",
        Mock(
            side_effect=OperationalError(
                "SELECT 1",
                {},
                RuntimeError(secret),
            )
        ),
    )

    with (
        caplog.at_level(
            logging.ERROR,
            logger="backend.app.main",
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        main.readiness_check()

    captured = capsys.readouterr()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Database is unavailable"
    assert secret not in captured.out
    assert secret not in captured.err
    assert secret not in caplog.text
