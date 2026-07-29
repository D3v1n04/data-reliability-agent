import os
from typing import Any

import boto3
from botocore.config import Config

from backend.app.core.config import Settings


def is_aws_runtime() -> bool:
    """Return whether the process is executing in an AWS managed runtime."""
    return bool(
        os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("AWS_EXECUTION_ENV")
    )


def create_aws_session(settings: Settings) -> boto3.Session:
    """Create a session using profiles locally and IAM roles in AWS."""
    session_options: dict[str, Any] = {
        "region_name": settings.aws_region,
    }

    if settings.aws_profile and not is_aws_runtime():
        session_options["profile_name"] = settings.aws_profile

    return boto3.Session(**session_options)


def create_aws_client_config(settings: Settings) -> Config:
    """Return bounded network and retry behavior for AWS dependencies."""
    return Config(
        connect_timeout=settings.bedrock_connect_timeout_seconds,
        read_timeout=settings.bedrock_read_timeout_seconds,
        retries={
            "max_attempts": settings.aws_max_attempts,
            "mode": "standard",
        },
    )
