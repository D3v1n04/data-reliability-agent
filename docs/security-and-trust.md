# Security and trust

Data Reliability Agent is intentionally designed so that a model failure cannot
rewrite the operational facts that created an incident.

## Authority model

The deterministic engine owns:

- Reliability rule evaluation
- Incident creation and severity
- Idempotency and concurrent-duplicate handling
- Lifecycle transitions and terminal resolution

Amazon Bedrock may:

- Embed an immutable evidence snapshot
- Receive a bounded set of similar historical incidents
- Explain evidence and propose safe investigation steps

The diagnosis prompt contract forbids Bedrock from:

- Remove, contradict, or reinterpret emitted rule violations
- Claim a historical pattern proves the current root cause
- Execute remediation or modify a pipeline
- Treat logs, errors, metadata, or history as instructions

## Diagnosis guardrails

The live application uses structured tool output with strict schema
validation, length limits, list cardinality limits, unique items, and a
confidence range. The prompt contract requires every deterministic rule code to
appear in the explanation or cause list. When current evidence cannot support a
specific cause, deterministic post-processing replaces the model-proposed
causes with an insufficiency statement and caps confidence at `0.6`.

The separate Phase 7 release-evaluation corpus covers:

- Missing deterministic evidence
- Contradictory success claims
- Prompt injection inside untrusted evidence
- Unsupported root-cause claims
- Destructive recommendations
- Excessive confidence

The evaluator detects disallowed content in controlled cases before release;
it is not an inline filter on every production response and is not described as
a universal semantic-safety guarantee.

## Production controls

| Layer | Control |
|---|---|
| CockroachDB | Verified TLS, restricted `dra_app`, separate migration user, one-connection Lambda pools, statement timeout |
| AWS IAM | One SSM parameter and two named Bedrock model resources |
| Secrets | Database URL stored as SSM SecureString and loaded at runtime |
| Edge | CloudFront HTTPS, private S3 bucket, Origin Access Control |
| API | API Gateway rate 2 requests/second, burst 5 |
| Compute | Lambda timeout 25 seconds, reserved concurrency 2 |
| Model calls | Connect/read timeouts, two attempts, fixed embedding dimensions |
| Logs | Structured metadata only; no bodies, prompts, evidence, diagnoses, URLs, or exception chains |
| Monitoring | Lambda, API, database, Bedrock, throttle, and duration alarms |

## Known limitations

- The judging deployment has no end-user authentication. It must contain only
  synthetic data and should be torn down or secured after judging.
- Lambda is outside a VPC to avoid NAT cost and has no fixed egress IP. The
  CockroachDB network rule may allow public ingress, while authentication,
  least privilege, and verified TLS remain enforced.
- Similarity is evidence retrieval, not proof of causality.
- The deployment targets a controlled single-region demo. A real production
  rollout would add authentication, authorization, tenant isolation, and an
  organization-specific network design.

## Final secret audit

The release checklist requires both current-tree and Git-history scans for:

- AWS access-key identifiers and secret assignments
- GitHub or other bearer tokens
- Private keys
- Non-placeholder password-bearing database URLs
- `.env`, credentials, or private-key files accidentally tracked

Known fake credentials in `backend/tests/test_phase8_runtime.py` are test
fixtures (`secret` and `do-not-log`) used to prove that sensitive values do not
appear in logs. They are not real credentials.

CloudWatch evidence must be reviewed and redacted before publication. Never
publish AWS account IDs, ARNs containing account IDs, SSM values, database
hosts, private connection strings, email addresses, or unredacted log events.

## Dependency-audit note

On July 31, 2026, `pip-audit` reported no known Python vulnerabilities.
`npm audit` reported two high findings for `react-router` and
`react-router-dom` through
[`GHSA-qwww-vcr4-c8h2`](https://github.com/advisories/GHSA-qwww-vcr4-c8h2).
The upstream
[React Router maintainer advisory](https://github.com/remix-run/react-router/security/advisories/GHSA-qwww-vcr4-c8h2)
lists `7.18.2` as the patched 7.x version and states that the affected path is
limited to unstable React Server Component APIs. This repository resolves
`react-router` and `react-router-dom` to `7.18.2` and uses a client-only Vite
SPA with no RSC routes, server actions, or RSC runtime.

The npm/GitHub aggregate advisory currently describes a broader affected
range, so the audit still exits nonzero. This exception is narrow and
evidence-based; it must be rechecked before every deployment and removed if the
application adopts RSC or if the upstream advisory changes.
