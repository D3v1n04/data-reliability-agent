# Data Reliability Agent dashboard

React and TypeScript browser interface for pipeline reliability, deterministic
incident evidence, Bedrock diagnosis, similar incident memory, and incident
lifecycle actions.

## Local development

```bash
npm install
npm run dev
```

The dashboard defaults to `http://127.0.0.1:8000` for the FastAPI API. Copy
`.env.example` to `.env` only when you need to override that URL.

Production builds default to same-origin API paths. CloudFront sends `/api/*`,
`/health`, and `/ready` to API Gateway while all other paths use the private S3
frontend origin.

## Verification

```bash
npm run lint
npm run build
npm test
npx playwright install chromium
npm run test:e2e
```

The Vitest suite exercises the incident detail workflow with controlled API
responses. The Playwright workflow navigates from a failed pipeline run to its
incident, generates a diagnosis, reviews related history, and moves the
incident from open to investigating to resolved.
