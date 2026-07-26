import clsx from 'clsx';
import type { ReactNode } from 'react';
import {
  TONE_FILL,
  TONE_TEXT,
  rangePosition,
  type LimitStatus,
  type Tone,
} from '../../lib/hmi';

interface FaceplateProps {
  /** Human-readable variable name, uppercase in the header strip. */
  label: string;
  /** Instrument tag code, e.g. `BW.DEV`. */
  tag: string;
  /** The process value. Always monospaced. */
  value: ReactNode;
  /** Engineering unit, set smaller beside the value. */
  unit?: string;
  /**
   * Severity of this reading. Drives the digit colour, the range needle and the
   * status line, so one variable's condition is stated three consistent ways.
   */
  tone?: Tone;
  /** Colour-coded status line: in range / near limit / out of range. */
  status?: LimitStatus;
  /** Neutral secondary caption, used where there is no limit to check against. */
  detail?: ReactNode;
  /** Range bar: needle positioned at the value between min and max. */
  range?: { min: number; max: number; current: number };
  className?: string;
}

/**
 * A single process-variable faceplate: tag code, large monospaced digits, an
 * optional range bar with a needle at the reading, and a colour-coded status
 * line.
 *
 * The digits take their colour from the reading's own severity rather than a
 * fixed accent, so a grid of faceplates is scannable in a glance: white digits
 * are fine, amber is drifting, red is broken.
 */
export function Faceplate({
  label,
  tag,
  value,
  unit,
  tone = 'neutral',
  status,
  detail,
  range,
  className,
}: FaceplateProps) {
  return (
    <div
      className={clsx(
        'flex h-full flex-col rounded-panel border border-hmi-line bg-hmi-panel',
        // A critical reading gets a coloured edge as well as coloured digits:
        // enough to find it in peripheral vision without adding motion.
        tone === 'bad' && 'border-alarm-critical/60',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-hmi-line bg-hmi-header px-4 py-2">
        <span className="truncate text-tag uppercase text-hmi-label">{label}</span>
        <span className="shrink-0 font-mono text-micro text-hmi-dim">{tag}</span>
      </div>

      <div className="flex flex-1 flex-col justify-between p-5">
        <p className="flex items-baseline gap-1.5">
          <span className={clsx('font-mono text-pv', TONE_TEXT[tone])}>{value}</span>
          {unit && <span className="font-mono text-caption text-hmi-dim">{unit}</span>}
        </p>

        {range && <RangeBar {...range} tone={tone} />}

        {status ? (
          <p
            className={clsx(
              'mt-3 flex items-center gap-1.5 font-mono text-micro uppercase',
              TONE_TEXT[status.tone],
            )}
          >
            <span aria-hidden="true">{status.icon}</span>
            {status.text}
          </p>
        ) : (
          <p
            className={clsx(
              'mt-3 font-mono text-micro uppercase',
              tone === 'neutral' ? 'text-hmi-dim' : TONE_TEXT[tone],
            )}
          >
            {detail ?? '\u00a0'}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * Position indicator, not a magnitude bar.
 *
 * The track spans min to max, and a needle marks where the reading falls inside
 * it. A fill-to-value bar was misleading here: stock flow of 105.85 in a
 * 92.7–106.9 range filled 93% of the track purely because the range does not
 * start at zero, so every variable looked pegged regardless of position.
 */
function RangeBar({
  min,
  max,
  current,
  tone,
}: {
  min: number;
  max: number;
  current: number;
  tone: Tone;
}) {
  const { percent, overflow } = rangePosition(min, max, current);

  return (
    <div className="mt-4">
      <div className="flex items-center gap-1">
        {/* Overflow chevron: the reading is off the low end of the track. */}
        <span
          className={clsx(
            'w-2 shrink-0 text-center font-mono text-micro',
            overflow === 'low' ? TONE_TEXT[tone] : 'text-transparent',
          )}
          aria-hidden="true"
        >
          ◀
        </span>

        <div className="relative h-2.5 flex-1 border border-hmi-bezel bg-hmi-inset">
          {/* The whole track is the in-range band; tint it so "inside" reads as
              the safe zone even before the needle is located. */}
          <div className="absolute inset-0 bg-alarm-normal/10" aria-hidden="true" />
          {/* Range end stops. */}
          <div className="absolute inset-y-0 left-0 w-px bg-hmi-bezel" aria-hidden="true" />
          <div className="absolute inset-y-0 right-0 w-px bg-hmi-bezel" aria-hidden="true" />
          {/* Mid-range reference. */}
          <div
            className="absolute inset-y-1 left-1/2 w-px bg-hmi-line"
            aria-hidden="true"
          />
          {/* Needle at the reading, clamped to the track when outside. */}
          <div
            className={clsx('absolute w-[3px]', TONE_FILL[tone])}
            style={{
              left: `calc(${percent}% - 1.5px)`,
              // Overhangs the track top and bottom so the needle reads as a
              // carriage mark rather than a segment of fill.
              top: '-4px',
              height: 'calc(100% + 8px)',
            }}
            aria-hidden="true"
          />
        </div>

        <span
          className={clsx(
            'w-2 shrink-0 text-center font-mono text-micro',
            overflow === 'high' ? TONE_TEXT[tone] : 'text-transparent',
          )}
          aria-hidden="true"
        >
          ▶
        </span>
      </div>

      <div className="mt-1.5 flex justify-between px-3 font-mono text-micro text-hmi-dim">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
