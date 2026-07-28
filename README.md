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
- Backend, frontend component, and Playwright workflow tests

MCP is not part of the completed implementation and remains a later explicit
milestone. Autonomous remediation, AWS deployment, and production
infrastructure are also outside the current scope.

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

## Phase 6 read APIs

The dashboard uses the existing incident and diagnosis endpoints plus these
read-only pipeline navigation endpoints:

- `GET /api/pipelines`
- `GET /api/pipelines/{pipeline_id}/runs`
- `GET /api/pipeline-runs/{run_id}`
