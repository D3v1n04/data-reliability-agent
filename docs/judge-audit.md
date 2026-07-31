# Judge-perspective repository audit

Audit date: July 31, 2026
Baseline: `main` at `72a2c8e`

## Executive assessment

The implemented product is substantially stronger than the baseline README
communicated. A judge inspecting only the old repository landing page could see
that the application used CockroachDB and Bedrock, but would not quickly find
the architecture, agentic-memory proof, judging-criteria mapping, reproducible
demo, trust boundary, release evaluation, or public evidence.

The audit also found two pass/fail submission gaps:

1. The public repository had no root open-source license.
2. The application used `VECTOR(256)` and cosine distance, but no CockroachDB
   vector index, and no second named CockroachDB hackathon tool was evidenced.

Phase 9 addresses the source-level portions by adding an MIT license, a cosine
vector-index migration, and an auditable use of the official CockroachDB Agent
Skills Repo. Live database verification remains a final release gate.

## What judges should understand in the first minute

- The problem: data teams repeat incident investigations.
- The novelty: CockroachDB remembers structured facts and semantic history in
  one consistent system.
- The trust model: current deterministic facts outrank memory and model output.
- The proof: the live incident page shows current violations, a persisted
  diagnosis, and related historical incidents.
- The production story: the application is deployed on AWS with least
  privilege, encrypted configuration, observability, failure handling, and
  teardown.

## Criterion readiness

| Criterion | Current strength | Remaining evidence before release |
|---|---|---|
| Agentic Memory Design | Strong schema and workflow: immutable JSONB snapshot, `VECTOR(256)`, historical retrieval, persisted diagnosis | Apply and show the live cosine vector index; show related memory in video |
| Technological Implementation | Strong tests, dimensions, normalized embeddings, idempotency, structured Bedrock output, Agent Skills audit | Capture live index/query-plan check; do not claim MCP or `ccloud` |
| Real-World Impact | Clear data-platform incident use case and operator workflow | State the repeated-investigation cost clearly in video opening |
| Product Readiness | Strong AWS SAM, IAM, SSM, TLS, throttling, timeouts, alarms, degraded behavior, rollback, teardown | Rerun final live acceptance and log audit; disclose unauthenticated synthetic-demo limitation |
| Creativity & Originality | Distinct authority hierarchy between facts, memory, and AI guidance | Make the trust boundary visible rather than burying it in setup docs |

## Repository findings

| Finding | Baseline status | Phase 9 response |
|---|---|---|
| Public open-source license | Blocking: absent | MIT license added |
| Judge-facing README | Too short for the implemented system | Rewritten around problem, proof, memory, trust, setup, and evidence |
| Architecture diagram | Absent | Render-verified SVG plus detailed memory-flow document |
| Named CockroachDB tools | Only vector storage/query visible; no index or second tool | Cosine index migration plus official Agent Skills audit |
| AWS service explanation | Distributed across Phase 8 runbook | Consolidated in README and submission copy |
| Reproducible dataset | Acceptance test created one random incident | Idempotent history-first synthetic demo seeder added |
| Video and screenshots | Absent | Timed 2:38 script, recording plan, evidence filenames, and redaction checklist |
| Judging map | Absent | Equal-weight criteria mapped to concrete evidence |
| Security narrative | Detailed but deployment-focused | Trust, guardrails, known limits, dependency audit, and secret review consolidated |
| Final release process | Informal | Blocking checklist for database, demo, evidence, validation, and tag |

## Risks to avoid

- Do not submit before the live vector index exists.
- Do not describe plain vector storage as Distributed Vector Indexing.
- Do not claim MCP or `ccloud` merely because they are available.
- Do not describe the phrase-based release evaluator as an inline universal
  safety filter.
- Do not imply historical similarity proves a root cause.
- Do not show real credentials, AWS account identifiers, database hosts, or
  non-synthetic evidence.
- Do not tear down the deployment before the judging period ends.
- Do not add autonomous remediation merely to make the agent appear more
  powerful; the constrained authority model is a project strength.
