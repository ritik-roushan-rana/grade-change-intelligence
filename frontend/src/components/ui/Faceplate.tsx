import clsx from 'clsx';
import type { ReactNode } from 'react';
import { TONE_FILL, TONE_TEXT, type Tone } from '../../lib/hmi';

interface FaceplateProps {
  /** Human-readable variable name, uppercase in the header strip. */
  label: string;
  /** Instrument tag code, e.g. `BW.DEV`. */
  tag: string;
  /** The process value. Always monospaced. */
  value: ReactNode;
  /** Engineering unit, set smaller beside the value. */
  unit?: string;
  /** Secondary line: setpoint, deviation from spec, or a qualifier. */
  detail?: ReactNode;
  tone?: Tone;
  /** Range bar: draws current position between min and max with limit ticks. */
  range?: { min: number; max: number; current: number; limit?: number };
  className?: string;
}

/**
 * A single process-variable faceplate: tag code, large monospaced digits, and
 * an optional bar showing where the value sits inside its operating range.
 *
 * This replaces the plain "number in a card" readout. It is the only way a
 * process value is displayed in the app, so every reading on every screen has
 * the same anatomy.
 */
export function Faceplate({
  label,
  tag,
  value,
  unit,
  detail,
  tone = 'neutral',
  range,
  className,
}: FaceplateProps) {
  return (
    <div
      className={clsx(
        'flex h-full flex-col rounded-panel border border-hmi-line bg-hmi-panel',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-hmi-line bg-hmi-header px-3 py-1.5">
        <span className="truncate text-tag uppercase text-hmi-label">{label}</span>
        <span className="shrink-0 font-mono text-micro text-hmi-dim">{tag}</span>
      </div>

      <div className="flex flex-1 flex-col justify-between p-3">
        <p className="flex items-baseline gap-1.5">
          <span className={clsx('font-mono text-pv', TONE_TEXT[tone])}>{value}</span>
          {unit && <span className="font-mono text-caption text-hmi-dim">{unit}</span>}
        </p>

        {range && <RangeBar {...range} tone={tone} />}

        <p className="mt-2 font-mono text-caption text-hmi-label">{detail ?? '\u00a0'}</p>
      </div>
    </div>
  );
}

function RangeBar({
  min,
  max,
  current,
  limit,
  tone,
}: {
  min: number;
  max: number;
  current: number;
  limit?: number;
  tone: Tone;
}) {
  const span = max - min || 1;
  const clamp = (value: number) => Math.max(0, Math.min(100, ((value - min) / span) * 100));
  const position = clamp(current);
  const limitPosition = limit === undefined ? null : clamp(limit);

  return (
    <div className="mt-3">
      <div className="relative h-2 border border-hmi-bezel bg-hmi-inset">
        {/* Filled travel from the low end of the range to the current value. */}
        <div
          className={clsx('absolute inset-y-0 left-0', TONE_FILL[tone])}
          style={{ width: `${position}%` }}
        />
        {/* Operating limit tick, drawn over the fill. */}
        {limitPosition !== null && (
          <div
            className="absolute inset-y-0 w-px bg-alarm-critical"
            style={{ left: `${limitPosition}%` }}
            aria-hidden="true"
          />
        )}
        {/* Carriage mark at the current value. */}
        <div
          className="absolute -top-0.5 h-3 w-0.5 bg-hmi-text"
          style={{ left: `calc(${position}% - 1px)` }}
          aria-hidden="true"
        />
      </div>
      <div className="mt-1 flex justify-between font-mono text-micro text-hmi-dim">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
