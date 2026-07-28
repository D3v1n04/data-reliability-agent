import {
  ArrowRight,
  Filter,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Link } from "react-router-dom";

import { getIncidents } from "../api/client";
import type {
  Incident,
  IncidentFilters,
  IncidentStatus,
  Severity,
} from "../api/types";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "../components/AsyncState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime, getViolations } from "../utils/format";

interface FilterForm {
  status: IncidentStatus | "";
  severity: Severity | "";
  source: string;
}

const emptyFilters: FilterForm = {
  status: "",
  severity: "",
  source: "",
};

export function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [filterForm, setFilterForm] =
    useState<FilterForm>(emptyFilters);
  const [appliedFilters, setAppliedFilters] =
    useState<IncidentFilters>(emptyFilters);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadIncidents = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      setIncidents(await getIncidents(appliedFilters));
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load incidents.",
      );
    } finally {
      setLoading(false);
    }
  }, [appliedFilters]);

  useEffect(() => {
    void loadIncidents();
  }, [loadIncidents]);

  const visibleIncidents = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    if (!normalizedSearch) {
      return incidents;
    }

    return incidents.filter((incident) =>
      [
        incident.title,
        incident.description,
        incident.source,
        incident.id,
      ]
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(normalizedSearch),
        ),
    );
  }, [incidents, search]);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setAppliedFilters({ ...filterForm });
  }

  function clearFilters() {
    setFilterForm(emptyFilters);
    setAppliedFilters(emptyFilters);
    setSearch("");
  }

  const hasFilters =
    Boolean(appliedFilters.status) ||
    Boolean(appliedFilters.severity) ||
    Boolean(appliedFilters.source) ||
    Boolean(search);

  return (
    <main className="page">
      <PageHeader
        eyebrow="Reliability engine"
        title="Incidents"
        description="Filter deterministic failures, inspect their evidence, and move each incident through its audit-safe lifecycle."
      />

      <form className="filter-bar" onSubmit={applyFilters}>
        <label className="search-field">
          <Search size={17} />
          <span className="sr-only">Search incidents</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search incidents"
          />
        </label>
        <label className="select-field">
          <span>Status</span>
          <select
            value={filterForm.status}
            onChange={(event) =>
              setFilterForm((current) => ({
                ...current,
                status: event.target.value as IncidentStatus | "",
              }))
            }
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
          </select>
        </label>
        <label className="select-field">
          <span>Severity</span>
          <select
            value={filterForm.severity}
            onChange={(event) =>
              setFilterForm((current) => ({
                ...current,
                severity: event.target.value as Severity | "",
              }))
            }
          >
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
        <label className="input-field">
          <span>Source</span>
          <input
            value={filterForm.source}
            onChange={(event) =>
              setFilterForm((current) => ({
                ...current,
                source: event.target.value,
              }))
            }
            placeholder="reliability-engine"
            maxLength={100}
          />
        </label>
        <button className="button button--primary" type="submit">
          <Filter size={16} /> Apply
        </button>
        {hasFilters && (
          <button
            className="button button--ghost"
            type="button"
            onClick={clearFilters}
          >
            <X size={16} /> Clear
          </button>
        )}
      </form>

      <div className="result-summary">
        <span>
          <SlidersHorizontal size={16} />
          {loading
            ? "Loading incidents"
            : `${visibleIncidents.length} incident${
                visibleIncidents.length === 1 ? "" : "s"
              }`}
        </span>
        <span>Newest detected first</span>
      </div>

      {loading ? (
        <LoadingState label="Loading incidents" />
      ) : error ? (
        <ErrorState message={error} onRetry={loadIncidents} />
      ) : visibleIncidents.length === 0 ? (
        <EmptyState
          title={hasFilters ? "No matching incidents" : "No incidents yet"}
          message={
            hasFilters
              ? "Adjust or clear the filters to expand the results."
              : "Incidents created by the reliability engine will appear here."
          }
          action={
            hasFilters ? (
              <button
                className="button button--secondary"
                type="button"
                onClick={clearFilters}
              >
                Clear filters
              </button>
            ) : undefined
          }
        />
      ) : (
        <section className="incident-list" aria-label="Incident results">
          {visibleIncidents.map((incident) => {
            const violations = getViolations(incident);

            return (
              <Link
                className="incident-row"
                key={incident.id}
                to={`/incidents/${incident.id}`}
              >
                <span
                  className={`incident-row__accent incident-row__accent--${incident.severity}`}
                />
                <div className="incident-row__main">
                  <div className="incident-row__title">
                    <h2>{incident.title}</h2>
                    <div>
                      <StatusBadge value={incident.severity} />
                      <StatusBadge value={incident.status} />
                    </div>
                  </div>
                  <p>
                    {incident.description ??
                      "No additional incident description."}
                  </p>
                  <div className="incident-row__meta">
                    <span>{incident.source}</span>
                    <span>{formatDateTime(incident.detected_at)}</span>
                    <span>
                      {violations.length} deterministic violation
                      {violations.length === 1 ? "" : "s"}
                    </span>
                  </div>
                </div>
                <ArrowRight className="incident-row__arrow" size={19} />
              </Link>
            );
          })}
        </section>
      )}
    </main>
  );
}
