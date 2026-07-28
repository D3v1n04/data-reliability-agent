import type {
  Incident,
  IncidentDiagnosis,
  Pipeline,
  PipelineRun,
} from "../api/types";

export const pipeline: Pipeline = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "daily-customer-import",
  description: "Imports and validates customer records every morning.",
  max_duration_seconds: 900,
  min_rows_processed: 1000,
  max_start_delay_seconds: 300,
  enabled: true,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

export const pipelineRun: PipelineRun = {
  id: "22222222-2222-2222-2222-222222222222",
  pipeline_id: pipeline.id,
  external_run_id: "customer-import-2026-07-28",
  status: "failed",
  scheduled_at: "2026-07-28T12:00:00Z",
  started_at: "2026-07-28T12:08:00Z",
  completed_at: "2026-07-28T12:30:00Z",
  rows_processed: 450,
  quality_checks_failed: 2,
  metrics: { rejected_rows: 550 },
  error_message: "Source file validation failed",
  logs: [
    "Received customer_2026-07-28.csv",
    "Validation failed for 550 records",
  ],
  created_at: "2026-07-28T12:30:02Z",
};

export const incident: Incident = {
  id: "33333333-3333-3333-3333-333333333333",
  pipeline_run_id: pipelineRun.id,
  source: "reliability-engine",
  title: "Reliability failure: daily-customer-import",
  description: "The customer import failed deterministic checks.",
  severity: "critical",
  status: "open",
  detected_at: "2026-07-28T12:30:01Z",
  resolved_at: null,
  details: {
    violations: [
      {
        rule_code: "RUN_FAILED",
        severity: "critical",
        message: "Pipeline reported a failed status",
        actual: "failed",
        threshold: "succeeded",
      },
      {
        rule_code: "ROW_COUNT_BELOW_MINIMUM",
        severity: "high",
        message: "Rows processed were below the configured minimum",
        actual: 450,
        threshold: 1000,
      },
    ],
  },
  created_at: "2026-07-28T12:30:01Z",
  updated_at: "2026-07-28T12:30:01Z",
};

export const diagnosis: IncidentDiagnosis = {
  id: "44444444-4444-4444-4444-444444444444",
  incident_id: incident.id,
  explanation:
    "The source file failed validation and the run processed fewer rows than the deterministic minimum.",
  likely_causes: [
    "A source schema or formatting change caused record rejection.",
    "The upstream export may have been incomplete.",
  ],
  recommendations: [
    "Compare the rejected file schema with the last successful import.",
    "Inspect the validation errors before retrying the pipeline.",
  ],
  confidence: 0.88,
  evidence: {
    current_incident_id: incident.id,
    deterministic_violations:
      incident.details.violations as IncidentDiagnosis["evidence"]["deterministic_violations"],
    similar_incidents: [
      {
        incident_id: "55555555-5555-5555-5555-555555555555",
        distance: 0.12,
        similarity: 0.88,
        title: "Customer import validation failure",
        pipeline_name: "daily-customer-import",
      },
    ],
  },
  text_model_id: "amazon.nova-lite-v1:0",
  created_at: "2026-07-28T12:35:00Z",
};
