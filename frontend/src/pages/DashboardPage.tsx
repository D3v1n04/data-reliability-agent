import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  GitBranch,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getIncidents, getPipelines } from "../api/client";
import type { Incident, Pipeline } from "../api/types";
import { ErrorState, LoadingState } from "../components/AsyncState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";

export function DashboardPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [pipelineData, incidentData] = await Promise.all([
        getPipelines(),
        getIncidents(),
      ]);
      setPipelines(pipelineData);
      setIncidents(incidentData);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load the operations overview.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  if (loading) {
    return (
      <main className="page">
        <LoadingState label="Loading reliability overview" />
      </main>
    );
  }

  if (error) {
    return (
      <main className="page">
        <PageHeader title="Operations overview" />
        <ErrorState message={error} onRetry={loadOverview} />
      </main>
    );
  }

  const openIncidents = incidents.filter(
    (incident) => incident.status === "open",
  );
  const investigatingIncidents = incidents.filter(
    (incident) => incident.status === "investigating",
  );
  const criticalActive = incidents.filter(
    (incident) =>
      incident.severity === "critical" &&
      incident.status !== "resolved",
  );
  const activeIncidents = incidents
    .filter((incident) => incident.status !== "resolved")
    .slice(0, 5);

  return (
    <main className="page">
      <PageHeader
        eyebrow="Operations"
        title="Reliability overview"
        description="Current pipeline coverage, active incidents, and the evidence that needs attention."
        actions={
          <Link className="button button--primary" to="/incidents">
            Review incidents
            <ArrowRight size={17} />
          </Link>
        }
      />

      <section className="metric-grid" aria-label="Reliability metrics">
        <MetricCard
          label="Tracked pipelines"
          value={pipelines.length}
          detail={`${pipelines.filter((pipeline) => pipeline.enabled).length} enabled`}
          icon={GitBranch}
        />
        <MetricCard
          label="Open incidents"
          value={openIncidents.length}
          detail="Awaiting investigation"
          icon={AlertTriangle}
          tone={openIncidents.length ? "warning" : "success"}
        />
        <MetricCard
          label="Investigating"
          value={investigatingIncidents.length}
          detail="Actively being reviewed"
          icon={AlertOctagon}
          tone={investigatingIncidents.length ? "danger" : "neutral"}
        />
        <MetricCard
          label="Critical active"
          value={criticalActive.length}
          detail={
            criticalActive.length
              ? "Immediate attention needed"
              : "No critical incidents"
          }
          icon={CheckCircle2}
          tone={criticalActive.length ? "danger" : "success"}
        />
      </section>

      <div className="content-grid content-grid--wide">
        <section className="panel">
          <div className="panel__header">
            <div>
              <span className="eyebrow">Priority queue</span>
              <h2>Active incidents</h2>
            </div>
            <Link className="text-link" to="/incidents">
              View all <ArrowRight size={15} />
            </Link>
          </div>

          {activeIncidents.length ? (
            <div className="incident-feed">
              {activeIncidents.map((incident) => (
                <Link
                  className="incident-feed__item"
                  key={incident.id}
                  to={`/incidents/${incident.id}`}
                >
                  <span
                    className={`severity-marker severity-marker--${incident.severity}`}
                  />
                  <div className="incident-feed__content">
                    <div>
                      <strong>{incident.title}</strong>
                      <span>{incident.source}</span>
                    </div>
                    <div className="incident-feed__meta">
                      <StatusBadge value={incident.severity} />
                      <StatusBadge value={incident.status} />
                      <time>{formatDateTime(incident.detected_at)}</time>
                    </div>
                  </div>
                  <ArrowRight size={17} />
                </Link>
              ))}
            </div>
          ) : (
            <div className="inline-empty">
              <CheckCircle2 size={22} />
              <div>
                <strong>No active incidents</strong>
                <span>The deterministic engine has no unresolved alerts.</span>
              </div>
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel__header">
            <div>
              <span className="eyebrow">Coverage</span>
              <h2>Pipelines</h2>
            </div>
            <Link className="text-link" to="/pipelines">
              Explore <ArrowRight size={15} />
            </Link>
          </div>

          {pipelines.length ? (
            <div className="pipeline-list">
              {pipelines.slice(0, 6).map((pipeline) => (
                <Link
                  className="pipeline-list__item"
                  key={pipeline.id}
                  to={`/pipelines/${pipeline.id}`}
                >
                  <span className="pipeline-icon">
                    <GitBranch size={17} />
                  </span>
                  <div>
                    <strong>{pipeline.name}</strong>
                    <span>
                      {pipeline.description ?? "No description provided"}
                    </span>
                  </div>
                  <StatusBadge
                    value={pipeline.enabled ? "enabled" : "disabled"}
                  />
                </Link>
              ))}
            </div>
          ) : (
            <div className="inline-empty">
              <GitBranch size={22} />
              <div>
                <strong>No pipelines configured</strong>
                <span>Create a pipeline through the API to begin.</span>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
