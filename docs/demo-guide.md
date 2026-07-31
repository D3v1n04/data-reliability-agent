# Demo, screenshot, and video guide

This guide creates a repeatable two-history/one-current incident narrative
using synthetic data only. It is designed around the official requirement to
show both a functioning application and the CockroachDB memory layer in a video
shorter than three minutes.

## Prepare the recording dataset

Run the final database migration and production deployment first. Then seed a
new scenario label:

```bash
python scripts/seed_demo.py \
  https://YOUR_CLOUDFRONT_DOMAIN \
  --label final-recording-v1
```

The seeder:

1. Creates or reuses one clearly labeled synthetic customer-orders pipeline.
2. Ingests and diagnoses two historical failed runs.
3. Advances those historical incidents to `resolved`.
4. Ingests and diagnoses one current failed run.
5. Fails unless the current diagnosis contains retrieved incident memory.
6. Leaves the current incident `open` and prints its direct dashboard URL.

The script is idempotent while the current incident remains open. Use a new
label if that incident was advanced during a rehearsal.

## Demo storyline

The story is not “an AI watches pipelines.” The stronger and more accurate
story is:

> A data team receives a failed-run incident. Deterministic rules preserve what
> actually happened. CockroachDB remembers the current evidence and related
> historical investigations. Bedrock turns that memory into bounded guidance,
> while application guardrails prevent the model from overriding facts or
> taking action.

## Target video: 2 minutes 38 seconds

Do one clean recording at 1080p or higher. Use browser zoom near 100%, a large
cursor, no notifications, no background music, and no tabs or bookmarks that
expose personal information.

| Time | Screen action | Narration |
|---:|---|---|
| 0:00–0:12 | Dashboard overview | “Pipeline incidents cost teams twice: first in downtime, then in repeated investigation. Data Reliability Agent detects failures, remembers prior incidents, and helps responders investigate without giving AI control of operational facts.” |
| 0:12–0:30 | Architecture diagram | “The application runs on AWS Lambda behind API Gateway and CloudFront. CockroachDB is both the transactional system of record and the vector memory layer. Bedrock supplies embeddings and structured diagnoses.” |
| 0:30–0:55 | Open the seeded pipeline and current failed run | “This synthetic customer-orders run failed deterministic checks for run status, start delay, low row count, and quality failures. Those rules—not the model—create one idempotent incident and set its severity.” |
| 0:55–1:30 | Open the incident’s deterministic-evidence panel | “The current run is authoritative. Every observed value and threshold is preserved as structured evidence. Even if Bedrock is unavailable, detection and incident creation still work.” |
| 1:30–2:05 | Scroll through diagnosis, confidence, and similar incidents | “The immutable snapshot is embedded with Titan and stored in CockroachDB as a 256-dimensional vector. A cosine vector index retrieves related memories. Nova Lite uses them only as context; history cannot override today’s facts or prove causality.” |
| 2:05–2:26 | Show trust-boundary/guardrail panel and lifecycle control | “The live output is schema-validated, unsupported causes are replaced with an insufficiency statement capped at sixty percent confidence, and a nine-scenario release corpus detects injection, contradiction, and destructive advice. Only the operator advances the incident.” |
| 2:26–2:38 | Return to dashboard or architecture | “The result is a production-deployed, observable incident investigator with durable agentic memory—and deliberately no autonomous remediation.” |

Leave at least ten seconds of margin below the three-minute limit. Judges are
not required to watch beyond three minutes.

## CockroachDB memory evidence

The video must visibly prove memory, not merely mention it. Include all three:

- The incident page’s similar-incidents section with at least one similarity
  result.
- The architecture diagram’s CockroachDB memory path.
- A brief terminal frame showing the sanitized seeder result:
  `similar_memories_retrieved` greater than zero.

Do not show a database connection string, CockroachDB host, user inventory, or
unredacted SQL client history.

## Screenshot set

Capture PNG files at a consistent 16:9 browser size:

1. `01-dashboard.png` — overall health, counts, and recent incidents.
2. `02-deterministic-evidence.png` — current incident with rule codes, observed
   values, and thresholds.
3. `03-agentic-memory.png` — diagnosis plus similar incident cards and
   similarity score.
4. `04-trust-boundary.png` — confidence, safe recommendations, and lifecycle
   control.
5. `05-architecture.png` — export or render `docs/assets/architecture.svg`.

Before publishing, inspect every screenshot for account names, AWS account IDs,
emails, database hosts, record contents not labeled synthetic, bookmarks,
notifications, or unrelated tabs.

Store approved public screenshots under `docs/evidence/`. Keep raw AWS console
captures outside the repository until they are redacted.

## Recording checklist

- Use the CloudFront URL, not localhost.
- Confirm `/health` and `/ready` immediately before recording.
- Rehearse the exact seeded incident path.
- Keep browser developer tools closed unless showing a sanitized API response.
- Do not include third-party music or unrelated trademarks.
- Upload publicly to YouTube or Vimeo.
- Confirm the public video works in a private/incognito browser.
- Add the final URL to Devpost before the deadline.
