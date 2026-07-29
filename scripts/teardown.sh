#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stack_name="${STACK_NAME:-data-reliability-agent-production}"
aws_region="${AWS_REGION:-us-east-1}"
aws_profile_arguments=()

if [[ "${CONFIRM_TEARDOWN:-}" != "yes" ]]; then
  echo "Set CONFIRM_TEARDOWN=yes to delete stack ${stack_name}." >&2
  exit 2
fi

if [[ -n "${AWS_PROFILE:-}" ]]; then
  aws_profile_arguments=(--profile "${AWS_PROFILE}")
fi

frontend_bucket="$(
  aws "${aws_profile_arguments[@]}" --region "${aws_region}" \
    cloudformation describe-stacks \
    --stack-name "${stack_name}" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
    --output text
)"

bucket_profile_arguments=()
if [[ -n "${AWS_PROFILE:-}" ]]; then
  bucket_profile_arguments=(--profile "${AWS_PROFILE}")
fi

"${repository_root}/.venv/bin/python" \
  "${repository_root}/scripts/empty_versioned_bucket.py" \
  --bucket "${frontend_bucket}" \
  --confirm-bucket "${frontend_bucket}" \
  --region "${aws_region}" \
  "${bucket_profile_arguments[@]}"

sam delete \
  --stack-name "${stack_name}" \
  --region "${aws_region}" \
  "${aws_profile_arguments[@]}" \
  --no-prompts

echo "The application stack and frontend objects were removed."
echo "The SSM database parameter was intentionally preserved."
