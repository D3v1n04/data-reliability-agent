from dataclasses import FrozenInstanceError

import pytest

from backend.app.evaluation.corpus import (
    DIAGNOSIS_EVALUATION_CORPUS,
)
from backend.app.evaluation.runner import (
    DiagnosisCorpusEvaluation,
    ScenarioEvaluationResult,
    evaluate_corpus_outputs,
)


def reference_diagnoses() -> dict[str, object]:
    return {
        scenario.name: scenario.reference_diagnosis
        for scenario in DIAGNOSIS_EVALUATION_CORPUS
    }


def test_reference_diagnoses_produce_passing_corpus_evaluation() -> None:
    evaluation = evaluate_corpus_outputs(reference_diagnoses())

    assert len(evaluation.scenario_results) == 9
    assert evaluation.summary.total_cases == 9
    assert evaluation.summary.passed_cases == 9
    assert evaluation.summary.pass_rate == 1.0
    assert evaluation.summary.mean_grounding_score == 1.0
    assert evaluation.summary.contradiction_free_rate == 1.0
    assert evaluation.summary.destructive_recommendation_rate == 0.0


def test_results_preserve_canonical_corpus_order() -> None:
    diagnoses = reference_diagnoses()
    evaluation = evaluate_corpus_outputs(
        dict(reversed(tuple(diagnoses.items())))
    )

    assert tuple(
        item.scenario_name
        for item in evaluation.scenario_results
    ) == tuple(
        scenario.name
        for scenario in DIAGNOSIS_EVALUATION_CORPUS
    )


def test_missing_scenario_output_is_rejected() -> None:
    diagnoses = reference_diagnoses()
    missing_name = DIAGNOSIS_EVALUATION_CORPUS[0].name
    del diagnoses[missing_name]

    with pytest.raises(ValueError, match=missing_name):
        evaluate_corpus_outputs(diagnoses)


def test_unknown_extra_scenario_output_is_rejected() -> None:
    diagnoses = reference_diagnoses()
    diagnoses["synthetic unknown scenario"] = (
        DIAGNOSIS_EVALUATION_CORPUS[0].reference_diagnosis
    )

    with pytest.raises(ValueError, match="synthetic unknown scenario"):
        evaluate_corpus_outputs(diagnoses)


def test_unsafe_diagnosis_fails_and_changes_summary() -> None:
    diagnoses = reference_diagnoses()
    scenario = DIAGNOSIS_EVALUATION_CORPUS[2]
    reference = scenario.reference_diagnosis
    diagnoses[scenario.name] = type(reference)(
        explanation=f"{reference.explanation} The run succeeded.",
        likely_causes=reference.likely_causes,
        recommendations=reference.recommendations,
        confidence=reference.confidence,
    )

    evaluation = evaluate_corpus_outputs(diagnoses)
    changed_result = evaluation.scenario_results[2].result

    assert not changed_result.passed
    assert evaluation.summary.passed_cases == 8
    assert evaluation.summary.pass_rate == pytest.approx(8 / 9)
    assert evaluation.summary.contradiction_free_rate == pytest.approx(8 / 9)


def test_repeated_evaluation_of_identical_inputs_is_equal() -> None:
    diagnoses = reference_diagnoses()

    assert evaluate_corpus_outputs(diagnoses) == (
        evaluate_corpus_outputs(diagnoses)
    )


def test_returned_dataclasses_and_results_tuple_are_immutable() -> None:
    evaluation = evaluate_corpus_outputs(reference_diagnoses())
    scenario_result = evaluation.scenario_results[0]

    assert isinstance(evaluation, DiagnosisCorpusEvaluation)
    assert isinstance(scenario_result, ScenarioEvaluationResult)
    assert isinstance(evaluation.scenario_results, tuple)
    with pytest.raises(FrozenInstanceError):
        evaluation.summary = evaluation.summary  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        scenario_result.category = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        evaluation.scenario_results[0] = scenario_result  # type: ignore[index]
