# Phase 9 final release checklist

Do not create the final tag while any blocking item remains open. Preserve the
live demo and public evidence until the judging period ends.

## Eligibility and metadata

- [x] Official requirements rechecked on July 31, 2026.
- [x] Public repository confirmed.
- [x] MIT `LICENSE` added at repository root.
- [ ] GitHub recognizes and displays the MIT license in the repository header.
- [ ] Repository About section has a concise description, live demo URL, and
      relevant topics.
- [ ] Devpost registration and entrant/team details are complete.

## Required CockroachDB tools

- [x] Distributed vector-index migration is committed.
- [ ] Vector indexes are enabled on the live CockroachDB cluster.
- [ ] `alembic upgrade head` applies
      `ix_incident_memories_embedding_cosine` successfully.
- [ ] Live `SHOW INDEXES FROM incident_memories` confirms the cosine vector
      index.
- [ ] A live query-plan/index check is captured without exposing a connection
      string.
- [x] Official CockroachDB Agent Skills source commit and applied skills are
      documented.
- [ ] Read-only `dra_app` and `public` grant checks are captured and reviewed.
- [x] MCP and `ccloud` are not falsely claimed.

## Demo and evidence

- [ ] A fresh synthetic label is seeded with two historical memories and one
      open current incident.
- [ ] The seeder reports `similar_memories_retrieved > 0`.
- [ ] Five approved screenshots are stored in `docs/evidence/`.
- [ ] Screenshots contain no account IDs, emails, hosts, credentials, personal
      notifications, or non-synthetic data.
- [ ] The final video is shorter than three minutes.
- [ ] The video shows the live CloudFront application functioning.
- [ ] The video visibly demonstrates CockroachDB memory retrieval.
- [ ] The video is public on YouTube or Vimeo and works in an incognito window.
- [ ] The final live app and video URLs are added to Devpost.

## Security and secrets

- [ ] Current-tree secret scan returns no real findings.
- [ ] Full Git-history secret scan returns no real findings.
- [ ] Tracked-file review finds no `.env`, private key, credential, or raw
      evidence file.
- [ ] Dependency audits are reviewed and any accepted exception is documented
      with an authoritative advisory.
- [ ] CloudWatch sensitive-log audit passes after final demo seeding.
- [ ] Manual log review finds only approved structured events and metrics.
- [ ] All published AWS or CockroachDB captures are redacted.

## Full validation

- [ ] `python -m pytest -q`
- [ ] `python -m compileall -q backend/app backend/migrations scripts`
- [ ] `npm ci`
- [ ] `npm run lint`
- [ ] `npm run build`
- [ ] `npm test`
- [ ] `npm run test:e2e`
- [ ] `bash -n scripts/*.sh`
- [ ] `sam validate --lint --template-file infra/template.yaml`
- [ ] `sam build --template-file infra/template.yaml`
- [ ] `git diff --check`
- [ ] AWS live acceptance passes against the CloudFront URL.
- [ ] `/health` and `/ready` return expected results immediately before
      submission.
- [ ] CloudWatch alarms are reviewed and healthy.

## Release

- [ ] README contains no placeholder, stale phase status, or unsupported claim.
- [ ] Architecture, demo guide, submission copy, security posture, and judging
      map agree with the deployed behavior.
- [ ] Phase 9 branch is reviewed and merged to `main`.
- [ ] `HEAD`, `main`, and `origin/main` match with a clean working tree.
- [ ] Annotated release tag and GitHub release are created from that exact
      commit.
- [ ] Release notes include validation counts and live acceptance date.
- [ ] Devpost entry is submitted before August 18, 2026 at 5:00 PM EDT.
- [ ] Live resources remain available until judging ends.
