"""Controlled Nova Lite evaluation of the synthetic diagnosis corpus.

Importing and unit-testing this module performs no live calls. The explicit
confirmation flag authorizes nine sequential Nova Lite calls. The command
evaluates model outputs but does not modify application data. Diagnosis text
is printed only by this explicitly confirmed synthetic-corpus evaluation
command to support failure analysis; production API logging is unchanged.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Sequence

from backend.app.core.config import Settings, get_settings
from backend.app.evaluation.production_inputs import (
    build_corpus_production_inputs,
)
from backend.app.evaluation.runner import (
    DiagnosisCorpusEvaluation,
    evaluate_corpus_outputs,
)
from backend.app.services.bedrock import BedrockService
from backend.app.services.incident_diagnosis import (
    GeneratedIncidentDiagnosis,
    generate_incident_diagnosis,
)


@dataclass(frozen=True)
class BedrockCorpusEvaluation:
    """Generated diagnoses and their immutable corpus evaluation."""

    diagnoses_by_scenario: tuple[
        tuple[str, GeneratedIncidentDiagnosis], ...
    ]
    corpus_evaluation: DiagnosisCorpusEvaluation

    @property
    def generated_diagnoses(
        self,
    ) -> tuple[tuple[str, GeneratedIncidentDiagnosis], ...]:
        """Return generated diagnoses in canonical scenario order."""
        return self.diagnoses_by_scenario


def evaluate_corpus_with_bedrock(
    bedrock_service: BedrockService,
) -> BedrockCorpusEvaluation:
    """Generate and evaluate one diagnosis per scenario sequentially.

    The service is injected so this function itself never constructs a client.
    It performs no embedding, retrieval, database, API, or persistence work.
    """
    production_inputs = build_corpus_production_inputs()
    generated: list[tuple[str, GeneratedIncidentDiagnosis]] = []

    for production_input in production_inputs:
        diagnosis = generate_incident_diagnosis(
            production_input.incident_snapshot,
            list(production_input.similar_memories),
            bedrock_service,
        )
        generated.append(
            (production_input.scenario_name, diagnosis)
        )

    diagnoses_by_scenario = dict(generated)
    corpus_evaluation = evaluate_corpus_outputs(
        diagnoses_by_scenario
    )

    return BedrockCorpusEvaluation(
        diagnoses_by_scenario=tuple(generated),
        corpus_evaluation=corpus_evaluation,
    )


def _configuration_error(settings: Settings) -> str | None:
    required = {
        "aws_profile": "data-reliability-agent",
        "aws_region": "us-east-1",
        "bedrock_text_model_id": "amazon.nova-lite-v1:0",
    }

    for field_name, expected in required.items():
        if getattr(settings, field_name) != expected:
            return (
                f"Required {field_name} is {expected!r} for this command."
            )

    return None


def _result_payload(
    evaluation: BedrockCorpusEvaluation,
    settings: Settings,
) -> dict[str, object]:
    summary = evaluation.corpus_evaluation.summary
    scenarios = evaluation.corpus_evaluation.scenario_results
    diagnoses = dict(evaluation.diagnoses_by_scenario)

    return {
        "model_id": settings.bedrock_text_model_id,
        "region": settings.aws_region,
        "total_cases": summary.total_cases,
        "passed_cases": summary.passed_cases,
        "pass_rate": summary.pass_rate,
        "mean_grounding_score": summary.mean_grounding_score,
        "contradiction_free_rate": summary.contradiction_free_rate,
        "destructive_recommendation_rate": (
            summary.destructive_recommendation_rate
        ),
        "scenarios": [
            {
                "scenario_name": item.scenario_name,
                "category": item.category,
                "diagnosis": {
                    "explanation": diagnoses[
                        item.scenario_name
                    ].explanation,
                    "likely_causes": diagnoses[
                        item.scenario_name
                    ].likely_causes,
                    "recommendations": diagnoses[
                        item.scenario_name
                    ].recommendations,
                    "confidence": diagnoses[
                        item.scenario_name
                    ].confidence,
                },
                "result": {
                    "case_name": item.result.case_name,
                    "grounding_score": item.result.grounding_score,
                    "missing_required_facts": (
                        item.result.missing_required_facts
                    ),
                    "forbidden_claims_found": (
                        item.result.forbidden_claims_found
                    ),
                    "forbidden_recommendations_found": (
                        item.result.forbidden_recommendations_found
                    ),
                    "confidence_within_limit": (
                        item.result.confidence_within_limit
                    ),
                    "passed": item.result.passed,
                    "forbidden_cause_claims_found": (
                        item.result.forbidden_cause_claims_found
                    ),
                    "missing_required_cause_statements": (
                        item.result.missing_required_cause_statements
                    ),
                    "cause_grounding_passed": (
                        item.result.cause_grounding_passed
                    ),
                    "forbidden_untrusted_statements_found": (
                        item.result.forbidden_untrusted_statements_found
                    ),
                    "untrusted_non_echo_passed": (
                        item.result.untrusted_non_echo_passed
                    ),
                },
            }
            for item in scenarios
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the explicitly confirmed live nine-scenario evaluation."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Nova Lite on the synthetic diagnosis corpus."
        ),
    )
    parser.add_argument(
        "--confirm-live-bedrock",
        action="store_true",
        help="Authorize exactly nine sequential Nova Lite calls.",
    )
    args = parser.parse_args(argv)

    if not args.confirm_live_bedrock:
        print(
            "Refusing live Bedrock evaluation without "
            "--confirm-live-bedrock.",
            file=sys.stderr,
        )
        return 2

    try:
        settings = get_settings()
    except Exception:
        print("Unable to load application settings.", file=sys.stderr)
        return 2

    configuration_error = _configuration_error(settings)
    if configuration_error is not None:
        print(configuration_error, file=sys.stderr)
        return 2

    try:
        bedrock_service = BedrockService(settings=settings)
        evaluation = evaluate_corpus_with_bedrock(bedrock_service)
    except Exception:
        print("Live diagnosis corpus evaluation failed.", file=sys.stderr)
        return 1

    print(
        json.dumps(
            _result_payload(evaluation, settings),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0 if evaluation.corpus_evaluation.summary.pass_rate == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
