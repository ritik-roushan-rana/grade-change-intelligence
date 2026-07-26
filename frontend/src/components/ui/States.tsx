import clsx from 'clsx';
import type { ReactNode } from 'react';
import { ApiError } from '../../lib/api';
import { Panel } from './Panel';

/** Placeholder block used while a slow request is in flight. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={clsx('animate-pulse rounded-control bg-hmi-header', className)}
      aria-hidden="true"
    />
  );
}

export function SkeletonPanel({
  lines = 3,
  label = 'LOADING',
  className,
}: {
  lines?: number;
  label?: string;
  className?: string;
}) {
  return (
    <Panel label={label} tag="…" className={className}>
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, index) => (
          <Skeleton key={index} className={index === lines - 1 ? 'h-3 w-2/3' : 'h-3 w-full'} />
        ))}
      </div>
    </Panel>
  );
}

/** Inline activity marker for refreshes that keep stale readings on screen. */
export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 font-mono text-micro uppercase text-hmi-dim">
      <span
        className="h-2.5 w-2.5 animate-spin border border-hmi-bezel border-t-signal"
        aria-hidden="true"
      />
      {label && <span>{label}</span>}
      <span className="sr-only">Loading</span>
    </span>
  );
}

interface ErrorStateProps {
  error: unknown;
  /** What the operator was trying to see, e.g. "risk prediction". */
  context?: string;
  onRetry?: () => void;
}

/**
 * Communication fault, presented as a console diagnostic. Raw fetch/JSON
 * errors never reach the screen — the API layer has already translated them.
 */
export function ErrorState({ error, context, onRetry }: ErrorStateProps) {
  const unreachable = error instanceof ApiError && error.unreachable;
  const message =
    error instanceof ApiError
      ? error.message
      : `Something went wrong loading ${context ?? 'this display'}.`;

  return (
    <div className="rounded-panel border border-alarm-critical/50 bg-hmi-panel">
      <header className="flex items-center justify-between gap-3 border-b border-alarm-critical/40 bg-alarm-critical-fill px-4 py-2">
        <span className="text-tag uppercase text-alarm-critical">
          {unreachable ? 'Communication fault' : 'Display fault'}
        </span>
        <span className="font-mono text-micro text-alarm-critical/80">
          {unreachable ? 'COMM.FAIL' : 'DISP.ERR'}
        </span>
      </header>
      <div className="p-5">
        <p className="text-body text-hmi-text">
          {unreachable
            ? 'No response from the prediction service.'
            : `Could not load ${context ?? 'this display'}.`}
        </p>
        <p className="mt-1.5 font-mono text-caption text-hmi-label">{message}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded-control border border-hmi-bezel bg-hmi-header px-3 py-1.5 font-mono text-micro uppercase text-hmi-text transition-colors hover:border-signal hover:text-signal"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

/** Neutral "no data" panel. */
export function EmptyState({ title, hint, tag }: { title: string; hint?: ReactNode; tag?: string }) {
  return (
    <Panel label="No data" tag={tag ?? 'EMPTY'}>
      <div className="py-10 text-center">
        <p className="font-mono text-pv-xs uppercase text-hmi-label">{title}</p>
        {hint && <p className="mt-2 text-caption text-hmi-dim">{hint}</p>}
      </div>
    </Panel>
  );
}

/** Inline notice where a display is valid but has nothing to compute yet. */
export function Notice({ children, tag }: { children: ReactNode; tag?: string }) {
  return (
    <div className="flex items-start gap-3 rounded-panel border border-hmi-bezel bg-hmi-panel p-5">
      <span className="mt-0.5 font-mono text-micro uppercase text-hmi-dim">
        {tag ?? 'INFO'}
      </span>
      <p className="text-caption text-hmi-label">{children}</p>
    </div>
  );
}
