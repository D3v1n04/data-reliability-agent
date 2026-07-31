import json
import logging
import re
from pathlib import Path
from unittest.mock import Mock, patch

import boto3
import pytest
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import OperationalError

from backend.app.core.aws import (
    create_aws_client_config,
    create_aws_session,
)
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


def test_bedrock_client_uses_explicit_bounded_attempts_and_timeouts() -> None:
    settings = make_settings()
    client = boto3.Session(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    ).client(
        "bedrock-runtime",
        config=create_aws_client_config(settings),
    )

    assert client.meta.config.connect_timeout == 2
    assert client.meta.config.read_timeout == 5
    assert client.meta.config.retries == {
        "mode": "standard",
        "total_max_attempts": 1,
    }


def test_diagnosis_budget_reserves_overhead_and_lambda_margin() -> None:
    settings = make_settings()

    assert settings.diagnosis_inference_socket_budget_seconds == 14
    assert settings.diagnosis_overhead_reserve_seconds == 6
    assert settings.lambda_safety_margin_seconds == 5
    assert (
        settings.diagnosis_inference_socket_budget_seconds
        + settings.diagnosis_overhead_reserve_seconds
        == settings.diagnosis_timeout_seconds
    )
    assert (
        settings.diagnosis_timeout_seconds
        < settings.lambda_timeout_seconds
    )


def test_sam_lambda_timeout_uses_one_constrained_parameter() -> None:
    template = (
        Path(__file__).parents[2] / "infra" / "template.yaml"
    ).read_text(encoding="utf-8")

    parameter_match = re.search(
        r"(?m)^  LambdaTimeoutSeconds:\n"
        r"(?P<body>(?:    .*\n)+)",
        template,
    )
    function_timeout_match = re.search(
        r"(?m)^    Timeout: !Ref (?P<parameter>\w+)$",
        template,
    )
    environment_timeout_match = re.search(
        r"(?m)^        LAMBDA_TIMEOUT_SECONDS: "
        r"!Ref (?P<parameter>\w+)$",
        template,
    )

    assert parameter_match is not None
    assert function_timeout_match is not None
    assert environment_timeout_match is not None
    parameter_body = parameter_match.group("body")
    assert re.search(r"(?m)^    Type: Number$", parameter_body)
    assert re.search(r"(?m)^    Default: 25$", parameter_body)
    assert re.search(
        r"(?m)^    AllowedValues:\n      - 25$",
        parameter_body,
    )
    assert re.findall(
        r"(?m)^      - (.+)$",
        parameter_body,
    ) == ["25"]
    assert function_timeout_match.group("parameter") == (
        "LambdaTimeoutSeconds"
    )
    assert environment_timeout_match.group("parameter") == (
        function_timeout_match.group("parameter")
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"diagnosis_timeout_seconds": 14},
            "must reserve at least 6 seconds",
        ),
        (
            {"diagnosis_timeout_seconds": 15},
            "must reserve at least 6 seconds",
        ),
        (
            {"diagnosis_timeout_seconds": 25},
            "must remain at least 5 seconds below",
        ),
        (
            {"diagnosis_timeout_seconds": 21},
            "must remain at least 5 seconds below",
        ),
    ],
)
def test_invalid_diagnosis_timeout_relationships_fail_validation(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        make_settings(**overrides)


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
