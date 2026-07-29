#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def request_json(
    base_url: str,
    path: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    allowed_error_statuses: set[int] | None = None,
) -> tuple[int, dict[str, Any]]:
    encoded_body = (
        json.dumps(body).encode("utf-8")
        if body is not None
        else None
    )
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=encoded_body,
        method=method,
        headers={
            "Accept": "application/json",
            **(
                {"Content-Type": "application/json"}
                if encoded_body is not None
                else {}
            ),
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")

        if allowed_error_statuses and exc.code in allowed_error_statuses:
            return exc.code, json.loads(response_body)

        raise RuntimeError(
            f"{method} {path} returned {exc.code}: {response_body}"
        ) from None
    except URLError as exc:
        raise RuntimeError(
            f"{method} {path} could not connect: {exc.reason}"
        ) from None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the deployed Phase 8 acceptance workflow."
    )
    parser.add_argument("application_url")
    parser.add_argument(
        "--expect-diagnosis-failure",
        action="store_true",
        help="Pass only when diagnosis returns a sanitized HTTP 503.",
    )
    args = parser.parse_args()
    base_url = args.application_url
    unique_suffix = uuid4().hex[:10]

    _, health = request_json(base_url, "/health")
    assert health["status"] == "ok"

    _, readiness = request_json(base_url, "/ready")
    assert readiness == {"status": "ready", "database": "ok"}

    _, pipeline = request_json(
        base_url,
        "/api/pipelines",
        method="POST",
        body={
            "name": f"phase-8-acceptance-{unique_suffix}",
            "description": "Phase 8 live acceptance test",
            "max_duration_seconds": 300,
            "min_rows_processed": 100,
            "max_start_delay_seconds": 60,
            "enabled": True,
        },
    )

    now = datetime.now(timezone.utc)
    _, ingestion = request_json(
        base_url,
        f"/api/pipelines/{pipeline['id']}/runs",
        method="POST",
        body={
            "external_run_id": f"phase-8-run-{unique_suffix}",
            "status": "failed",
            "scheduled_at": (now - timedelta(minutes=12)).isoformat(),
            "started_at": (now - timedelta(minutes=10)).isoformat(),
            "completed_at": now.isoformat(),
            "rows_processed": 40,
            "quality_checks_failed": 2,
            "metrics": {"acceptance_test": True},
            "error_message": "Synthetic acceptance failure",
            "logs": ["Synthetic validation failure"],
        },
    )
    incident = ingestion["incident"]
    assert incident is not None
    assert ingestion["violations"]

    diagnosis_status, diagnosis = request_json(
        base_url,
        f"/api/incidents/{incident['id']}/diagnosis",
        method="POST",
        allowed_error_statuses=(
            {503}
            if args.expect_diagnosis_failure
            else None
        ),
    )

    if args.expect_diagnosis_failure:
        assert diagnosis_status == 503
        assert diagnosis == {"detail": "Unable to diagnose incident"}
        print(
            json.dumps(
                {
                    "status": "passed",
                    "mode": "expected-diagnosis-failure",
                    "incident_id": incident["id"],
                },
                indent=2,
            )
        )
        return 0

    assert diagnosis["explanation"]
    assert diagnosis["likely_causes"]
    assert diagnosis["recommendations"]
    assert diagnosis["confidence"] <= 0.6

    for next_status in ("investigating", "resolved"):
        _, incident = request_json(
            base_url,
            f"/api/incidents/{incident['id']}/status",
            method="PATCH",
            body={"status": next_status},
        )
        assert incident["status"] == next_status

    print(
        json.dumps(
            {
                "status": "passed",
                "pipeline_id": pipeline["id"],
                "incident_id": incident["id"],
                "final_status": incident["status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError, KeyError, ValueError) as exc:
        print(f"Acceptance test failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
