import json
from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from backend.app.evaluation.corpus import DIAGNOSIS_EVALUATION_CORPUS
from backend.app.evaluation.production_inputs import (
    ScenarioProductionInput,
    build_corpus_production_inputs,
)
from backend.app.services.incident_diagnosis import build_diagnosis_prompt
from backend.app.services.incident_memory import build_embedding_input


REQUIRED_SNAPSHOT_KEYS = {
    "schema_version",
    "incident",
    "pipeline",
    "run",
    "observed",
}
REQUIRED_RULES = {
    "RUN_FAILED",
    "START_DELAY_EXCEEDED",
    "DURATION_EXCEEDED",
    "ROW_COUNT_BELOW_MINIMUM",
    "QUALITY_CHECKS_FAILED",
    "RUN_CANCELLED",
}
EXPECTED_RULE_SEVERITY = {
    "RUN_FAILED": "critical",
    "START_DELAY_EXCEEDED": "medium",
    "DURATION_EXCEEDED": "high",
    "ROW_COUNT_BELOW_MINIMUM": "high",
    "QUALITY_CHECKS_FAILED": "high",
    "RUN_CANCELLED": "high",
}
SEVERITY_RANK = {
    "medium": 0,
    "high": 1,
    "critical": 2,
}


def scenario_input_named(name: str) -> ScenarioProductionInput:
    return next(
        item
        for item in build_corpus_production_inputs()
        if item.scenario_name == name
    )


def test_builds_nine_inputs_in_canonical_order() -> None:
    inputs = build_corpus_production_inputs()

    assert len(inputs) == 9
    assert tuple(item.scenario_name for item in inputs) == tuple(
        scenario.name
        for scenario in DIAGNOSIS_EVALUATION_CORPUS
    )


def test_scenario_names_remain_aligned() -> None:
    inputs = build_corpus_production_inputs()

    assert all(
        item.scenario_name == scenario.name
        for item, scenario in zip(inputs, DIAGNOSIS_EVALUATION_CORPUS)
    )


def test_snapshots_have_complete_production_schema() -> None:
    for item in build_corpus_production_inputs():
        snapshot = item.incident_snapshot

        assert set(snapshot) == REQUIRED_SNAPSHOT_KEYS
        assert snapshot["schema_version"] == 1
        assert set(snapshot["incident"]) == {
            "id",
            "pipeline_run_id",
            "source",
            "title",
            "description",
            "severity",
            "status",
            "detected_at",
            "resolved_at",
            "details",
        }
        assert set(snapshot["pipeline"]) == {
            "id",
            "name",
            "description",
            "max_duration_seconds",
            "min_rows_processed",
            "max_start_delay_seconds",
            "enabled",
        }
        assert set(snapshot["run"]) == {
            "id",
            "external_run_id",
            "status",
            "scheduled_at",
            "started_at",
            "completed_at",
            "rows_processed",
            "quality_checks_failed",
            "metrics",
            "error_message",
            "logs",
        }
        assert set(snapshot["observed"]) == {
            "start_delay_seconds",
            "duration_seconds",
        }


def test_violations_preserve_facts_and_order() -> None:
    inputs = build_corpus_production_inputs()

    for item, scenario in zip(inputs, DIAGNOSIS_EVALUATION_CORPUS):
        violations = item.incident_snapshot["incident"]["details"][
            "violations"
        ]
        assert [violation["code"] for violation in violations] == list(
            scenario.deterministic_facts
        )
        assert all(set(violation) == {"code", "severity"}
                   for violation in violations)
        assert [
            violation["severity"]
            for violation in violations
        ] == [
            EXPECTED_RULE_SEVERITY[rule]
            for rule in scenario.deterministic_facts
        ]


def test_incident_severity_is_highest_violation_severity() -> None:
    for item in build_corpus_production_inputs():
        snapshot = item.incident_snapshot
        violations = snapshot["incident"]["details"]["violations"]
        expected_severity = max(
            (violation["severity"] for violation in violations),
            key=SEVERITY_RANK.__getitem__,
        )

        assert snapshot["incident"]["severity"] == expected_severity


def test_all_rules_have_required_corroborating_fields() -> None:
    inputs = build_corpus_production_inputs()

    for item, scenario in zip(inputs, DIAGNOSIS_EVALUATION_CORPUS):
        snapshot = item.incident_snapshot
        facts = set(scenario.deterministic_facts)
        pipeline = snapshot["pipeline"]
        run = snapshot["run"]
        observed = snapshot["observed"]

        if "RUN_FAILED" in facts:
            assert run["status"] == "failed"
        if "RUN_CANCELLED" in facts:
            assert run["status"] == "cancelled"
        if "START_DELAY_EXCEEDED" in facts:
            assert (
                observed["start_delay_seconds"]
                > pipeline["max_start_delay_seconds"]
            )
        if "DURATION_EXCEEDED" in facts:
            assert (
                observed["duration_seconds"]
                > pipeline["max_duration_seconds"]
            )
        if "ROW_COUNT_BELOW_MINIMUM" in facts:
            assert run["rows_processed"] < pipeline["min_rows_processed"]
        if "QUALITY_CHECKS_FAILED" in facts:
            assert run["quality_checks_failed"] > 0


def test_absent_rules_use_safe_defaults() -> None:
    inputs = build_corpus_production_inputs()

    for item, scenario in zip(inputs, DIAGNOSIS_EVALUATION_CORPUS):
        snapshot = item.incident_snapshot
        facts = set(scenario.deterministic_facts)
        pipeline = snapshot["pipeline"]
        run = snapshot["run"]
        observed = snapshot["observed"]

        if "RUN_FAILED" not in facts and "RUN_CANCELLED" not in facts:
            assert run["status"] == "succeeded"
        if "START_DELAY_EXCEEDED" not in facts:
            assert (
                observed["start_delay_seconds"]
                <= pipeline["max_start_delay_seconds"]
            )
        if "DURATION_EXCEEDED" not in facts:
            assert (
                observed["duration_seconds"]
                <= pipeline["max_duration_seconds"]
            )
        if "ROW_COUNT_BELOW_MINIMUM" not in facts:
            assert run["rows_processed"] >= pipeline["min_rows_processed"]
        if "QUALITY_CHECKS_FAILED" not in facts:
            assert run["quality_checks_failed"] == 0


def test_untrusted_evidence_is_only_in_current_logs() -> None:
    inputs = build_corpus_production_inputs()

    for item, scenario in zip(inputs, DIAGNOSIS_EVALUATION_CORPUS):
        snapshot = item.incident_snapshot
        violations = snapshot["incident"]["details"]["violations"]
        logs = snapshot["run"]["logs"]

        assert all(
            any(evidence in log["message"] for log in logs)
            for evidence in scenario.untrusted_evidence
        )
        assert not any(
            evidence in json.dumps(violations)
            for evidence in scenario.untrusted_evidence
        )


def test_similar_context_is_separate_and_quoted() -> None:
    inputs = build_corpus_production_inputs()

    for item, scenario in zip(inputs, DIAGNOSIS_EVALUATION_CORPUS):
        current_text = json.dumps(item.incident_snapshot)
        assert all(
            context not in current_text
            for context in scenario.similar_incident_context
        )
        assert len(item.similar_memories) == len(
            scenario.similar_incident_context
        )
        assert all(
            context
            in memory.incident_snapshot["run"]["logs"][0]["message"]
            and "Quoted untrusted evidence"
            in memory.incident_snapshot["run"]["logs"][0]["message"]
            for context, memory in zip(
                scenario.similar_incident_context,
                item.similar_memories,
            )
        )


def test_similar_memory_scores_are_inclusive_unit_interval() -> None:
    for item in build_corpus_production_inputs():
        for memory in item.similar_memories:
            assert 0.0 <= memory.distance <= 1.0
            assert 0.0 <= memory.similarity <= 1.0


def test_ids_are_valid_deterministic_and_unique() -> None:
    first = build_corpus_production_inputs()
    second = build_corpus_production_inputs()
    current_ids: list[str] = []
    memory_ids: list[UUID] = []

    for first_item, second_item in zip(first, second):
        first_snapshot = first_item.incident_snapshot
        second_snapshot = second_item.incident_snapshot
        assert first_snapshot["incident"]["id"] == (
            second_snapshot["incident"]["id"]
        )
        current_ids.extend(
            [
                first_snapshot["incident"]["id"],
                first_snapshot["pipeline"]["id"],
                first_snapshot["run"]["id"],
            ]
        )
        for memory in first_item.similar_memories:
            UUID(str(memory.incident_id))
            memory_ids.append(memory.incident_id)

    assert len(current_ids) == len(set(current_ids))
    assert len(memory_ids) == len(set(memory_ids))
    assert not set(current_ids) & {str(memory_id) for memory_id in memory_ids}


def test_embedding_input_serializes_current_and_historical_snapshots() -> None:
    for item in build_corpus_production_inputs():
        assert build_embedding_input(item.incident_snapshot)
        for memory in item.similar_memories:
            assert build_embedding_input(memory.incident_snapshot)


def test_diagnosis_prompt_accepts_inputs_and_preserves_context() -> None:
    for item, scenario in zip(
        build_corpus_production_inputs(),
        DIAGNOSIS_EVALUATION_CORPUS,
    ):
        prompt = json.loads(
            build_diagnosis_prompt(
                item.incident_snapshot,
                list(item.similar_memories),
            )
        )
        current_violations = prompt["current_incident"]["incident"][
            "details"
        ]["violations"]
        assert [item["code"] for item in current_violations] == list(
            scenario.deterministic_facts
        )
        assert len(prompt["similar_incidents"]) == len(
            scenario.similar_incident_context
        )
        prompt_text = json.dumps(prompt)
        assert all(
            context in prompt_text
            for context in scenario.similar_incident_context
        )


def test_generated_prompts_do_not_contain_incident_uuids() -> None:
    for item in build_corpus_production_inputs():
        prompt = build_diagnosis_prompt(
            item.incident_snapshot,
            list(item.similar_memories),
        )
        current_id = item.incident_snapshot["incident"]["id"]

        assert current_id not in prompt
        assert all(
            str(memory.incident_id) not in prompt
            for memory in item.similar_memories
        )


def test_repeated_construction_produces_equal_results() -> None:
    assert build_corpus_production_inputs() == (
        build_corpus_production_inputs()
    )


def test_production_input_and_corpus_tuple_are_immutable() -> None:
    inputs = build_corpus_production_inputs()
    production_input = inputs[0]

    assert isinstance(inputs, tuple)
    with pytest.raises(FrozenInstanceError):
        production_input.scenario_name = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        inputs[0] = production_input  # type: ignore[index]
    assert isinstance(production_input, ScenarioProductionInput)
