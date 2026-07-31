from datetime import datetime, timezone
from typing import Any

import pytest

from scripts.seed_demo import seed_demo


def test_seed_demo_creates_history_before_current_memory() -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []
    incidents = [
        {"id": "incident-1", "status": "open"},
        {"id": "incident-2", "status": "open"},
        {"id": "incident-3", "status": "open"},
    ]
    ingestion_index = 0

    def fake_request(
        base_url: str,
        path: str,
        method: str,
        body: dict[str, Any] | None,
    ) -> tuple[int, Any]:
        nonlocal ingestion_index
        calls.append((path, method, body))

        if path == "/api/pipelines?limit=100":
            return 200, []
        if path == "/api/pipelines":
            return 201, {"id": "pipeline-1", **(body or {})}
        if path.endswith("/runs"):
            incident = incidents[ingestion_index]
            ingestion_index += 1
            return 201, {
                "incident": incident,
                "violations": [{"rule_code": "RUN_FAILED"}],
            }
        if path.endswith("/diagnosis"):
            diagnosis_number = len(
                [
                    call
                    for call in calls
                    if call[0].endswith("/diagnosis")
                ]
            )
            return 201, {
                "evidence": {
                    "similar_incidents": (
                        []
                        if diagnosis_number == 1
                        else [{"incident_id": "incident-1"}]
                    )
                }
            }
        if path.endswith("/status"):
            assert body is not None
            return 200, {
                "id": path.split("/")[3],
                "status": body["status"],
            }
        raise AssertionError(f"Unexpected request: {method} {path}")

    result = seed_demo(
        "https://demo.example",
        "recording-v1",
        request=fake_request,
        now=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )

    assert result["status"] == "ready"
    assert result["synthetic_data_only"] is True
    assert result["similar_memories_retrieved"] == 1
    assert result["current_incident_id"] == "incident-3"
    assert result["current_incident_url"] == (
        "https://demo.example/incidents/incident-3"
    )

    diagnosis_paths = [
        path
        for path, _, _ in calls
        if path.endswith("/diagnosis")
    ]
    assert diagnosis_paths == [
        "/api/incidents/incident-1/diagnosis",
        "/api/incidents/incident-2/diagnosis",
        "/api/incidents/incident-3/diagnosis",
    ]


@pytest.mark.parametrize(
    "label",
    [
        "",
        "Has-Capitals",
        "contains spaces",
        "-starts-with-hyphen",
        "x" * 31,
    ],
)
def test_seed_demo_rejects_unsafe_labels(label: str) -> None:
    with pytest.raises(ValueError, match="label"):
        seed_demo(
            "https://demo.example",
            label,
            request=lambda *_args: (200, []),
        )
