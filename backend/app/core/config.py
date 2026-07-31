from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DIAGNOSIS_BEDROCK_PHASE_COUNT = 2
MIN_DIAGNOSIS_OVERHEAD_RESERVE_SECONDS = 6
MIN_LAMBDA_SAFETY_MARGIN_SECONDS = 5


class Settings(BaseSettings):
    app_name: str = "Data Reliability Agent"
    environment: Literal["local", "test", "production"] = "local"
    database_url: SecretStr | None = None
    database_url_ssm_parameter: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    aws_profile: str | None = "data-reliability-agent"
    aws_region: str = "us-east-1"

    bedrock_text_model_id: str = "amazon.nova-lite-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_embedding_dimensions: int = Field(default=256, ge=1)
    bedrock_connect_timeout_seconds: int = Field(
        default=2,
        ge=1,
        le=10,
    )
    bedrock_read_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=30,
    )
    aws_total_max_attempts: int = Field(default=1, ge=1, le=3)
    diagnosis_timeout_seconds: int = Field(default=20, ge=1, le=60)
    lambda_timeout_seconds: int = Field(default=25, ge=1, le=900)

    similar_incident_limit: int = Field(default=5, ge=1, le=20)
    cors_allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    database_pool_size: int = Field(default=1, ge=1, le=5)
    database_max_overflow: int = Field(default=0, ge=0, le=2)
    database_pool_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=15,
    )
    database_pool_recycle_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
    )
    database_connect_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=15,
    )
    database_statement_timeout_ms: int = Field(
        default=10000,
        ge=1000,
        le=30000,
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    metrics_namespace: str = "DataReliabilityAgent"

    @property
    def diagnosis_inference_socket_budget_seconds(self) -> int:
        """Return the aggregate connect/read budget for Titan and Nova."""
        return (
            DIAGNOSIS_BEDROCK_PHASE_COUNT
            * self.aws_total_max_attempts
            * (
                self.bedrock_connect_timeout_seconds
                + self.bedrock_read_timeout_seconds
            )
        )

    @property
    def diagnosis_overhead_reserve_seconds(self) -> int:
        """Return time reserved for database and application work."""
        return (
            self.diagnosis_timeout_seconds
            - self.diagnosis_inference_socket_budget_seconds
        )

    @property
    def lambda_safety_margin_seconds(self) -> int:
        """Return time reserved before Lambda termination."""
        return (
            self.lambda_timeout_seconds
            - self.diagnosis_timeout_seconds
        )

    @model_validator(mode="after")
    def validate_diagnosis_timeout_budget(self) -> Self:
        if (
            self.diagnosis_overhead_reserve_seconds
            < MIN_DIAGNOSIS_OVERHEAD_RESERVE_SECONDS
        ):
            raise ValueError(
                "Diagnosis timeout must reserve at least 6 seconds "
                "beyond the aggregate Bedrock connect/read budget"
            )

        if (
            self.lambda_safety_margin_seconds
            < MIN_LAMBDA_SAFETY_MARGIN_SECONDS
        ):
            raise ValueError(
                "Diagnosis timeout must remain at least 5 seconds below "
                "the Lambda timeout"
            )

        return self

    @property
    def allowed_origins(self) -> list[str]:
        """Return normalized configured browser origins."""
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
