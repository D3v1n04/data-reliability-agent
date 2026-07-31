#!/usr/bin/env python3
"""Create an idempotent synthetic history-first hackathon demo."""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


JsonRequest = Callable[
    [str, str, str, dict[str, Any] | None],
    tuple[int, Any],
]

LABEL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")


def request_json(
    base_url: str,
    path: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    """Send one bounded JSON request to the demo application."""
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
        raise RuntimeError(
            f"{method} {path} returned {exc.code}: {response_body}"
        ) from None
    except URLError as exc:
        raise RuntimeError(
            f"{method} {path} could not connect: {exc.reason}"
        ) from None


def _find_or_create_pipeline(
    base_url: str,
    label: str,
    request: JsonRequest,
) -> dict[str, Any]:
    pipeline_name = f"customer-orders-demo-{label}"
    _, pipelines = request(
        base_url,
        "/api/pipelines?limit=100",
        "GET",
        None,
    )

    for pipeline in pipelines:
        if pipeline["name"] == pipeline_name:
            return pipeline

    _, pipeline = request(
        base_url,
        "/api/pipelines",
        "POST",
        {
            "name": pipeline_name,
            "description": (
                "Synthetic customer-order pipeline used only for the "
                "hackathon demonstration"
            ),
            "max_duration_seconds": 300,
            "min_rows_processed": 100,
            "max_start_delay_seconds": 60,
            "enabled": True,
        },
    )
    return pipeline


def _run_payloads(
    now: datetime,
    label: str,
) -> list[dict[str, Any]]:
    return [
        {
            "external_run_id": f"{label}-history-duration",
            "status": "failed",
            "scheduled_at": (now - timedelta(days=2, minutes=22)).isoformat(),
            "started_at": (now - timedelta(days=2, minutes=20)).isoformat(),
            "completed_at": (now - timedelta(days=2)).isoformat(),
            "rows_processed": 145,
            "quality_checks_failed": 0,
            "metrics": {
                "dataset": "synthetic",
                "scenario": "historical-duration",
            },
            "error_message": (
                "Synthetic warehouse transform timeout after partition skew"
            ),
            "logs": [
                "Synthetic demo record: transform exceeded its duration limit"
            ],
        },
        {
            "external_run_id": f"{label}-history-quality",
            "status": "failed",
            "scheduled_at": (now - timedelta(days=1, minutes=13)).isoformat(),
            "started_at": (now - timedelta(days=1, minutes=11)).isoformat(),
            "completed_at": (now - timedelta(days=1)).isoformat(),
            "rows_processed": 51,
            "quality_checks_failed": 3,
            "metrics": {
                "dataset": "synthetic",
                "scenario": "historical-quality",
            },
            "error_message": (
                "Synthetic customer-order validation rejected schema changes"
            ),
            "logs": [
                "Synthetic demo record: order fields failed validation"
            ],
        },
        {
            "external_run_id": f"{label}-current-quality",
            "status": "failed",
            "scheduled_at": (now - timedelta(minutes=12)).isoformat(),
            "started_at": (now - timedelta(minutes=10)).isoformat(),
            "completed_at": now.isoformat(),
            "rows_processed": 42,
            "quality_checks_failed": 2,
            "metrics": {
                "dataset": "synthetic",
                "scenario": "current-quality",
            },
            "error_message": (
                "Synthetic customer-order validation rejected records after "
                "an upstream schema change"
            ),
            "logs": [
                "Synthetic demo record: required order fields were missing"
            ],
        },
    ]


def _advance_to_resolved(
    base_url: str,
    incident: dict[str, Any],
    request: JsonRequest,
) -> None:
    status = incident["status"]

    if status == "open":
        _, incident = request(
            base_url,
            f"/api/incidents/{incident['id']}/status",
            "PATCH",
            {"status": "investigating"},
        )
        status = incident["status"]

    if status == "investigating":
        request(
            base_url,
            f"/api/incidents/{incident['id']}/status",
            "PATCH",
            {"status": "resolved"},
        )


def seed_demo(
    base_url: str,
    label: str,
    request: JsonRequest = request_json,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create two resolved memories followed by one current incident."""
    if not LABEL_PATTERN.fullmatch(label):
        raise ValueError(
            "label must be 1-30 lowercase letters, numbers, or hyphens"
        )

    resolved_now = now or datetime.now(timezone.utc)
    pipeline = _find_or_create_pipeline(base_url, label, request)
    incidents: list[dict[str, Any]] = []
    diagnoses: list[dict[str, Any]] = []

    for position, payload in enumerate(_run_payloads(resolved_now, label)):
        _, ingestion = request(
            base_url,
            f"/api/pipelines/{pipeline['id']}/runs",
            "POST",
            payload,
        )
        incident = ingestion["incident"]

        if incident is None or not ingestion["violations"]:
            raise RuntimeError(
                f"demo run {payload['external_run_id']} created no incident"
            )

        _, diagnosis = request(
            base_url,
            f"/api/incidents/{incident['id']}/diagnosis",
            "POST",
            None,
        )
        incidents.append(incident)
        diagnoses.append(diagnosis)

        if position < 2:
            _advance_to_resolved(base_url, incident, request)

    current_incident = incidents[-1]
    current_diagnosis = diagnoses[-1]
    similar_incidents = current_diagnosis.get("evidence", {}).get(
        "similar_incidents",
        [],
    )

    if not similar_incidents:
        raise RuntimeError(
            "current diagnosis did not retrieve any incident memory"
        )

    if current_incident["status"] != "open":
        raise RuntimeError(
            "the current demo incident was already advanced; choose a new label"
        )

    return {
        "status": "ready",
        "synthetic_data_only": True,
        "label": label,
        "pipeline_id": pipeline["id"],
        "historical_incident_ids": [
            incident["id"]
            for incident in incidents[:2]
        ],
        "current_incident_id": current_incident["id"],
        "current_incident_url": (
            f"{base_url.rstrip('/')}/incidents/{current_incident['id']}"
        ),
        "similar_memories_retrieved": len(similar_incidents),
        "trust_boundary": (
            "deterministic rules establish facts; AI provides bounded "
            "investigation guidance"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Seed two historical incident memories and one current demo "
            "incident through the public API."
        )
    )
    parser.add_argument("application_url")
    parser.add_argument(
        "--label",
        default="hackathon-demo-v1",
        help=(
            "Stable scenario label. Use a new label after advancing the "
            "current incident."
        ),
    )
    args = parser.parse_args()
    result = seed_demo(args.application_url, args.label)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        print(f"Demo seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
