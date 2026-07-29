#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stack_name="${STACK_NAME:-data-reliability-agent-production}"
aws_region="${AWS_REGION:-us-east-1}"
aws_profile_arguments=()

if [[ -n "${AWS_PROFILE:-}" ]]; then
  aws_profile_arguments=(--profile "${AWS_PROFILE}")
fi

VITE_API_BASE_URL="" \
  npm --prefix "${repository_root}/frontend" run build

frontend_bucket="$(
  aws "${aws_profile_arguments[@]}" --region "${aws_region}" \
    cloudformation describe-stacks \
    --stack-name "${stack_name}" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
    --output text
)"

distribution_id="$(
  aws "${aws_profile_arguments[@]}" --region "${aws_region}" \
    cloudformation describe-stacks \
    --stack-name "${stack_name}" \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
    --output text
)"

aws "${aws_profile_arguments[@]}" --region "${aws_region}" \
  s3 sync \
  "${repository_root}/frontend/dist/" \
  "s3://${frontend_bucket}/" \
  --delete

aws "${aws_profile_arguments[@]}" --region "${aws_region}" \
  cloudfront create-invalidation \
  --distribution-id "${distribution_id}" \
  --paths "/*" >/dev/null

aws "${aws_profile_arguments[@]}" --region "${aws_region}" \
  cloudformation describe-stacks \
  --stack-name "${stack_name}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApplicationUrl'].OutputValue" \
  --output text
