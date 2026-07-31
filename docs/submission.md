# Hackathon submission package

Requirements were verified on July 31, 2026 against the official
[hackathon overview](https://cockroachdb-ai.devpost.com/) and
[official rules](https://cockroachdb-ai.devpost.com/rules).
Recheck both pages immediately before submission because the rules may change.

## Official deadline and pass/fail requirements

- Deadline: **August 18, 2026 at 5:00 PM EDT**.
- The project must be an agentic application with CockroachDB as persistent
  memory and must be deployed on AWS.
- At least **two named CockroachDB tools** must be meaningfully used.
- At least **one AWS service** must be meaningfully used.
- The repository must be public, open source, licensed, complete, and
  reproducible.
- A free, unrestricted functional demo URL is required through the judging
  period.
- The English demo video must be public on YouTube or Vimeo, shorter than three
  minutes, show the application functioning, and show CockroachDB memory at
  work.
- The submission must identify the CockroachDB tools and AWS services used and
  explain what the agent did with them.

Judges may score only the written description, images, and video, so every
critical claim must be visible without requiring them to install the project.

## Submission form copy

### Project name

Data Reliability Agent

### One-line pitch

A production-deployed incident investigator that uses CockroachDB vector memory
and Amazon Bedrock to learn from prior pipeline failures without letting AI
override deterministic operational facts.

### Inspiration

Data teams often diagnose the same class of pipeline failure repeatedly.
Traditional alerts preserve that something failed but not the reusable
investigation context. At the same time, giving an LLM authority over incident
facts or remediation creates a new reliability risk. Data Reliability Agent
was built to make memory useful without making it authoritative.

### What it does

The application ingests completed pipeline runs and evaluates deterministic
reliability rules for failures, cancellations, start delay, duration, row
counts, and data-quality checks. Multiple violations create exactly one
idempotent incident with the highest applicable severity.

When an operator requests a diagnosis, the application builds an immutable
evidence snapshot, uses Amazon Titan Text Embeddings V2 to create a normalized
256-dimensional embedding, and persists it in CockroachDB. CockroachDB’s cosine
vector index retrieves related historical incident memories. Amazon Nova Lite
then produces a structured explanation, likely-cause hypotheses, safe
investigation recommendations, and confidence.

Current deterministic evidence always wins. Historical similarity cannot prove
causality. The prompt contract treats untrusted text as data; a separate
adversarial release corpus checks this behavior. Model-proposed causes are
replaced with an insufficiency statement, and confidence is capped when the
evidence is incomplete. The model has no tools or API authority to modify
pipelines, transition incidents, or perform remediation.

### How it was built

The backend is FastAPI and SQLAlchemy on Python 3.12. CockroachDB stores
pipelines, immutable runs, incidents, JSONB evidence, `VECTOR(256)` memories,
and persisted diagnoses. The React/TypeScript dashboard exposes pipeline, run,
incident, evidence, diagnosis, memory, and lifecycle views.

AWS SAM deploys the backend as a Lambda container behind API Gateway and the
frontend to a private S3 bucket behind CloudFront. Lambda retrieves one
encrypted runtime database URL from SSM Parameter Store and may invoke only the
two configured Bedrock models. CloudWatch provides structured redacted logs,
dependency metrics, and alarms.

The release includes deterministic unit/integration tests, a browser workflow
test, a nine-scenario adversarial diagnosis corpus, live acceptance testing,
degraded dependency tests, log-secret auditing, rollback, and teardown.

### CockroachDB tools used

1. **Distributed Vector Indexing** — The diagnosis workflow stores normalized
   Titan embeddings in `incident_memories.embedding` as `VECTOR(256)`. A
   `vector_cosine_ops` index accelerates cosine nearest-neighbor retrieval.
   Retrieved memories are supplemental context for the diagnosis; they remain
   transactionally consistent with incident records in the same database.
2. **CockroachDB Agent Skills Repo** — The development agent applied the
   official `cockroachdb-sql` and `hardening-user-privileges` skills to review
   the memory schema, add the correct cosine vector index, and produce the final
   least-privilege release audit. The source revision, findings, and required
   live checks are committed in
   `docs/cockroachdb-agent-skills-audit.md`.

The project does not claim the managed MCP Server or `ccloud` CLI.

### AWS services used

- Amazon Bedrock — Nova Lite diagnosis and Titan Text Embeddings V2.
- AWS Lambda — containerized serverless FastAPI execution.
- Amazon API Gateway — bounded HTTP ingress.
- Amazon S3 — private versioned frontend artifact storage.
- Amazon CloudFront — HTTPS frontend delivery and API routing.
- AWS Systems Manager Parameter Store — one encrypted database URL.
- Amazon CloudWatch — redacted logs, custom metrics, and alarms.
- AWS SAM / CloudFormation — reproducible infrastructure.

### Challenges

The hardest problem was not generating an answer; it was defining which parts
of an answer the system was allowed to trust. The implementation keeps
deterministic evidence immutable, treats logs and historical incidents as
untrusted data, validates structured model output, and post-processes
unsupported cause claims. Production deployment added a second challenge:
bounded database connections, least-privilege IAM, secret loading, sanitized
failure behavior, observability, and low-cost serverless limits all had to work
together.

### Accomplishments

- One consistent CockroachDB system for transactional evidence and semantic
  memory.
- Idempotent incident creation with concurrency handling.
- Evidence-grounded diagnoses with explicit authority boundaries.
- Adversarial evaluation for contradiction, injection, destructive advice,
  cause grounding, and confidence.
- A real AWS deployment with infrastructure as code, observability, rollback,
  and teardown.
- A judge-friendly dashboard and reproducible synthetic demo.

### What was learned

Agentic memory is not simply saving chat history. Useful production memory needs
stable evidence, retrieval semantics, transactional consistency, access
control, observability, and rules about when memory may influence a decision.
The most important design choice was to keep detection deterministic and make
AI assistance bounded and auditable.

### What is next

The next production steps would be authentication, tenant authorization,
organization-specific network controls, and larger-scale retrieval evaluation.
MCP could be evaluated later as a separately permissioned, read-only
operational interface. Autonomous remediation is not on the roadmap without a
new threat model, approval workflow, and safety review.

## Judging-criteria map

The five official criteria are equally weighted. Tie-breaking begins with
Agentic Memory Design.

| Criterion | Judge-facing evidence |
|---|---|
| Agentic Memory Design | CockroachDB co-locates immutable JSONB snapshots, `VECTOR(256)` embeddings, diagnoses, runs, and incident state; cosine-indexed retrieval changes the context available to the agent; the video shows related memory in the current diagnosis |
| Technological Implementation | Explicit vector index/opclass, dimension validation, normalized embeddings, transactional idempotency, Bedrock structured output, official Agent Skills audit, FastAPI/React tests, and no false MCP claim |
| Real-World Impact | Reduces repeated pipeline-investigation work while preserving a reliable audit trail; directly fits data-platform and operations workflows |
| Product Readiness | Public AWS deployment, SAM infrastructure, private S3/OAC, least-privilege IAM and database roles, SSM secrets, TLS, timeouts, throttling, bounded pools, redacted logs, metrics, alarms, degraded tests, rollback, and teardown |
| Creativity & Originality | Treats memory as evidence with an explicit authority hierarchy: current deterministic facts outrank historical similarity and model output |

## Final Devpost-only fields

Do not tag the release until all are complete:

- Public repository URL:
  `https://github.com/D3v1n04/data-reliability-agent`
- Functional CloudFront demo URL: **add after final deployment**
- Public YouTube or Vimeo URL: **add after recording**
- Approved screenshots: **add after redaction review**
- Testing instructions: open the seeded current incident URL, inspect
  deterministic evidence, diagnosis, similar incidents, and lifecycle control;
  no login is required and all data is synthetic.
