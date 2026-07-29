# Data Reliability Agent

Data Reliability Agent detects pipeline failures with deterministic rules,
stores incident memory in CockroachDB, and uses Amazon Bedrock to generate
evidence-grounded investigation guidance.

The governing principle is:

> Deterministic rules decide what happened. AI helps explain why it may have
> happened and what to investigate next.

## Current capabilities

- FastAPI backend and React/TypeScript dashboard
- CockroachDB pipelines, immutable runs, incidents, diagnoses, and vector memory
- Deterministic pipeline reliability rules and idempotent incident creation
- Incident lifecycle: `open → investigating → resolved`
- Amazon Nova Lite structured diagnoses
- Titan Text Embeddings V2 normalized 256-dimensional incident embeddings
- Similar incident retrieval through CockroachDB vector distance
- Responsive pipeline, run, incident, evidence, diagnosis, and history views
- Cost-conscious AWS SAM deployment through CloudFront, S3, API Gateway, and
  Lambda
- Runtime IAM roles, SSM SecureString configuration, bounded dependency calls,
  structured logs, metrics, and CloudWatch alarms
- Backend, frontend component, and Playwright workflow tests

MCP is not part of the completed implementation and remains a later explicit
Phase 8.5 candidate. Autonomous remediation and automatic pipeline changes
remain outside the current scope.

## Run locally

The backend loads its CockroachDB and Bedrock configuration from the root
`.env`. Use `.env.example` as the configuration contract. Local Bedrock access
uses the `data-reliability-agent` AWS profile in `us-east-1`.

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Verify

```bash
python -m pytest -q
python -m compileall -q backend/app backend/migrations

cd frontend
npm run lint
npm run build
npm test
npx playwright install chromium
npm run test:e2e
```

The browser workflow covered by Playwright is:

`pipeline failure → run evidence → incident evidence → diagnosis → similar
history → investigating → resolved`

## Deploy to AWS

Phase 8 uses a private S3/CloudFront frontend and an API Gateway/Lambda
FastAPI backend. Lambda uses its execution role, loads the restricted
CockroachDB runtime URL from SSM SecureString, and invokes only the approved
Bedrock models.

Read [the Phase 8 deployment and observability runbook](docs/phase-8-deployment.md)
before creating resources. It covers architecture, expected cost, local
validation, deployment, live acceptance, degraded dependency tests, log
auditing, rollback, and teardown.

## Phase 6 read APIs

The dashboard uses the existing incident and diagnosis endpoints plus these
read-only pipeline navigation endpoints:

- `GET /api/pipelines`
- `GET /api/pipelines/{pipeline_id}/runs`
- `GET /api/pipeline-runs/{run_id}`
