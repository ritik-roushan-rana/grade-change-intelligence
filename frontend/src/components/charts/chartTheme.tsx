import type { ReactNode } from 'react';
import clsx from 'clsx';
import { PEN } from '../../lib/hmi';

/**
 * Shared trend-recorder styling.
 *
 * Every chart in the app is framed as a strip-chart recorder: a bezelled panel,
 * a pen legend printed across the top like the pen bar on a real trend
 * recorder, and the trace itself sitting in a recessed graph-paper well.
 */

export const AXIS_PROPS = {
  stroke: PEN.grid,
  tick: { fill: PEN.axis, fontSize: 10, fontFamily: 'IBM Plex Mono, monospace' },
  tickLine: { stroke: PEN.grid },
  axisLine: { stroke: PEN.bezel },
} as const;

/** Solid hairline grid, aligned to axis ticks — engineering paper, not dashes. */
export const GRID_PROPS = {
  stroke: PEN.grid,
  strokeWidth: 1,
  vertical: true,
} as const;

/** Fixed margins so plot areas line up column to column across the screen. */
export const CHART_MARGIN = { top: 10, right: 18, bottom: 4, left: 0 } as const;

export interface PenSpec {
  /** Instrument tag, printed in the legend. */
  tag: string;
  /** Human-readable name. */
  name: string;
  color: string;
  /** Dashed pen = projected/limit trace rather than a measured one. */
  dashed?: boolean;
}

/** Pen bar: swatch, tag code, name. Reads across the top of the recorder. */
function PenLegend({ pens }: { pens: PenSpec[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-hmi-line bg-hmi-panel px-4 py-2">
      {pens.map((pen) => (
        <li key={`${pen.tag}-${pen.name}`} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-0 w-4 shrink-0 border-t-2"
            style={{
              borderTopColor: pen.color,
              borderTopStyle: pen.dashed ? 'dashed' : 'solid',
            }}
          />
          <span className="font-mono text-micro text-hmi-text">{pen.tag}</span>
          <span className="text-micro uppercase text-hmi-dim">{pen.name}</span>
        </li>
      ))}
    </ul>
  );
}

interface TrendPanelProps {
  /** Panel label, uppercase in the header strip. */
  title: string;
  /** Instrument tag or display code for the trend. */
  tag: string;
  pens?: PenSpec[];
  height?: number;
  children: ReactNode;
  /** Footnote under the well, e.g. a projection caveat. */
  caption?: ReactNode;
  aside?: ReactNode;
  className?: string;
}

export function TrendPanel({
  title,
  tag,
  pens,
  height = 300,
  children,
  caption,
  aside,
  className,
}: TrendPanelProps) {
  return (
    <section
      className={clsx(
        'flex h-full flex-col rounded-panel border border-hmi-line bg-hmi-panel',
        className,
      )}
    >
      <header className="flex items-center justify-between gap-3 border-b border-hmi-line bg-hmi-header px-4 py-2">
        <h3 className="text-tag uppercase text-hmi-label">{title}</h3>
        {aside ?? <span className="font-mono text-micro text-hmi-dim">{tag}</span>}
      </header>

      {pens && pens.length > 0 && <PenLegend pens={pens} />}

      {/* Recessed graph-paper well: the recorder's paper.
          Height is explicit and the well is not a flex child — a flex-basis of
          0 here would leave ResponsiveContainer measuring zero and the pens
          would never be drawn. */}
      <div className="hmi-trend-paper w-full border-b border-hmi-line" style={{ height }}>
        {children}
      </div>

      {caption && <p className="px-4 py-2 text-caption text-hmi-dim">{caption}</p>}
    </section>
  );
}

export interface TooltipRow {
  name?: string | number;
  value?: number | string | (number | string)[];
  color?: string;
  dataKey?: string | number;
}

interface HmiTooltipProps {
  active?: boolean;
  label?: string | number;
  payload?: TooltipRow[];
  labelFormatter?: (label: string | number) => string;
  digits?: number;
}

/** Cursor readout, formatted like a console value inspector. */
export function HmiTooltip({
  active,
  label,
  payload,
  labelFormatter,
  digits = 2,
}: HmiTooltipProps) {
  if (!active || !payload?.length) return null;

  const rows = payload.filter(
    (row) => row.value !== undefined && row.value !== null && !Array.isArray(row.value),
  );
  if (rows.length === 0) return null;

  return (
    <div className="rounded-control border border-hmi-bezel bg-hmi-header px-2.5 py-1.5">
      {label !== undefined && (
        <p className="mb-1 border-b border-hmi-line pb-1 font-mono text-micro text-hmi-label">
          {labelFormatter ? labelFormatter(label) : label}
        </p>
      )}
      <ul className="space-y-0.5">
        {rows.map((row, index) => (
          <li
            key={`${row.dataKey}-${index}`}
            className="flex items-center gap-2 font-mono text-caption text-hmi-text"
          >
            <span
              className="h-0 w-3 shrink-0 border-t-2"
              style={{ borderTopColor: row.color }}
              aria-hidden="true"
            />
            <span className="text-hmi-label">{row.name}</span>
            <span className="ml-auto">
              {typeof row.value === 'number' ? row.value.toFixed(digits) : row.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Elapsed-time tick, always in seconds with a unit suffix. */
export const timeTick = (value: number): string => `${value}s`;
export const tooltipTime = (label: string | number) => `T + ${label}s`;

/**
 * Recorder pen tip.
 *
 * Draws a small square nib at the newest sample of a measured trace — the
 * physical pen resting on the paper at the current simulation time. This is the
 * app's single animated element: the nib blinks on a slow two-step cycle, the
 * way a live recorder marks its position.
 */
export function penTip(color: string, lastIndex: number) {
  return (props: unknown) => {
    const { cx, cy, index } = props as { cx: number; cy: number; index: number };
    if (index !== lastIndex || cx === undefined || cy === undefined) {
      // Recharts requires an element from a dot renderer; an empty group keeps
      // the other samples undecorated.
      return <g />;
    }
    return (
      <g className="animate-pen-tip">
        <rect x={cx - 3} y={cy - 3} width={6} height={6} fill={color} />
        <rect
          x={cx - 5}
          y={cy - 5}
          width={10}
          height={10}
          fill="none"
          stroke={color}
          strokeOpacity={0.45}
        />
      </g>
    );
  };
}

/** Vertical scan line marking the present instant on a trend. */
export const NOW_LINE = {
  stroke: PEN.scan,
  strokeWidth: 1,
  strokeDasharray: '2 3',
} as const;
