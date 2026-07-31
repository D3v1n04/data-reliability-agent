import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  CircleDot,
  Clock3,
  Database,
  FileSearch,
  GitCompareArrows,
  Lightbulb,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  TriangleAlert,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  diagnoseIncident,
  getDiagnosis,
  getIncident,
  getPipeline,
  getPipelineRun,
  updateIncidentStatus,
} from "../api/client";
import type {
  Incident,
  IncidentDiagnosis,
  IncidentStatus,
  Pipeline,
  PipelineRun,
} from "../api/types";
import { ErrorState, LoadingState } from "../components/AsyncState";
import { IncidentRunEvidence } from "../components/IncidentRunEvidence";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  formatDateTime,
  getViolations,
  titleCase,
  truncateId,
} from "../utils/format";

export function IncidentDetailPage() {
  const { incidentId = "" } = useParams();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [diagnosis, setDiagnosis] =
    useState<IncidentDiagnosis | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [diagnosisError, setDiagnosisError] = useState<string | null>(
    null,
  );
  const [diagnosing, setDiagnosing] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const loadIncident = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    setDiagnosisError(null);

    try {
      const incidentData = await getIncident(incidentId);
      setIncident(incidentData);

      const contextPromise = incidentData.pipeline_run_id
        ? getPipelineRun(incidentData.pipeline_run_id).then(
            async (runData) => ({
              run: runData,
              pipeline: await getPipeline(runData.pipeline_id),
            }),
          )
        : Promise.resolve({ run: null, pipeline: null });

      const diagnosisPromise = getDiagnosis(incidentId).catch(
        (diagnosisLoadError) => {
          if (
            diagnosisLoadError instanceof ApiError &&
            diagnosisLoadError.status === 404
          ) {
            return null;
          }
          throw diagnosisLoadError;
        },
      );

      const [context, diagnosisData] = await Promise.all([
        contextPromise,
        diagnosisPromise,
      ]);

      setRun(context.run);
      setPipeline(context.pipeline);
      setDiagnosis(diagnosisData);
    } catch (loadError) {
      setPageError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load incident evidence.",
      );
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    void loadIncident();
  }, [loadIncident]);

  const violations = useMemo(
    () => (incident ? getViolations(incident) : []),
    [incident],
  );

  async function generateDiagnosis() {
    setDiagnosing(true);
    setDiagnosisError(null);

    try {
      setDiagnosis(await diagnoseIncident(incidentId));
    } catch (diagnosisRequestError) {
      setDiagnosisError(
        diagnosisRequestError instanceof Error
          ? diagnosisRequestError.message
          : "Unable to generate a diagnosis.",
      );
    } finally {
      setDiagnosing(false);
    }
  }

  async function transitionStatus(nextStatus: IncidentStatus) {
    setUpdatingStatus(true);
    setStatusError(null);

    try {
      setIncident(await updateIncidentStatus(incidentId, nextStatus));
    } catch (updateError) {
      setStatusError(
        updateError instanceof Error
          ? updateError.message
          : "Unable to update incident status.",
      );
    } finally {
      setUpdatingStatus(false);
    }
  }

  if (loading) {
    return (
      <main className="page">
        <LoadingState label="Loading incident evidence" />
      </main>
    );
  }

  if (pageError || !incident) {
    return (
      <main className="page">
        <Link className="back-link" to="/incidents">
          <ArrowLeft size={16} /> Incidents
        </Link>
        <ErrorState
          message={pageError ?? "Incident was not found."}
          onRetry={loadIncident}
        />
      </main>
    );
  }

  const nextStatus =
    incident.status === "open"
      ? ("investigating" as const)
      : incident.status === "investigating"
        ? ("resolved" as const)
        : null;

  const similarIncidents =
    diagnosis?.evidence.similar_incidents ?? [];
  const confidence = diagnosis
    ? Math.round(Math.min(1, Math.max(0, diagnosis.confidence)) * 100)
    : 0;

  return (
    <main className="page">
      <Link className="back-link" to="/incidents">
        <ArrowLeft size={16} /> Incidents
      </Link>
      <PageHeader
        eyebrow={`Incident ${truncateId(incident.id)}`}
        title={incident.title}
        description={
          incident.description ??
          "Deterministic reliability incident evidence."
        }
        actions={
          <div className="header-badges">
            <StatusBadge value={incident.severity} />
            <StatusBadge value={incident.status} />
          </div>
        }
      />

      <section className="lifecycle-bar">
        <div className="lifecycle-steps" aria-label="Incident lifecycle">
          {(["open", "investigating", "resolved"] as const).map(
            (status, index) => {
              const statusIndex = [
                "open",
                "investigating",
                "resolved",
              ].indexOf(incident.status);
              const complete = index <= statusIndex;

              return (
                <div
                  className={`lifecycle-step ${
                    complete ? "lifecycle-step--complete" : ""
                  }`}
                  key={status}
                >
                  <span>{complete ? <CheckCircle2 size={17} /> : index + 1}</span>
                  <strong>{titleCase(status)}</strong>
                </div>
              );
            },
          )}
        </div>
        <div className="lifecycle-action">
          {nextStatus ? (
            <button
              className="button button--primary"
              type="button"
              disabled={updatingStatus}
              onClick={() => void transitionStatus(nextStatus)}
            >
              {updatingStatus ? (
                <LoaderCircle className="spin" size={17} />
              ) : nextStatus === "investigating" ? (
                <FileSearch size={17} />
              ) : (
                <ShieldCheck size={17} />
              )}
              {nextStatus === "investigating"
                ? "Start investigation"
                : "Resolve incident"}
            </button>
          ) : (
            <span className="terminal-state">
              <ShieldCheck size={17} /> Terminal audit record
            </span>
          )}
          {statusError && (
            <span className="field-error" role="alert">
              {statusError}
            </span>
          )}
        </div>
      </section>

      <section className="incident-metadata" aria-label="Incident metadata">
        <div>
          <Clock3 size={17} />
          <span>Detected</span>
          <strong>{formatDateTime(incident.detected_at)}</strong>
        </div>
        <div>
          <CircleDot size={17} />
          <span>Source</span>
          <strong>{incident.source}</strong>
        </div>
        <div>
          <Database size={17} />
          <span>Pipeline</span>
          <strong>{pipeline?.name ?? "Manual incident"}</strong>
        </div>
        <div>
          <GitCompareArrows size={17} />
          <span>Run</span>
          {run ? (
            <Link to={`/runs/${run.id}`}>{run.external_run_id}</Link>
          ) : (
            <strong>Not associated</strong>
          )}
        </div>
      </section>

      <section className="panel evidence-panel">
        <div className="panel__header">
          <div>
            <span className="eyebrow">Source of truth</span>
            <h2>
              <ShieldCheck size={20} /> Deterministic evidence
            </h2>
          </div>
          <span className="panel__count">
            {violations.length} violation
            {violations.length === 1 ? "" : "s"}
          </span>
        </div>

        {violations.length ? (
          <div className="violation-list">
            {violations.map((violation, index) => (
              <article
                className={`violation-card violation-card--${violation.severity}`}
                key={`${violation.rule_code}-${index}`}
              >
                <div className="violation-card__topline">
                  <span className="violation-card__icon">
                    <TriangleAlert size={18} />
                  </span>
                  <div>
                    <strong>{titleCase(violation.rule_code)}</strong>
                    <code>{violation.rule_code}</code>
                  </div>
                  <StatusBadge value={violation.severity} />
                </div>
                <p>{violation.message}</p>
                {(violation.actual !== undefined ||
                  violation.threshold !== undefined) && (
                  <dl className="evidence-comparison">
                    <div>
                      <dt>Observed</dt>
                      <dd>{String(violation.actual ?? "Not reported")}</dd>
                    </div>
                    <div>
                      <dt>Expected</dt>
                      <dd>{String(violation.threshold ?? "Not set")}</dd>
                    </div>
                  </dl>
                )}
              </article>
            ))}
          </div>
        ) : (
          <div className="inline-empty">
            <AlertCircle size={21} />
            <div>
              <strong>No structured violations available</strong>
              <span>
                This incident does not include deterministic rule details.
              </span>
            </div>
          </div>
        )}

        {run && <IncidentRunEvidence run={run} />}
      </section>

      <section className="panel diagnosis-panel">
        <div className="panel__header">
          <div>
            <span className="eyebrow">Amazon Bedrock + incident memory</span>
            <h2>
              <BrainCircuit size={21} /> AI-assisted diagnosis
            </h2>
          </div>
          {diagnosis && (
            <span className="stored-label">
              <Database size={15} /> Stored diagnosis
            </span>
          )}
        </div>

        {!incident.pipeline_run_id ? (
          <div className="inline-empty">
            <Bot size={22} />
            <div>
              <strong>Diagnosis unavailable</strong>
              <span>
                Only incidents associated with a pipeline run contain the
                required deterministic evidence.
              </span>
            </div>
          </div>
        ) : diagnosis ? (
          <div className="diagnosis-content">
            <div className="diagnosis-explanation">
              <div className="diagnosis-explanation__header">
                <span className="diagnosis-icon">
                  <Sparkles size={19} />
                </span>
                <div>
                  <span>Explanation</span>
                  <h3>What the evidence suggests</h3>
                </div>
                <div
                  className="confidence-ring"
                  style={
                    {
                      "--confidence": `${confidence * 3.6}deg`,
                    } as React.CSSProperties
                  }
                  aria-label={`${confidence}% confidence`}
                >
                  <span>{confidence}%</span>
                </div>
              </div>
              <p>{diagnosis.explanation}</p>
              <span className="model-label">
                Generated by {diagnosis.text_model_id} ·{" "}
                {formatDateTime(diagnosis.created_at)}
              </span>
            </div>

            <div className="diagnosis-columns">
              <div>
                <div className="section-label">
                  <Target size={17} />
                  <h3>Likely causes</h3>
                </div>
                <ol className="diagnosis-list diagnosis-list--causes">
                  {diagnosis.likely_causes.map((cause, index) => (
                    <li key={cause}>
                      <span>{index + 1}</span>
                      <p>{cause}</p>
                    </li>
                  ))}
                </ol>
              </div>
              <div>
                <div className="section-label">
                  <Lightbulb size={17} />
                  <h3>Recommended investigation</h3>
                </div>
                <ol className="diagnosis-list diagnosis-list--recommendations">
                  {diagnosis.recommendations.map(
                    (recommendation) => (
                      <li key={recommendation}>
                        <span>
                          <CheckCircle2 size={15} />
                        </span>
                        <p>{recommendation}</p>
                      </li>
                    ),
                  )}
                </ol>
              </div>
            </div>
          </div>
        ) : (
          <div className="diagnosis-empty">
            <span className="diagnosis-empty__icon">
              <BrainCircuit size={29} />
            </span>
            <div>
              <h3>Generate an evidence-grounded diagnosis</h3>
              <p>
                Nova Lite will explain the failure and propose safe
                investigation steps using deterministic evidence and
                similar stored incident memories.
              </p>
            </div>
            <button
              className="button button--primary button--large"
              type="button"
              disabled={diagnosing}
              onClick={() => void generateDiagnosis()}
            >
              {diagnosing ? (
                <>
                  <LoaderCircle className="spin" size={18} />
                  Generating diagnosis
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  Generate diagnosis
                </>
              )}
            </button>
          </div>
        )}

        {diagnosisError && (
          <div className="inline-error" role="alert">
            <AlertCircle size={18} />
            <div>
              <strong>Diagnosis request failed</strong>
              <span>{diagnosisError}</span>
            </div>
            <button
              className="button button--secondary"
              type="button"
              onClick={() => void generateDiagnosis()}
            >
              <RefreshCw size={15} /> Retry
            </button>
          </div>
        )}
      </section>

      {diagnosis && (
        <section className="panel">
          <div className="panel__header">
            <div>
              <span className="eyebrow">CockroachDB vector memory</span>
              <h2>
                <GitCompareArrows size={20} /> Similar historical
                incidents
              </h2>
            </div>
            <span className="panel__count">
              {similarIncidents.length} match
              {similarIncidents.length === 1 ? "" : "es"}
            </span>
          </div>

          {similarIncidents.length ? (
            <div className="similar-list">
              {similarIncidents.map((similar) => (
                <Link
                  className="similar-card"
                  key={similar.incident_id}
                  to={`/incidents/${similar.incident_id}`}
                >
                  <div className="similar-card__score">
                    <strong>{Math.round(similar.similarity * 100)}%</strong>
                    <span>similarity</span>
                  </div>
                  <div>
                    <span>{similar.pipeline_name}</span>
                    <h3>{similar.title}</h3>
                    <code>{truncateId(similar.incident_id)}</code>
                  </div>
                  <ArrowRight size={18} />
                </Link>
              ))}
            </div>
          ) : (
            <div className="inline-empty">
              <GitCompareArrows size={22} />
              <div>
                <strong>No related history yet</strong>
                <span>
                  This diagnosis did not find another stored incident
                  memory to use as evidence.
                </span>
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
