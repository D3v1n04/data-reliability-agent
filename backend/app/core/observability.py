import json
import logging
import sys
from datetime import datetime, timezone
from time import perf_counter
from typing import Final, Literal
from uuid import uuid4

from fastapi import Request, Response

from backend.app.core.config import Settings, get_settings


FailureCategory = Literal["bedrock", "database", "diagnosis"]

_SAFE_LOG_FIELDS: Final[tuple[str, ...]] = (
    "event",
    "request_id",
    "method",
    "route",
    "status_code",
    "duration_ms",
    "failure_category",
)

_METRIC_NAMES: Final[dict[FailureCategory, str]] = {
    "bedrock": "BedrockFailures",
    "database": "DatabaseFailures",
    "diagnosis": "DiagnosisFailures",
}


class JsonFormatter(logging.Formatter):
    """Format an allowlisted operational log record as one JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in _SAFE_LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        return json.dumps(
            payload,
            separators=(",", ":"),
            default=str,
        )


def configure_logging(settings: Settings | None = None) -> None:
    """Configure sanitized structured application logging once."""
    resolved_settings = settings or get_settings()
    root_logger = logging.getLogger()

    if getattr(root_logger, "_dra_configured", False):
        return

    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root_logger.addHandler(handler)

    root_logger.setLevel(resolved_settings.log_level)
    root_logger._dra_configured = True  # type: ignore[attr-defined]


def emit_dependency_failure(
    category: FailureCategory,
    settings: Settings | None = None,
) -> None:
    """Emit one CloudWatch Embedded Metric Format failure count."""
    resolved_settings = settings or get_settings()
    metric_name = _METRIC_NAMES[category]
    timestamp_ms = int(
        datetime.now(timezone.utc).timestamp() * 1000
    )
    payload = {
        "_aws": {
            "Timestamp": timestamp_ms,
            "CloudWatchMetrics": [
                {
                    "Namespace": resolved_settings.metrics_namespace,
                    "Dimensions": [["Environment"]],
                    "Metrics": [
                        {
                            "Name": metric_name,
                            "Unit": "Count",
                        }
                    ],
                }
            ],
        },
        "Environment": resolved_settings.environment,
        metric_name: 1,
    }
    print(json.dumps(payload, separators=(",", ":")), flush=True)


async def request_observability_middleware(
    request: Request,
    call_next,
) -> Response:
    """Log bounded request metadata without bodies, queries, or evidence."""
    request_id = str(uuid4())
    started_at = perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        _log_request(
            request=request,
            request_id=request_id,
            status_code=status_code,
            started_at=started_at,
        )
        raise

    response.headers["X-Request-ID"] = request_id
    _log_request(
        request=request,
        request_id=request_id,
        status_code=status_code,
        started_at=started_at,
    )
    return response


def _log_request(
    request: Request,
    request_id: str,
    status_code: int,
    started_at: float,
) -> None:
    route = request.scope.get("route")
    route_template = getattr(route, "path", "unmatched")
    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    level = logging.ERROR if status_code >= 500 else logging.INFO

    logging.getLogger("backend.request").log(
        level,
        "request_completed",
        extra={
            "event": "request_completed",
            "request_id": request_id,
            "method": request.method,
            "route": route_template,
            "status_code": status_code,
            "duration_ms": duration_ms,
        },
    )
