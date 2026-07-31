# Data Reliability Agent

**A production-deployed incident investigator that remembers prior pipeline
failures without letting AI rewrite operational facts.**

Data Reliability Agent detects unhealthy data-pipeline runs with deterministic
rules, stores transactional and vector memory in CockroachDB, and uses Amazon
Bedrock to generate evidence-grounded investigation guidance.

> Deterministic rules decide what happened. AI helps explain why it may have
> happened and what to investigate next.

![Data Reliability Agent production architecture](docs/assets/architecture.svg)

## Why this exists

Pipeline incidents are expensive twice: first when data stops or becomes
untrustworthy, and again when responders repeat investigations that the
organization has already performed. A conventional alert can say that a run
failed. Data Reliability Agent also preserves the run evidence, retrieves
semantically related incidents, and turns that history into safe next steps.

The design solves a central production-AI problem: memory should improve an
agent without becoming a new source of truth. Current deterministic evidence
always wins over model output or historical similarity.

## What the demo proves

1. A synthetic completed run violates reliability thresholds.
2. Seven deterministic rule types can create one idempotent incident with the
   highest applicable severity.
3. Titan Text Embeddings V2 converts an immutable incident snapshot into a
   normalized 256-dimensional embedding.
4. CockroachDB stores the operational records, JSONB evidence, embedding, and
   persisted diagnosis in one consistent system.
5. A cosine vector index retrieves related incident memories without a
   separate vector database or synchronization pipeline.
6. Nova Lite receives current facts plus bounded historical context and returns
   a structured diagnosis.
7. A nine-scenario release evaluator detects contradictions, destructive
   advice, prompt injection, unsupported causes, and excessive confidence.
8. The operator—not the model—moves the incident through
   `open → investigating → resolved`.

Use the [reproducible demo guide](docs/demo-guide.md) to create this exact
history-first scenario.

## Trust boundary

| Deterministic system | AI assistance |
|---|---|
| Owns rule results, severity, incident creation, and lifecycle | Explains evidence and proposes investigation steps |
| Commits current run evidence to CockroachDB | Retrieves similar historical memories |
| Remains available when Bedrock fails | Cannot remove violations, change pipelines, or remediate systems |
| Enforces idempotency and terminal resolution | Must distinguish observed facts from hypotheses |

When evidence cannot establish a specific cause, application code replaces
model-proposed causes with an insufficiency statement and caps confidence at
`0.6`. The prompt contract treats logs, errors, metadata, and historical
incidents as untrusted data—not instructions. Phase 7 separately evaluates
Bedrock output against controlled adversarial cases before release.

Autonomous remediation and automatic pipeline changes are intentionally out of
scope. MCP is not part of the runtime application.

## Architecture

The production deployment uses one public CloudFront origin:

- React and TypeScript assets are stored in a private, versioned S3 bucket.
- CloudFront serves the SPA and proxies `/api/*`, `/health`, and `/ready`.
- API Gateway invokes a containerized FastAPI backend on AWS Lambda.
- Lambda reads one encrypted CockroachDB runtime URL from SSM Parameter Store.
- CockroachDB stores pipelines, runs, incidents, memories, and diagnoses.
- Amazon Bedrock provides Titan embeddings and Nova Lite diagnoses.
- CloudWatch receives redacted structured logs, metrics, and alarms.

Read the full [architecture and agentic-memory walkthrough](docs/architecture.md)
and [AWS deployment runbook](docs/phase-8-deployment.md).

## Hackathon technology

### CockroachDB

- **Distributed Vector Indexing:** `VECTOR(256)` memories are queried with
  cosine distance through a `vector_cosine_ops` index.
- **Agent Skills Repo:** the official `cockroachdb-sql` and
  `hardening-user-privileges` skills were applied to the Phase 9 vector-index
  migration and least-privilege release audit. The exact source revision and
  results are recorded in the
  [CockroachDB Agent Skills audit](docs/cockroachdb-agent-skills-audit.md).
- **Distributed SQL and JSONB:** operational evidence, memory, and diagnoses
  remain transactionally consistent in the same database.

The managed CockroachDB MCP Server and `ccloud` CLI are not claimed as
implemented tools.

### AWS

- **Amazon Bedrock:** Nova Lite structured diagnoses and Titan Text Embeddings
  V2 memory embeddings.
- **AWS Lambda:** serverless FastAPI runtime using a Python 3.12 container.
- **Amazon API Gateway:** bounded HTTP API ingress.
- **Amazon S3 + CloudFront:** private frontend storage and global HTTPS
  delivery.
- **AWS Systems Manager Parameter Store:** encrypted runtime database
  configuration.
- **Amazon CloudWatch:** structured logs, dependency metrics, and alarms.
- **AWS SAM / CloudFormation:** reproducible infrastructure as code.

## Reliability engine

The engine evaluates completed runs for:

- `RUN_FAILED`
- `RUN_CANCELLED`
- `START_DELAY_EXCEEDED`
- `DURATION_EXCEEDED`
- `ROW_COUNT_BELOW_MINIMUM`
- `ROW_COUNT_MISSING`
- `QUALITY_CHECKS_FAILED`

Multiple violations are combined into one incident. Duplicate run submissions
return the existing run and incident, including under concurrent requests.
Resolved incidents are terminal audit records.

## Run locally

### Prerequisites

- Python 3.12
- Node.js 24
- A CockroachDB database
- AWS credentials authorized for the two configured Bedrock models

Create the local configuration:

```bash
cp .env.example .env
```

Fill in the restricted runtime and migration URLs. Both URLs must use verified
TLS; never commit `.env`.

The Phase 9 vector-index migration requires CockroachDB vector indexes to be
enabled once by a cluster administrator:

```sql
SET CLUSTER SETTING feature.vector_index.enabled = true;
```

Then install, migrate, and start the backend:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
alembic upgrade head
uvicorn backend.app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`.

## Create safe demo data

The demo seeder sends only clearly labeled synthetic evidence through the
public application API. It creates two resolved historical memories before one
open current incident, then confirms that the current diagnosis retrieved
memory.

```bash
python scripts/seed_demo.py \
  https://YOUR_CLOUDFRONT_DOMAIN \
  --label recording-v1
```

Use a new label after advancing the current incident. The script prints the
direct incident URL and no credentials.

## Validate

```bash
source .venv/bin/activate
python -m pytest -q
python -m compileall -q backend/app backend/migrations scripts

cd frontend
npm ci
npm run lint
npm run build
npm test
npx playwright install chromium
npm run test:e2e
cd ..

bash -n scripts/*.sh
sam validate --lint --template-file infra/template.yaml
git diff --check
```

The end-to-end workflow is:

`pipeline failure → deterministic evidence → incident memory → diagnosis →
similar history → investigating → resolved`

Phase 7 includes a nine-scenario adversarial diagnosis corpus covering missing
evidence, contradictory claims, prompt injection, destructive recommendations,
unsupported causes, and excessive confidence.

## Security and production posture

- Separate `dra_admin` migration and `dra_app` runtime database users.
- Restricted runtime grants; no application admin role.
- Verified CockroachDB TLS and bounded Lambda connection pooling.
- Lambda IAM permission limited to one SSM parameter and two Bedrock models.
- Request and dependency timeouts, API throttling, reserved concurrency, and
  cost-aware limits.
- Logs exclude bodies, prompts, diagnoses, database URLs, raw record IDs, and
  exception chains.
- Health, readiness, dependency-failure metrics, alarms, rollback, and teardown
  procedures.

The public demo has no end-user authentication and contains synthetic data
only. It is a controlled judging environment, not a public multi-tenant
service. See [security and trust](docs/security-and-trust.md).

## Submission resources

- [Architecture and memory workflow](docs/architecture.md)
- [Judge-perspective repository audit](docs/judge-audit.md)
- [Demo, screenshot, and video plan](docs/demo-guide.md)
- [Devpost copy and judging-criteria map](docs/submission.md)
- [Security and trust](docs/security-and-trust.md)
- [Final release checklist](docs/phase-9-release-checklist.md)
- [AWS deployment, observability, costs, and teardown](docs/phase-8-deployment.md)

## License

Released under the [MIT License](LICENSE).
