#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${repository_root}/.venv/bin/python" -m compileall -q \
  "${repository_root}/backend/app" \
  "${repository_root}/backend/migrations"

npm --prefix "${repository_root}/frontend" run lint
VITE_API_BASE_URL="" \
  npm --prefix "${repository_root}/frontend" run build

sam build \
  --template-file "${repository_root}/infra/template.yaml"
