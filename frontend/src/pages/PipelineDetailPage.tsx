import {
  ArrowLeft,
  ArrowRight,
  Clock3,
  Database,
  GitCommitHorizontal,
  Timer,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getPipeline, getPipelineRuns } from "../api/client";
import type { Pipeline, PipelineRun } from "../api/types";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "../components/AsyncState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  formatDateTime,
  formatDuration,
  formatNumber,
} from "../utils/format";

export function PipelineDetailPage() {
  const { pipelineId = "" } = useParams();
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPipeline = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [pipelineData, runData] = await Promise.all([
        getPipeline(pipelineId),
        getPipelineRuns(pipelineId),
      ]);
      setPipeline(pipelineData);
      setRuns(runData);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load pipeline history.",
      );
    } finally {
      setLoading(false);
    }
  }, [pipelineId]);

  useEffect(() => {
    void loadPipeline();
  }, [loadPipeline]);

  if (loading) {
    return (
      <main className="page">
        <LoadingState label="Loading pipeline details" />
      </main>
    );
  }

  if (error || !pipeline) {
    return (
      <main className="page">
        <Link className="back-link" to="/pipelines">
          <ArrowLeft size={16} /> Pipelines
        </Link>
        <ErrorState
          message={error ?? "Pipeline was not found."}
          onRetry={loadPipeline}
        />
      </main>
    );
  }

  return (
    <main className="page">
      <Link className="back-link" to="/pipelines">
        <ArrowLeft size={16} /> Pipelines
      </Link>
      <PageHeader
        eyebrow="Pipeline detail"
        title={pipeline.name}
        description={
          pipeline.description ??
          "Reliability thresholds and recent execution evidence."
        }
        actions={
          <StatusBadge
            value={pipeline.enabled ? "enabled" : "disabled"}
          />
        }
      />

      <section className="threshold-summary" aria-label="Pipeline thresholds">
        <div>
          <span className="threshold-summary__icon">
            <Timer size={18} />
          </span>
          <span>Maximum duration</span>
          <strong>
            {pipeline.max_duration_seconds === null
              ? "Not set"
              : `${pipeline.max_duration_seconds}s`}
          </strong>
        </div>
        <div>
          <span className="threshold-summary__icon">
            <Database size={18} />
          </span>
          <span>Minimum rows</span>
          <strong>{formatNumber(pipeline.min_rows_processed)}</strong>
        </div>
        <div>
          <span className="threshold-summary__icon">
            <Clock3 size={18} />
          </span>
          <span>Maximum start delay</span>
          <strong>
            {pipeline.max_start_delay_seconds === null
              ? "Not set"
              : `${pipeline.max_start_delay_seconds}s`}
          </strong>
        </div>
        <div>
          <span className="threshold-summary__icon">
            <GitCommitHorizontal size={18} />
          </span>
          <span>Recorded runs</span>
          <strong>{runs.length}</strong>
        </div>
      </section>

      <section className="panel">
        <div className="panel__header">
          <div>
            <span className="eyebrow">Execution history</span>
            <h2>Pipeline runs</h2>
          </div>
          <span className="panel__count">{runs.length} records</span>
        </div>

        {runs.length === 0 ? (
          <EmptyState
            title="No runs recorded"
            message="Ingest a pipeline run through the API and it will appear here."
          />
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Completed</th>
                  <th>Duration</th>
                  <th>Rows</th>
                  <th>Quality failures</th>
                  <th aria-label="View run" />
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <Link
                        className="table-primary-link"
                        to={`/runs/${run.id}`}
                      >
                        {run.external_run_id}
                      </Link>
                    </td>
                    <td>
                      <StatusBadge value={run.status} />
                    </td>
                    <td>{formatDateTime(run.completed_at)}</td>
                    <td>
                      {formatDuration(run.started_at, run.completed_at)}
                    </td>
                    <td>{formatNumber(run.rows_processed)}</td>
                    <td>{run.quality_checks_failed}</td>
                    <td>
                      <Link
                        className="icon-link"
                        to={`/runs/${run.id}`}
                        aria-label={`View ${run.external_run_id}`}
                      >
                        <ArrowRight size={17} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
