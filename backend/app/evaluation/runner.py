"""Offline evaluation runner for supplied diagnosis outputs.

This runner evaluates caller-supplied diagnoses against the canonical corpus;
it does not generate diagnoses or call a model or external service.
"""

from dataclasses import dataclass
from typing import Mapping

from backend.app.evaluation.corpus import DIAGNOSIS_EVALUATION_CORPUS
from backend.app.evaluation.diagnosis import (
    DiagnosisEvaluationResult,
    DiagnosisEvaluationSummary,
    DiagnosisLike,
    evaluate_diagnosis,
    summarize_results,
)


@dataclass(frozen=True)
class ScenarioEvaluationResult:
    """Evaluation result for one canonical corpus scenario."""

    scenario_name: str
    category: str
    result: DiagnosisEvaluationResult


@dataclass(frozen=True)
class DiagnosisCorpusEvaluation:
    """Ordered scenario results and their aggregate summary."""

    scenario_results: tuple[ScenarioEvaluationResult, ...]
    summary: DiagnosisEvaluationSummary


def evaluate_corpus_outputs(
    diagnoses_by_scenario: Mapping[str, DiagnosisLike],
) -> DiagnosisCorpusEvaluation:
    """Evaluate exactly one supplied diagnosis for every corpus scenario."""
    expected_names = {
        scenario.name
        for scenario in DIAGNOSIS_EVALUATION_CORPUS
    }
    supplied_names = set(diagnoses_by_scenario)
    missing_names = expected_names - supplied_names
    unknown_names = supplied_names - expected_names

    if missing_names or unknown_names:
        details: list[str] = []
        if missing_names:
            details.append(
                "missing scenario names: "
                + ", ".join(sorted(missing_names))
            )
        if unknown_names:
            details.append(
                "unknown scenario names: "
                + ", ".join(sorted(unknown_names))
            )
        message = "; ".join(details)
        raise ValueError(
            "Invalid diagnosis corpus outputs (" + message + ")"
        )

    scenario_results = tuple(
        ScenarioEvaluationResult(
            scenario_name=scenario.name,
            category=scenario.category,
            result=evaluate_diagnosis(
                scenario.evaluation_case,
                diagnoses_by_scenario[scenario.name],
            ),
        )
        for scenario in DIAGNOSIS_EVALUATION_CORPUS
    )
    summary = summarize_results(
        tuple(item.result for item in scenario_results)
    )

    return DiagnosisCorpusEvaluation(
        scenario_results=scenario_results,
        summary=summary,
    )
