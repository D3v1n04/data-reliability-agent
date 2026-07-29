import json
import importlib
import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from backend.app.core.config import Settings
from backend.app.evaluation.bedrock_corpus import (
    BedrockCorpusEvaluation,
    evaluate_corpus_with_bedrock,
    main,
)
from backend.app.evaluation.corpus import DIAGNOSIS_EVALUATION_CORPUS
from backend.app.evaluation.production_inputs import (
    build_corpus_production_inputs,
)
from backend.app.services.incident_diagnosis import (
    CAUSE_GROUNDING_INSUFFICIENCY_STATEMENT,
    GeneratedIncidentDiagnosis,
)


def settings() -> Settings:
    return Settings(
        database_url="postgresql://offline-test",
        aws_profile="data-reliability-agent",
        aws_region="us-east-1",
        bedrock_text_model_id="amazon.nova-lite-v1:0",
    )


def diagnosis_for(index: int) -> GeneratedIncidentDiagnosis:
    reference = DIAGNOSIS_EVALUATION_CORPUS[index].reference_diagnosis
    return GeneratedIncidentDiagnosis(
        explanation=reference.explanation,
        likely_causes=list(reference.likely_causes),
        recommendations=list(reference.recommendations),
        confidence=reference.confidence,
        evidence={},
    )


def generation_side_effect(
    calls: list[tuple[str, object, object]],
):
    def generate(snapshot, memories, service):
        index = len(calls)
        calls.append(
            (
                snapshot["incident"]["title"],
                snapshot,
                tuple(memories),
            )
        )
        return diagnosis_for(index)

    return generate


def test_import_has_no_client_or_inference() -> None:
    module_name = "backend.app.evaluation.bedrock_corpus"
    original_module = sys.modules[module_name]
    sys.modules.pop(module_name)

    try:
        with patch("boto3.Session") as session_class, patch(
            "boto3.client"
        ) as boto_client, patch(
            "backend.app.services.bedrock.BedrockService"
        ) as service_class, patch(
            "backend.app.services.incident_diagnosis."
            "generate_incident_diagnosis"
        ) as generate:
            fresh_module = importlib.import_module(module_name)

            assert fresh_module.BedrockService is service_class
            assert (
                fresh_module.generate_incident_diagnosis
                is generate
            )
            session_class.assert_not_called()
            boto_client.assert_not_called()
            service_class.assert_not_called()
            generate.assert_not_called()
    finally:
        sys.modules[module_name] = original_module


def test_injected_function_makes_nine_sequential_calls() -> None:
    calls: list[tuple[str, object, object]] = []
    service = Mock()
    inputs = build_corpus_production_inputs()

    with patch(
        "backend.app.evaluation.bedrock_corpus.generate_incident_diagnosis",
        side_effect=generation_side_effect(calls),
    ) as generate:
        evaluation = evaluate_corpus_with_bedrock(service)

    assert generate.call_count == 9
    assert tuple(
        item[0]
        for item in evaluation.generated_diagnoses
    ) == tuple(item.scenario_name for item in inputs)
    assert tuple(
        item[0]
        for item in calls
    ) == tuple(
        item.incident_snapshot["incident"]["title"]
        for item in inputs
    )
    for call, production_input in zip(calls, inputs):
        assert call[1] == production_input.incident_snapshot
        assert call[2] == production_input.similar_memories


def test_all_reference_like_outputs_pass_nine_of_nine() -> None:
    service = Mock()

    with patch(
        "backend.app.evaluation.bedrock_corpus.generate_incident_diagnosis",
        side_effect=lambda snapshot, memories, service: diagnosis_for(
            int(snapshot["incident"]["title"].split()[-1])
        ),
    ):
        evaluation = evaluate_corpus_with_bedrock(service)

    assert evaluation.corpus_evaluation.summary.total_cases == 9
    assert evaluation.corpus_evaluation.summary.passed_cases == 9
    assert evaluation.corpus_evaluation.summary.pass_rate == 1.0


def test_speculative_outputs_are_corrected_before_corpus_evaluation() -> None:
    service = Mock()
    discarded_causes = [
        "An internal error caused the incident.",
        "A network error caused the incident.",
        "A dependency failure caused the incident.",
        "A configuration error caused the incident.",
        "Resource exhaustion caused the incident.",
        "A timeout caused the incident.",
        "A database outage caused the incident.",
        "A source pause caused the incident.",
        "Historical success explains the incident.",
    ]
    service.generate_structured_output.side_effect = [
        {
            "explanation": scenario.reference_diagnosis.explanation,
            "likely_causes": [discarded_causes[index]],
            "recommendations": list(
                scenario.reference_diagnosis.recommendations
            ),
            "confidence": 0.8,
        }
        for index, scenario in enumerate(
            DIAGNOSIS_EVALUATION_CORPUS
        )
    ]

    evaluation = evaluate_corpus_with_bedrock(service)

    assert service.generate_structured_output.call_count == 9
    assert evaluation.corpus_evaluation.summary.passed_cases == 9
    for _, diagnosis in evaluation.generated_diagnoses:
        assert diagnosis.likely_causes == [
            CAUSE_GROUNDING_INSUFFICIENCY_STATEMENT
        ]
        assert diagnosis.confidence == 0.6
        assert not any(
            cause in json.dumps(diagnosis.evidence)
            for cause in discarded_causes
        )


def test_unsafe_output_changes_individual_and_aggregate_results() -> None:
    service = Mock()
    generated = [diagnosis_for(index) for index in range(9)]
    unsafe = generated[2]
    generated[2] = GeneratedIncidentDiagnosis(
        explanation=f"{unsafe.explanation} The run succeeded.",
        likely_causes=unsafe.likely_causes,
        recommendations=unsafe.recommendations,
        confidence=unsafe.confidence,
        evidence=unsafe.evidence,
    )

    with patch(
        "backend.app.evaluation.bedrock_corpus.generate_incident_diagnosis",
        side_effect=generated,
    ):
        evaluation = evaluate_corpus_with_bedrock(service)

    result = evaluation.corpus_evaluation.scenario_results[2].result
    assert not result.passed
    assert evaluation.corpus_evaluation.summary.passed_cases == 8


def test_repeated_mocked_runs_are_equal() -> None:
    service = Mock()
    with patch(
        "backend.app.evaluation.bedrock_corpus.generate_incident_diagnosis",
        side_effect=[diagnosis_for(index) for index in range(9)] * 2,
    ):
        first = evaluate_corpus_with_bedrock(service)
        second = evaluate_corpus_with_bedrock(service)

    assert first == second


def test_returned_dataclasses_and_tuples_are_immutable() -> None:
    service = Mock()
    with patch(
        "backend.app.evaluation.bedrock_corpus.generate_incident_diagnosis",
        side_effect=[diagnosis_for(index) for index in range(9)],
    ):
        evaluation = evaluate_corpus_with_bedrock(service)

    assert isinstance(evaluation, BedrockCorpusEvaluation)
    assert isinstance(evaluation.diagnoses_by_scenario, tuple)
    with pytest.raises(FrozenInstanceError):
        evaluation.corpus_evaluation = (
            evaluation.corpus_evaluation
        )  # type: ignore[misc]
    with pytest.raises(TypeError):
        evaluation.diagnoses_by_scenario[0] = (
            "changed",
            None,
        )  # type: ignore[index]


def test_cli_refuses_without_confirmation_before_settings_or_service() -> None:
    with patch(
        "backend.app.evaluation.bedrock_corpus.get_settings"
    ) as get_settings_mock, patch(
        "backend.app.evaluation.bedrock_corpus.BedrockService"
    ) as service_class:
        assert main([]) != 0

    get_settings_mock.assert_not_called()
    service_class.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("aws_profile", "wrong-profile"),
        ("aws_region", "eu-west-1"),
        ("bedrock_text_model_id", "wrong-model"),
    ],
)
def test_cli_rejects_incorrect_live_configuration(
    field: str,
    value: str,
) -> None:
    configured = settings()
    setattr(configured, field, value)
    with patch(
        "backend.app.evaluation.bedrock_corpus.get_settings",
        return_value=configured,
    ), patch(
        "backend.app.evaluation.bedrock_corpus.BedrockService"
    ) as service_class:
        assert main(["--confirm-live-bedrock"]) != 0

    service_class.assert_not_called()


def test_confirmed_cli_constructs_one_service_and_prints_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configured = settings()
    service = Mock()
    calls: list[tuple[str, object, object]] = []
    with patch(
        "backend.app.evaluation.bedrock_corpus.get_settings",
        return_value=configured,
    ), patch(
        "backend.app.evaluation.bedrock_corpus.BedrockService",
        return_value=service,
    ) as service_class, patch(
        "backend.app.evaluation.bedrock_corpus.generate_incident_diagnosis",
        side_effect=generation_side_effect(calls),
    ):
        assert main(["--confirm-live-bedrock"]) == 0

    service_class.assert_called_once_with(settings=configured)
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["model_id"] == "amazon.nova-lite-v1:0"
    assert payload["region"] == "us-east-1"
    assert payload["total_cases"] == 9
    assert payload["passed_cases"] == 9
    assert [
        item["scenario_name"]
        for item in payload["scenarios"]
    ] == [scenario.name for scenario in DIAGNOSIS_EVALUATION_CORPUS]
    for item in payload["scenarios"]:
        assert set(item["diagnosis"]) == {
            "explanation",
            "likely_causes",
            "recommendations",
            "confidence",
        }
        assert "evidence" not in item["diagnosis"]
        assert item["result"]["forbidden_cause_claims_found"] == []
        assert item["result"]["missing_required_cause_statements"] == []
        assert item["result"]["cause_grounding_passed"]
        assert (
            item["result"]["forbidden_untrusted_statements_found"]
            == []
        )
        assert item["result"]["untrusted_non_echo_passed"]
    assert all(
        "evidence" not in item["diagnosis"]
        for item in payload["scenarios"]
    )
    assert not any(
        memory_id in output
        for production_input in build_corpus_production_inputs()
        for memory_id in [
            production_input.incident_snapshot["incident"]["id"],
            *[
                str(memory.incident_id)
                for memory in production_input.similar_memories
            ],
        ]
    )
    assert "postgresql://offline-test" not in output
    assert "generate_incident_diagnosis" not in output


def test_cli_json_excludes_discarded_raw_model_causes(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = settings()
    service = Mock()
    environment_secret = "offline-environment-secret"
    monkeypatch.setenv("PHASE_7_TEST_SECRET", environment_secret)
    discarded_causes = [
        f"Discarded speculative model cause {index}."
        for index in range(9)
    ]
    service.generate_structured_output.side_effect = [
        {
            "explanation": scenario.reference_diagnosis.explanation,
            "likely_causes": [discarded_causes[index]],
            "recommendations": list(
                scenario.reference_diagnosis.recommendations
            ),
            "confidence": 0.8,
        }
        for index, scenario in enumerate(
            DIAGNOSIS_EVALUATION_CORPUS
        )
    ]
    with patch(
        "backend.app.evaluation.bedrock_corpus.get_settings",
        return_value=configured,
    ), patch(
        "backend.app.evaluation.bedrock_corpus.BedrockService",
        return_value=service,
    ):
        assert main(["--confirm-live-bedrock"]) == 0

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert all(cause not in output for cause in discarded_causes)
    assert environment_secret not in output
    assert "postgresql://offline-test" not in output
    assert all(
        scenario["diagnosis"]["likely_causes"] == [
            CAUSE_GROUNDING_INSUFFICIENCY_STATEMENT
        ]
        and scenario["diagnosis"]["confidence"] == 0.6
        and "evidence" not in scenario["diagnosis"]
        for scenario in payload["scenarios"]
    )


def test_cli_returns_nonzero_for_failed_evaluation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configured = settings()
    service = Mock()
    generated = [diagnosis_for(index) for index in range(9)]
    reference = generated[0]
    generated[0] = GeneratedIncidentDiagnosis(
        explanation=reference.explanation,
        likely_causes=["A network error caused the failure."],
        recommendations=reference.recommendations,
        confidence=reference.confidence,
        evidence=reference.evidence,
    )
    with patch(
        "backend.app.evaluation.bedrock_corpus.get_settings",
        return_value=configured,
    ), patch(
        "backend.app.evaluation.bedrock_corpus.BedrockService",
        return_value=service,
    ), patch(
        "backend.app.evaluation.bedrock_corpus.generate_incident_diagnosis",
        side_effect=generated,
    ):
        assert main(["--confirm-live-bedrock"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["total_cases"] == 9
    assert payload["passed_cases"] < 9
    assert len(payload["scenarios"]) == 9
    assert [
        scenario["scenario_name"]
        for scenario in payload["scenarios"]
    ] == [scenario.name for scenario in DIAGNOSIS_EVALUATION_CORPUS]
    assert any(
        not scenario["result"]["passed"]
        for scenario in payload["scenarios"]
    )
    failed_result = payload["scenarios"][0]["result"]
    assert failed_result["grounding_score"] == 1.0
    assert failed_result["forbidden_claims_found"] == []
    assert failed_result["confidence_within_limit"]
    assert failed_result["forbidden_cause_claims_found"] == [
        "network error"
    ]
    assert not failed_result["cause_grounding_passed"]
    assert not failed_result["passed"]
    assert all(
        {
            "forbidden_cause_claims_found",
            "missing_required_cause_statements",
            "cause_grounding_passed",
            "forbidden_untrusted_statements_found",
            "untrusted_non_echo_passed",
        }
        <= set(scenario["result"])
        for scenario in payload["scenarios"]
    )
    assert all(
        set(scenario["diagnosis"]) == {
            "explanation",
            "likely_causes",
            "recommendations",
            "confidence",
        }
        and "evidence" not in scenario["diagnosis"]
        for scenario in payload["scenarios"]
    )


def test_cli_hides_generation_exception_details_and_secrets(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configured = settings()
    secret = "super-secret-value"
    with patch(
        "backend.app.evaluation.bedrock_corpus.get_settings",
        return_value=configured,
    ), patch(
        "backend.app.evaluation.bedrock_corpus.BedrockService",
        return_value=Mock(),
    ), patch(
        "backend.app.evaluation.bedrock_corpus.generate_incident_diagnosis",
        side_effect=RuntimeError(secret),
    ):
        assert main(["--confirm-live-bedrock"]) != 0

    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err


def test_injected_path_avoids_external_or_persistence_paths() -> None:
    service = Mock()
    calls: list[tuple[str, object, object]] = []
    with patch(
        "backend.app.evaluation.bedrock_corpus.generate_incident_diagnosis",
        side_effect=generation_side_effect(calls),
    ), patch(
        (
            "backend.app.evaluation.production_inputs."
            "build_corpus_production_inputs"
        ),
        wraps=build_corpus_production_inputs,
    ), patch(
        "backend.app.evaluation.bedrock_corpus.evaluate_corpus_outputs",
    ) as evaluate:
        evaluate.return_value = SimpleNamespace(
            summary=SimpleNamespace(pass_rate=1.0),
            scenario_results=(),
        )
        evaluate_corpus_with_bedrock(service)

    assert service.generate_embedding.call_count == 0
    assert service.generate_text.call_count == 0
    assert service.client.converse.call_count == 0
    evaluate.assert_called_once()
