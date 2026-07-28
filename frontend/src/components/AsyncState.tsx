import {
  AlertCircle,
  Inbox,
  RefreshCw,
} from "lucide-react";
import type { ReactNode } from "react";

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function LoadingState({
  label = "Loading data",
}: {
  label?: string;
}) {
  return (
    <div className="loading-state" role="status" aria-label={label}>
      <div className="loading-state__header">
        <span className="skeleton skeleton--icon" />
        <span className="skeleton skeleton--title" />
      </div>
      <span className="skeleton skeleton--line" />
      <span className="skeleton skeleton--line skeleton--short" />
      <div className="loading-state__grid">
        <span className="skeleton skeleton--card" />
        <span className="skeleton skeleton--card" />
        <span className="skeleton skeleton--card" />
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="state-card state-card--error" role="alert">
      <span className="state-card__icon">
        <AlertCircle size={22} />
      </span>
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {onRetry && (
        <button className="button button--secondary" onClick={onRetry}>
          <RefreshCw size={16} />
          Try again
        </button>
      )}
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  message: string;
  action?: ReactNode;
}

export function EmptyState({
  title,
  message,
  action,
}: EmptyStateProps) {
  return (
    <div className="state-card state-card--empty">
      <span className="state-card__icon">
        <Inbox size={22} />
      </span>
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {action}
    </div>
  );
}
