#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stack_name="${STACK_NAME:-data-reliability-agent-production}"
aws_region="${AWS_REGION:-us-east-1}"
database_parameter_name="${DATABASE_URL_SSM_PARAMETER:-/data-reliability-agent/production/database-url}"
alarm_email="${ALARM_NOTIFICATION_EMAIL:-}"
bedrock_text_model_id="${BEDROCK_TEXT_MODEL_ID:-amazon.nova-lite-v1:0}"
bedrock_embedding_model_id="${BEDROCK_EMBEDDING_MODEL_ID:-amazon.titan-embed-text-v2:0}"
backend_reserved_concurrency="${BACKEND_RESERVED_CONCURRENCY:-0}"
aws_profile_arguments=()

if [[ -n "${AWS_PROFILE:-}" ]]; then
  aws_profile_arguments=(--profile "${AWS_PROFILE}")
fi

aws "${aws_profile_arguments[@]}" --region "${aws_region}" \
  ssm get-parameter \
  --name "${database_parameter_name}" \
  --query 'Parameter.Name' \
  --output text >/dev/null

"${repository_root}/scripts/build_production.sh"

parameter_overrides=(
  "Environment=production"
  "DatabaseUrlParameterName=${database_parameter_name}"
  "BedrockTextModelId=${bedrock_text_model_id}"
  "BedrockEmbeddingModelId=${bedrock_embedding_model_id}"
  "BackendReservedConcurrency=${backend_reserved_concurrency}"
)

if [[ -n "${alarm_email}" ]]; then
  parameter_overrides+=("AlarmNotificationEmail=${alarm_email}")
fi

sam deploy \
  --template-file "${repository_root}/.aws-sam/build/template.yaml" \
  --stack-name "${stack_name}" \
  --region "${aws_region}" \
  "${aws_profile_arguments[@]}" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --resolve-image-repos \
  --no-fail-on-empty-changeset \
  --parameter-overrides "${parameter_overrides[@]}"

"${repository_root}/scripts/deploy_frontend.sh"
