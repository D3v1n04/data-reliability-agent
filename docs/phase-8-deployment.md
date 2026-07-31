# Phase 8: AWS deployment and observability

Phase 8 deploys Data Reliability Agent as a controlled, production-style demo.
The deterministic reliability engine and Phase 7 cause-grounding policy remain
the trust boundary. The deployment does not add autonomous remediation,
pipeline modification, MCP, or broader model authority.

## Architecture

The SAM stack creates:

- A private, versioned S3 bucket for the React production artifact.
- A CloudFront distribution that serves the dashboard and proxies `/api/*`,
  `/health`, and `/ready` to the backend.
- An API Gateway HTTP API with a 2 request/second rate and burst of 5.
- A 1 GB Lambda container with a 25-second timeout and reserved concurrency of
  2.
- A 14-day CloudWatch log group, native service alarms, and custom Bedrock and
  database failure alarms.
- An optional SNS email subscription when `ALARM_NOTIFICATION_EMAIL` is set.

Lambda stays outside a VPC to avoid the fixed cost of a NAT Gateway. It connects
to CockroachDB's public endpoint using verified TLS, the restricted `dra_app`
user, a pool of one connection per Lambda environment, and bounded connection
and statement timeouts. This design does not provide a fixed Lambda egress IP;
the CockroachDB network rule may therefore need to allow public ingress. That
limitation is acceptable only for this controlled demo and must remain
documented.

CloudFront provides the application's one public origin. The production
frontend uses relative API paths, so browser CORS is not required. Direct API
Gateway calls remain possible for operational testing but do not receive
cross-origin browser permission.

## Runtime security contract

- Lambda receives temporary credentials from its execution role. `AWS_PROFILE`
  is never set in Lambda and is used only for local development.
- The execution role may read exactly one named SSM parameter and invoke only
  the configured Nova Lite and Titan Embeddings V2 foundation models.
- The database URL is stored in SSM as a SecureString and fetched once when a
  Lambda environment first needs a database connection.
- The URL must use PostgreSQL/CockroachDB and contain
  `sslmode=verify-full`; startup readiness fails otherwise.
- The `dra_app` runtime role is used by the application. Alembic migrations
  continue to use `dra_admin` outside Lambda.
- Request logs contain only a generated request ID, method, route template,
  status, duration, event name, and bounded failure category. Request bodies,
  query strings, raw paths containing record IDs, database URLs, prompts,
  incident evidence, diagnoses, and exception chains are excluded.
- CloudWatch Embedded Metric Format records contain only environment and a
  failure count.

This deployment has no user authentication. Treat it as a controlled demo, not
a public multi-tenant application. Add authentication and authorization before
placing real operational evidence behind it.

## Expected monthly cost

At approximately 10,000 API requests and 500 diagnoses per month:

| Service | Approximate monthly cost |
|---|---:|
| Lambda | $0–$0.15 |
| API Gateway HTTP API | About $0.01 |
| S3 and CloudFront | $0–$0.50 |
| SSM standard SecureString | $0 with the default AWS managed key |
| SAM-managed ECR storage | About $0.05 |
| CloudWatch metrics and alarms | About $1–$2 |
| Nova Lite and Titan embeddings | About $0.20–$0.40 |
| Existing CockroachDB Basic cluster | Existing allocation |

The expected Phase 8 AWS total is approximately $1–$4 per month at demo
traffic. CloudWatch alarms are the most likely first non-zero recurring cost.
Always check the current AWS pricing pages before deployment.

## Prerequisites

Install and verify:

```bash
aws --version
sam --version
docker --version
node --version
python --version
```

Authenticate the local deployment session:

```bash
aws login --profile data-reliability-agent
aws sts get-caller-identity \
  --profile data-reliability-agent \
  --region us-east-1
```

Phase 9 adds a CockroachDB cosine vector index. Before applying that migration,
enable vector indexes once from a cluster-administrator SQL session:

```sql
SET CLUSTER SETTING feature.vector_index.enabled = true;
```

Then run database migrations with `dra_admin` before deployment:

```bash
source .venv/bin/activate
alembic upgrade head
alembic current
```

Create or rotate the production SSM SecureString. Do not put the URL in a
CloudFormation parameter, repository file, shell history, or deployment log.
The AWS console is the simplest way to enter the value without placing it on a
command line:

- Region: `us-east-1`
- Name: `/data-reliability-agent/production/database-url`
- Type: `SecureString`
- KMS key: the default `aws/ssm` key
- Value: the restricted `dra_app` URL ending in `sslmode=verify-full`

Confirm only the parameter metadata:

```bash
aws ssm describe-parameters \
  --parameter-filters \
    Key=Name,Option=Equals,Values=/data-reliability-agent/production/database-url \
  --profile data-reliability-agent \
  --region us-east-1
```

Do not use `get-parameter --with-decryption` for routine checks.

Lambda requires the account to retain at least 100 units of unreserved
concurrency. Check the regional account values:

```bash
aws lambda get-account-settings \
  --profile data-reliability-agent \
  --region us-east-1
```

The default deployment reserves 2 units. If the account limit cannot support
that while retaining 100 unreserved units, set
`BACKEND_RESERVED_CONCURRENCY=0`. API Gateway still limits traffic to a burst of
5, and each Lambda environment still has a one-connection database pool.

## Local verification

```bash
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m pytest -q
python -m compileall -q backend/app backend/migrations scripts

cd frontend
npm ci
npm run lint
npm run build
npm test
cd ..

bash -n scripts/*.sh
git diff --check
```

Validate the SAM template before deployment:

```bash
sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml
```

`sam build` needs Docker because the Lambda artifact is a container image.

### React Router audit note

The frontend is pinned to `react-router-dom` 7.18.2, which resolves
`react-router` 7.18.2. The React Router maintainer advisory for
`GHSA-qwww-vcr4-c8h2` identifies 7.18.2 as the patched 7.x release and states
that the vulnerable path exists only in unstable React Server Component APIs.
This application is a declarative, client-only Vite SPA and has no RSC server
or server actions.

As of July 31, 2026, the npm audit feed still reports the advisory against
7.18.2. The upstream React Router maintainer advisory identifies 7.18.2 as the
patched 7.x release and limits the affected path to unstable RSC APIs; this
client-only Vite SPA uses neither RSC routes nor server actions. Treat the
nonzero audit as a narrowly documented upstream metadata discrepancy, not as
permission to ignore future advisories. Recheck the maintainer advisory and
npm audit before every deployment, and remove this exception when the feeds
converge or if the frontend architecture changes.

## Deploy

The deploy script verifies that the SSM parameter exists without decrypting it,
builds the backend and frontend, deploys the SAM stack, uploads `frontend/dist`
to the private bucket, and invalidates CloudFront:

```bash
export AWS_PROFILE=data-reliability-agent
export AWS_REGION=us-east-1
export STACK_NAME=data-reliability-agent-production
export DATABASE_URL_SSM_PARAMETER=/data-reliability-agent/production/database-url
export BACKEND_RESERVED_CONCURRENCY=2

# Optional; AWS sends a confirmation email before notifications become active.
export ALARM_NOTIFICATION_EMAIL=you@example.com

./scripts/deploy.sh
```

CloudFront creation can take several minutes. The script prints the application
URL after the frontend upload and invalidation request.

## Live acceptance test

The acceptance test creates one clearly named synthetic pipeline, failed run,
incident, diagnosis, and lifecycle sequence. It intentionally leaves those
records in CockroachDB as deployment evidence.

```bash
python scripts/acceptance_test.py https://CLOUDFRONT_DOMAIN
```

It verifies:

1. Process liveness returns `200`.
2. Database readiness returns `200`.
3. A failed run produces deterministic violations and an incident.
4. Bedrock produces a persisted diagnosis.
5. Phase 7's trust guardrail keeps ungrounded-cause confidence at or below
   `0.6`.
6. The incident moves from open to investigating to resolved.

Also open the CloudFront URL in a browser and repeat the dashboard workflow.

## Degraded dependency tests

Run degraded tests in temporary stacks, never by breaking the production
stack.

### Database failure

Create a temporary SecureString whose value is syntactically valid but points
to an unreachable test host. Deploy a separate stack:

```bash
export STACK_NAME=data-reliability-agent-database-failure-test
export DATABASE_URL_SSM_PARAMETER=/data-reliability-agent/test/unreachable-database-url
./scripts/deploy.sh
```

Expected behavior:

- `/health` returns `200` because the process is alive.
- `/ready` returns `503` with only `{"detail":"Database is unavailable"}`.
- A `DatabaseFailures` metric is emitted.
- The database and API 5xx alarms enter `ALARM` after evaluation.
- No connection URL or driver exception appears in logs.

### Bedrock failure

Use the valid production database parameter but an invalid model ID in another
temporary stack:

```bash
export STACK_NAME=data-reliability-agent-bedrock-failure-test
export DATABASE_URL_SSM_PARAMETER=/data-reliability-agent/production/database-url
export BEDROCK_TEXT_MODEL_ID=invalid.phase-8-test-model
./scripts/deploy.sh

python scripts/acceptance_test.py \
  https://FAILURE_TEST_CLOUDFRONT_DOMAIN \
  --expect-diagnosis-failure
```

Expected behavior:

- Deterministic run ingestion and incident creation still succeed.
- Diagnosis returns `503` with only
  `{"detail":"Unable to diagnose incident"}`.
- No incomplete diagnosis is persisted.
- A `BedrockFailures` metric is emitted and its alarm evaluates.
- Prompts, model response content, incident evidence, and exception details do
  not appear in logs.

Delete each failure-test stack immediately after recording the results.

## Sensitive-log audit

After normal acceptance and each degraded test:

```bash
python scripts/audit_cloudwatch_logs.py \
  --log-group /aws/lambda/data-reliability-agent-production-backend \
  --region us-east-1 \
  --profile data-reliability-agent \
  --minutes 60
```

The audit reads log events but prints no event contents. It fails if it finds a
database URL, known diagnosis-evidence field, or raw system-prompt marker.
Review the CloudWatch log stream manually as a second check; approved events
should be request summaries, bounded failure categories, Lambda platform
events, and metric records only.

## Rollback

CloudFormation automatically rolls back a failed stack update. For an
application rollback:

1. Record the current stack outputs and failing Git commit.
2. Check out the last known-good Git commit.
3. Re-run `./scripts/deploy.sh` with the same stack and parameter names.
4. Run the live acceptance test again.
5. Confirm the CloudWatch alarms return to `OK`.

Frontend objects are versioned in S3, but the preferred rollback is rebuilding
the known-good Git commit so backend, frontend, and infrastructure remain one
auditable release. Never roll back CockroachDB with `alembic downgrade` until
the downgrade has been reviewed for data loss. Prefer a forward migration.

## Teardown

The teardown script empties the frontend bucket and asks SAM to remove the
stack and its managed image repository. It preserves the SSM database parameter
to prevent accidental credential deletion:

```bash
export AWS_PROFILE=data-reliability-agent
export AWS_REGION=us-east-1
export STACK_NAME=data-reliability-agent-production
export CONFIRM_TEARDOWN=yes
./scripts/teardown.sh
```

After verifying the application is gone, explicitly remove the preserved SSM
parameter only if the database credential has been rotated or the entire
project is being retired. CockroachDB data and the cluster are not managed by
this stack.

## MCP decision

MCP is omitted from Phase 8. It may be proposed as a separately reviewed Phase
8.5 only after the deployed application is stable. Until then, documentation
must continue to state that MCP is not implemented.
