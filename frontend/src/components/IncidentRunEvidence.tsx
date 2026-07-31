import { AlertCircle, ScrollText } from "lucide-react";

import type { PipelineRun } from "../api/types";
import { formatDuration, formatNumber } from "../utils/format";
import { StatusBadge } from "./StatusBadge";

interface IncidentRunEvidenceProps {
  run: PipelineRun;
}

export function IncidentRunEvidence({
  run,
}: IncidentRunEvidenceProps) {
  return (
    <div className="run-evidence">
      <div className="run-evidence__stats">
        <div>
          <span>Run status</span>
          <StatusBadge value={run.status} />
        </div>
        <div>
          <span>Duration</span>
          <strong>
            {formatDuration(run.started_at, run.completed_at)}
          </strong>
        </div>
        <div>
          <span>Rows processed</span>
          <strong>{formatNumber(run.rows_processed)}</strong>
        </div>
        <div>
          <span>Quality failures</span>
          <strong>{run.quality_checks_failed}</strong>
        </div>
      </div>
      {run.error_message && (
        <div className="error-evidence">
          <AlertCircle size={18} />
          <div>
            <span>Run error</span>
            <code>{run.error_message}</code>
          </div>
        </div>
      )}
      {run.logs.length > 0 && (
        <details className="evidence-disclosure">
          <summary>
            <ScrollText size={17} />
            View {run.logs.length} log entr
            {run.logs.length === 1 ? "y" : "ies"}
          </summary>
          <ol className="log-list">
            {run.logs.map((entry, index) => (
              <li key={`${index}-${entry}`}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <code>{entry}</code>
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
