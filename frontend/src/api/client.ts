import type {
  ApiErrorBody,
  Incident,
  IncidentDiagnosis,
  IncidentFilters,
  IncidentStatus,
  Pipeline,
  PipelineRun,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      "Could not reach the Data Reliability Agent API.",
      0,
    );
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;

    try {
      const body = (await response.json()) as ApiErrorBody;
      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the status-based fallback for non-JSON responses.
    }

    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<{ status: string }> {
  return request("/health");
}

export function getPipelines(): Promise<Pipeline[]> {
  return request("/api/pipelines?limit=100");
}

export function getPipeline(pipelineId: string): Promise<Pipeline> {
  return request(`/api/pipelines/${pipelineId}`);
}

export function getPipelineRuns(
  pipelineId: string,
): Promise<PipelineRun[]> {
  return request(`/api/pipelines/${pipelineId}/runs?limit=100`);
}

export function getPipelineRun(runId: string): Promise<PipelineRun> {
  return request(`/api/pipeline-runs/${runId}`);
}

export function getIncidents(
  filters: IncidentFilters = {},
): Promise<Incident[]> {
  const params = new URLSearchParams();
  params.set("limit", String(filters.limit ?? 100));
  params.set("offset", String(filters.offset ?? 0));

  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.severity) {
    params.set("severity", filters.severity);
  }
  if (filters.source?.trim()) {
    params.set("source", filters.source.trim());
  }

  return request(`/api/incidents?${params.toString()}`);
}

export function getIncident(incidentId: string): Promise<Incident> {
  return request(`/api/incidents/${incidentId}`);
}

export function getDiagnosis(
  incidentId: string,
): Promise<IncidentDiagnosis> {
  return request(`/api/incidents/${incidentId}/diagnosis`);
}

export function diagnoseIncident(
  incidentId: string,
): Promise<IncidentDiagnosis> {
  return request(`/api/incidents/${incidentId}/diagnosis`, {
    method: "POST",
  });
}

export function updateIncidentStatus(
  incidentId: string,
  status: IncidentStatus,
): Promise<Incident> {
  return request(`/api/incidents/${incidentId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
