import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CalendarClock,
  CheckCheck,
  Database,
  FileWarning,
  ScrollText,
  Timer,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getIncidents,
  getPipeline,
  getPipelineRun,
} from "../api/client";
import type { Incident, Pipeline, PipelineRun } from "../api/types";
import { ErrorState, LoadingState } from "../components/AsyncState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  formatDateTime,
  formatDuration,
  formatNumber,
  titleCase,
} from "../utils/format";

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRun = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const runData = await getPipelineRun(runId);
      const [pipelineData, incidents] = await Promise.all([
        getPipeline(runData.pipeline_id),
        getIncidents({ pipeline_run_id: runData.id }),
      ]);
      setRun(runData);
      setPipeline(pipelineData);
      setIncident(
        incidents.find(
          (candidate) => candidate.pipeline_run_id === runData.id,
        ) ?? null,
      );
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load the pipeline run.",
      );
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void loadRun();
  }, [loadRun]);

  if (loading) {
    return (
      <main className="page">
        <LoadingState label="Loading pipeline run" />
      </main>
    );
  }

  if (error || !run || !pipeline) {
    return (
      <main className="page">
        <ErrorState
          message={error ?? "Pipeline run was not found."}
          onRetry={loadRun}
        />
      </main>
    );
  }

  const metrics = Object.entries(run.metrics);

  return (
    <main className="page">
      <Link className="back-link" to={`/pipelines/${pipeline.id}`}>
        <ArrowLeft size={16} /> {pipeline.name}
      </Link>
      <PageHeader
        eyebrow="Pipeline run"
        title={run.external_run_id}
        description={`Execution evidence for ${pipeline.name}.`}
        actions={<StatusBadge value={run.status} />}
      />

      {incident && (
        <Link
          className="incident-callout"
          to={`/incidents/${incident.id}`}
        >
          <span className="incident-callout__icon">
            <AlertTriangle size={20} />
          </span>
          <div>
            <span>Incident created from this run</span>
            <strong>{incident.title}</strong>
          </div>
          <div className="incident-callout__badges">
            <StatusBadge value={incident.severity} />
            <StatusBadge value={incident.status} />
          </div>
          <ArrowRight size={18} />
        </Link>
      )}

      <section className="run-stat-grid" aria-label="Run summary">
        <div>
          <CalendarClock size={18} />
          <span>Completed</span>
          <strong>{formatDateTime(run.completed_at)}</strong>
        </div>
        <div>
          <Timer size={18} />
          <span>Duration</span>
          <strong>
            {formatDuration(run.started_at, run.completed_at)}
          </strong>
        </div>
        <div>
          <Database size={18} />
          <span>Rows processed</span>
          <strong>{formatNumber(run.rows_processed)}</strong>
        </div>
        <div>
          <CheckCheck size={18} />
          <span>Quality failures</span>
          <strong>{run.quality_checks_failed}</strong>
        </div>
      </section>

      <div className="content-grid">
        <section className="panel">
          <div className="panel__header">
            <div>
              <span className="eyebrow">Timeline</span>
              <h2>Execution timing</h2>
            </div>
          </div>
          <dl className="definition-list">
            <div>
              <dt>Scheduled</dt>
              <dd>{formatDateTime(run.scheduled_at)}</dd>
            </div>
            <div>
              <dt>Started</dt>
              <dd>{formatDateTime(run.started_at)}</dd>
            </div>
            <div>
              <dt>Completed</dt>
              <dd>{formatDateTime(run.completed_at)}</dd>
            </div>
            <div>
              <dt>External run ID</dt>
              <dd className="mono">{run.external_run_id}</dd>
            </div>
          </dl>
        </section>

        <section className="panel">
          <div className="panel__header">
            <div>
              <span className="eyebrow">Measurements</span>
              <h2>Run metrics</h2>
            </div>
          </div>
          {metrics.length ? (
            <dl className="definition-list">
              {metrics.map(([key, value]) => (
                <div key={key}>
                  <dt>{titleCase(key)}</dt>
                  <dd>
                    {typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <div className="inline-empty inline-empty--compact">
              <Database size={20} />
              <span>No additional metrics were submitted.</span>
            </div>
          )}
        </section>
      </div>

      {run.error_message && (
        <section className="panel panel--danger">
          <div className="panel__header">
            <div>
              <span className="eyebrow">Failure evidence</span>
              <h2>
                <FileWarning size={19} /> Error message
              </h2>
            </div>
          </div>
          <pre className="evidence-code">{run.error_message}</pre>
        </section>
      )}

      <section className="panel">
        <div className="panel__header">
          <div>
            <span className="eyebrow">Raw evidence</span>
            <h2>
              <ScrollText size={19} /> Run logs
            </h2>
          </div>
          <span className="panel__count">{run.logs.length} entries</span>
        </div>
        {run.logs.length ? (
          <ol className="log-list">
            {run.logs.map((entry, index) => (
              <li key={`${index}-${entry}`}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <code>{entry}</code>
              </li>
            ))}
          </ol>
        ) : (
          <div className="inline-empty inline-empty--compact">
            <ScrollText size={20} />
            <span>No log entries were submitted with this run.</span>
          </div>
        )}
      </section>
    </main>
  );
}
