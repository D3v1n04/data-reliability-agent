import type {
  IncidentStatus,
  RunStatus,
  Severity,
} from "../api/types";
import { titleCase } from "../utils/format";

type BadgeValue =
  | IncidentStatus
  | RunStatus
  | Severity
  | "enabled"
  | "disabled";

interface StatusBadgeProps {
  value: BadgeValue;
  dot?: boolean;
}

export function StatusBadge({
  value,
  dot = true,
}: StatusBadgeProps) {
  return (
    <span className={`status-badge status-badge--${value}`}>
      {dot && <span className="status-badge__dot" aria-hidden="true" />}
      {titleCase(value)}
    </span>
  );
}
