import {
  ArrowRight,
  Clock3,
  Database,
  GitBranch,
  Timer,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getPipelines } from "../api/client";
import type { Pipeline } from "../api/types";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "../components/AsyncState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatNumber } from "../utils/format";

export function PipelinesPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPipelines = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      setPipelines(await getPipelines());
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load pipelines.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPipelines();
  }, [loadPipelines]);

  return (
    <main className="page">
      <PageHeader
        eyebrow="Data operations"
        title="Pipelines"
        description="Reliability thresholds and execution history for every tracked data workflow."
      />

      {loading ? (
        <LoadingState label="Loading pipelines" />
      ) : error ? (
        <ErrorState message={error} onRetry={loadPipelines} />
      ) : pipelines.length === 0 ? (
        <EmptyState
          title="No pipelines yet"
          message="Create your first pipeline through the API, then its run history will appear here."
        />
      ) : (
        <section className="pipeline-card-grid">
          {pipelines.map((pipeline) => (
            <Link
              className="pipeline-card"
              key={pipeline.id}
              to={`/pipelines/${pipeline.id}`}
            >
              <div className="pipeline-card__header">
                <span className="pipeline-card__icon">
                  <GitBranch size={20} />
                </span>
                <StatusBadge
                  value={pipeline.enabled ? "enabled" : "disabled"}
                />
              </div>
              <div className="pipeline-card__body">
                <h2>{pipeline.name}</h2>
                <p>
                  {pipeline.description ??
                    "No pipeline description has been provided."}
                </p>
              </div>
              <dl className="threshold-grid">
                <div>
                  <dt>
                    <Timer size={14} />
                    Max duration
                  </dt>
                  <dd>
                    {pipeline.max_duration_seconds === null
                      ? "Not set"
                      : `${pipeline.max_duration_seconds}s`}
                  </dd>
                </div>
                <div>
                  <dt>
                    <Database size={14} />
                    Minimum rows
                  </dt>
                  <dd>{formatNumber(pipeline.min_rows_processed)}</dd>
                </div>
                <div>
                  <dt>
                    <Clock3 size={14} />
                    Start delay
                  </dt>
                  <dd>
                    {pipeline.max_start_delay_seconds === null
                      ? "Not set"
                      : `${pipeline.max_start_delay_seconds}s`}
                  </dd>
                </div>
              </dl>
              <span className="pipeline-card__link">
                View run history <ArrowRight size={16} />
              </span>
            </Link>
          ))}
        </section>
      )}
    </main>
  );
}
