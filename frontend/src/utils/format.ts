import type { Incident, RuleViolation } from "../api/types";

export function formatDateTime(value: string | null): string {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatDuration(
  startedAt: string,
  completedAt: string,
): string {
  const seconds = Math.max(
    0,
    Math.round(
      (new Date(completedAt).getTime() -
        new Date(startedAt).getTime()) /
        1000,
    ),
  );

  if (seconds < 60) {
    return `${seconds}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  if (minutes < 60) {
    return remainingSeconds
      ? `${minutes}m ${remainingSeconds}s`
      : `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

export function formatNumber(value: number | null): string {
  return value === null
    ? "Not reported"
    : new Intl.NumberFormat().format(value);
}

export function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function getViolations(incident: Incident): RuleViolation[] {
  const violations = incident.details.violations;

  if (!Array.isArray(violations)) {
    return [];
  }

  return violations.filter(
    (violation): violation is RuleViolation =>
      typeof violation === "object" &&
      violation !== null &&
      typeof (violation as RuleViolation).rule_code === "string" &&
      typeof (violation as RuleViolation).severity === "string" &&
      typeof (violation as RuleViolation).message === "string",
  );
}

export function truncateId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}
