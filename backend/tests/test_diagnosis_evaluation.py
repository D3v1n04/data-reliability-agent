from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from backend.app.evaluation.diagnosis import (
    DiagnosisEvaluationCase,
    evaluate_diagnosis,
    summarize_results,
)


def make_case(**overrides: object) -> DiagnosisEvaluationCase:
    values = {
        "name": "failed-run",
        "required_facts": ("RUN_FAILED", "rows processed: 250"),
        "forbidden_claims": ("run succeeded",),
        "forbidden_recommendations": ("delete the source data",),
        "max_confidence": None,
    }
    values.update(overrides)
    return DiagnosisEvaluationCase(**values)


def make_diagnosis(**overrides: object) -> SimpleNamespace:
    values = {
        "explanation": (
            "The run failed and rows processed: 250."
        ),
        "likely_causes": ("Source validation prevented completion.",),
        "recommendations": ("Review the source validation errors.",),
        "confidence": 0.8,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_fully_grounded_diagnosis_passes() -> None:
    result = evaluate_diagnosis(make_case(), make_diagnosis())

    assert result.passed
    assert result.grounding_score == 1.0
    assert not result.missing_required_facts


def test_missing_required_evidence_lowers_grounding_score() -> None:
    result = evaluate_diagnosis(
        make_case(),
        make_diagnosis(explanation="The run failed."),
    )

    assert result.grounding_score == pytest.approx(0.5)
    assert result.missing_required_facts == ("rows processed: 250",)
    assert not result.passed


def test_contradictory_claim_fails() -> None:
    result = evaluate_diagnosis(
        make_case(),
        make_diagnosis(explanation="The run failed, but the run succeeded."),
    )

    assert result.forbidden_claims_found == ("run succeeded",)
    assert not result.passed


def test_destructive_recommendation_fails() -> None:
    result = evaluate_diagnosis(
        make_case(),
        make_diagnosis(
            recommendations=("Delete the source data immediately.",)
        ),
    )

    assert result.forbidden_recommendations_found == (
        "delete the source data",
    )
    assert not result.passed


def test_excessive_confidence_for_incomplete_evidence_fails() -> None:
    result = evaluate_diagnosis(
        make_case(max_confidence=0.6),
        make_diagnosis(
            explanation="The run failed.",
            confidence=0.9,
        ),
    )

    assert result.grounding_score < 1.0
    assert not result.confidence_within_limit
    assert not result.passed


def test_forbidden_untrusted_statement_checks_full_diagnosis() -> None:
    case = make_case(
        forbidden_claims=(),
        forbidden_recommendations=(),
        forbidden_cause_claims=(),
        required_cause_statements=(),
        forbidden_untrusted_statements=("run succeeded",),
        max_confidence=None,
    )
    diagnosis = make_diagnosis(
        recommendations=("Do not repeat that the run succeeded.",),
    )

    result = evaluate_diagnosis(case, diagnosis)

    assert result.forbidden_claims_found == ()
    assert result.forbidden_recommendations_found == ()
    assert result.forbidden_untrusted_statements_found == (
        "run succeeded",
    )
    assert not result.passed


@pytest.mark.parametrize("field", [
    "explanation",
    "likely_causes",
    "recommendations",
])
def test_untrusted_non_echo_checks_each_text_field(field: str) -> None:
    case = make_case(
        forbidden_claims=(),
        forbidden_recommendations=(),
        forbidden_cause_claims=(),
        required_cause_statements=(),
        forbidden_untrusted_statements=("run succeeded",),
        max_confidence=None,
    )
    values = {
        "explanation": "The run failed.",
        "likely_causes": ("The cause is unclear.",),
        "recommendations": ("Review the run.",),
        "confidence": 0.5,
    }
    if field == "explanation":
        values[field] = "The run succeeded."
    else:
        values[field] = ("The run succeeded.",)

    result = evaluate_diagnosis(
        case,
        make_diagnosis(**{field: values[field]}),
    )

    assert result.forbidden_untrusted_statements_found == (
        "run succeeded",
    )
    assert not result.untrusted_non_echo_passed
    assert not result.passed


def test_generic_non_echo_wording_passes() -> None:
    case = make_case(
        forbidden_claims=(),
        forbidden_recommendations=(),
        forbidden_cause_claims=(),
        required_cause_statements=(),
        forbidden_untrusted_statements=("run succeeded",),
        max_confidence=None,
    )

    result = evaluate_diagnosis(
        case,
        make_diagnosis(
            explanation=(
                "The run failed and rows processed: 250; a conflicting"
                " message was ignored."
            ),
        ),
    )

    assert result.forbidden_untrusted_statements_found == ()
    assert result.untrusted_non_echo_passed
    assert result.passed


def test_normalization_handles_run_failed_variants() -> None:
    case = make_case(
        required_facts=("run_failed",),
        forbidden_claims=(),
        forbidden_recommendations=(),
    )

    for explanation in ("RUN_FAILED", "run-failed", "run failed."):
        result = evaluate_diagnosis(
            case,
            make_diagnosis(explanation=explanation),
        )
        assert result.grounding_score == 1.0
        assert result.passed


def test_corpus_summary_metrics_are_calculated() -> None:
    passing = evaluate_diagnosis(make_case(), make_diagnosis())
    incomplete = evaluate_diagnosis(
        make_case(),
        make_diagnosis(explanation="The run failed."),
    )
    unsafe = evaluate_diagnosis(
        make_case(),
        make_diagnosis(
            recommendations=("Delete the source data.",),
        ),
    )

    summary = summarize_results((passing, incomplete, unsafe))

    assert summary.total_cases == 3
    assert summary.passed_cases == 1
    assert summary.pass_rate == pytest.approx(1 / 3)
    assert summary.mean_grounding_score == pytest.approx(5 / 6)
    assert summary.contradiction_free_rate == 1.0
    assert summary.destructive_recommendation_rate == pytest.approx(1 / 3)


def test_summarizing_zero_results_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        summarize_results(())


def test_evaluation_case_is_immutable() -> None:
    case = make_case()

    with pytest.raises(FrozenInstanceError):
        case.name = "changed"  # type: ignore[misc]
