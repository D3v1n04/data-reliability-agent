export type Severity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "open" | "investigating" | "resolved";
export type RunStatus = "succeeded" | "failed" | "cancelled";

export interface Pipeline {
  id: string;
  name: string;
  description: string | null;
  max_duration_seconds: number | null;
  min_rows_processed: number | null;
  max_start_delay_seconds: number | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface PipelineRun {
  id: string;
  pipeline_id: string;
  external_run_id: string;
  status: RunStatus;
  scheduled_at: string;
  started_at: string;
  completed_at: string;
  rows_processed: number | null;
  quality_checks_failed: number;
  metrics: Record<string, unknown>;
  error_message: string | null;
  logs: string[];
  created_at: string;
}

export interface RuleViolation {
  rule_code: string;
  severity: Severity;
  message: string;
  actual?: string | number | null;
  threshold?: string | number | null;
}

export interface Incident {
  id: string;
  pipeline_run_id: string | null;
  source: string;
  title: string;
  description: string | null;
  severity: Severity;
  status: IncidentStatus;
  detected_at: string;
  resolved_at: string | null;
  details: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SimilarIncidentEvidence {
  incident_id: string;
  distance: number;
  similarity: number;
  title: string;
  pipeline_name: string;
}

export interface DiagnosisEvidence {
  current_incident_id?: string;
  deterministic_violations?: RuleViolation[];
  similar_incidents?: SimilarIncidentEvidence[];
  [key: string]: unknown;
}

export interface IncidentDiagnosis {
  id: string;
  incident_id: string;
  explanation: string;
  likely_causes: string[];
  recommendations: string[];
  confidence: number;
  evidence: DiagnosisEvidence;
  text_model_id: string;
  created_at: string;
}

export interface IncidentFilters {
  status?: IncidentStatus | "";
  severity?: Severity | "";
  source?: string;
  limit?: number;
  offset?: number;
}

export interface ApiErrorBody {
  detail?: string;
}
