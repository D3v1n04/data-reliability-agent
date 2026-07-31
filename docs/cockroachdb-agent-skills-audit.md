# CockroachDB Agent Skills release audit

Phase 9 used the official CockroachDB Agent Skills Repo as an AI-assisted
development and governance tool. This is separate from the Data Reliability
Agent runtime; it does not grant the diagnosis model database or control-plane
access.

## Provenance

- Repository:
  [`cockroachlabs/cockroachdb-skills`](https://github.com/cockroachlabs/cockroachdb-skills)
- Audited source commit: `e14e86d23ce8ee2e7e40a34ce2944c2502b6eadd`
- Skills applied:
  - `cockroachdb-query-and-schema-design/cockroachdb-sql`
  - `cockroachdb-security-and-governance/hardening-user-privileges`
- Audit date: July 31, 2026

## What the agent did

The `cockroachdb-sql` skill guided a source-level review of the memory schema
and similarity query. It checked for explicit distributed primary keys,
CockroachDB-native types, vector dimensions, the distance operator, index
strategy, and production anti-patterns.

The `hardening-user-privileges` skill guided a least-privilege review of the
Alembic grant migrations and produced the read-only live verification checklist
below. No production grant was changed automatically.

## Source-level findings

| Check | Result | Evidence or action |
|---|---|---|
| Distributed primary keys | Pass | Tables use UUID primary keys with `gen_random_uuid()` |
| Memory types | Pass | Immutable JSONB snapshot plus explicit `VECTOR(256)` |
| Similarity metric | Pass | SQLAlchemy compiles cosine distance for normalized Titan embeddings |
| Vector-index acceleration | Fixed in Phase 9 | Added `ix_incident_memories_embedding_cosine` with `vector_cosine_ops` |
| Transactional co-location | Pass | Operational data, memory, and diagnoses share CockroachDB |
| Runtime admin access | Pass by migration review | `dra_app` receives table-level DML, not admin or DDL |
| Migration/runtime separation | Pass | `dra_admin` and `dra_app` have distinct responsibilities |
| PUBLIC data access | Live verification required | Confirm immediately before release |

## Required live verification

Run these read-only checks from an administrative CockroachDB SQL session
before the final release. Capture results without connection strings, account
emails, or unrelated user names.

```sql
SHOW INDEXES FROM incident_memories;
SHOW GRANTS FOR dra_app;
SHOW GRANTS FOR public;
SELECT count(*) AS memory_count FROM incident_memories;
SELECT count(*) AS diagnosis_count FROM incident_diagnoses;
```

Expected evidence:

- `ix_incident_memories_embedding_cosine` exists and is a vector index.
- `dra_app` is not an `admin` member and has only the documented application
  privileges.
- `public` has no application-table DML privileges.
- At least two historical memories exist before the recorded current diagnosis.

Because the release-audit environment had no production database connection,
the agent generated no `EXPLAIN` claim. The final operator must run the live
query-plan and index checks against the deployed cluster before tagging the
release.

## Safety outcome

The skill use narrowed a real submission gap without expanding model
authority: it added a database index and a read-only audit trail. It did not add
MCP, autonomous remediation, direct SQL generation by the diagnosis model, or
control-plane access.
