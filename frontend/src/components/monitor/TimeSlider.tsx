import { clock } from '../../lib/format';
import { Spinner } from '../ui/States';

export interface TransportReadout {
  tag: string;
  value: string;
  unit?: string;
  /** Pen colour of the corresponding trend, tying the readout to its trace. */
  color: string;
}

interface TimeSliderProps {
  value: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  /** True while the debounced value is still catching up to the carriage. */
  settling: boolean;
  /** Key values at the current position, printed alongside the transport. */
  readouts?: TransportReadout[];
}

/**
 * Recorder transport: positions the pen along the paper.
 *
 * The carriage follows the pointer on every input event, but the value that
 * drives API calls is debounced upstream, so a full-length drag issues one
 * request rather than one per pixel.
 *
 * The readout strip on the right exists because this panel would otherwise hold
 * one control in a 20px-inset panel and read as a gap in the page. Rather than
 * loosening its padding to fill the space, it carries the tag values at the
 * current position — which is what an operator wants next to a scrubber anyway.
 */
export function TimeSlider({
  value,
  max,
  step,
  onChange,
  settling,
  readouts,
}: TimeSliderProps) {
  const fill = max > 0 ? (value / max) * 100 : 0;
  const stepBy = (delta: number) => onChange(Math.max(0, Math.min(max, value + delta)));

  return (
    <section className="rounded-panel border border-hmi-line bg-hmi-panel">
      <header className="flex items-center justify-between gap-3 border-b border-hmi-line bg-hmi-header px-4 py-2">
        <h3 className="text-tag uppercase text-hmi-label">Transition replay · transport</h3>
        <div className="flex items-center gap-3">
          {settling && <Spinner />}
          <span className="font-mono text-micro text-hmi-dim">GC.ELAP</span>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-4 p-5 xl:flex-nowrap">
        {/* Transport counter. */}
        <div className="min-w-[7.5rem] shrink-0">
          <span className="block font-mono text-micro uppercase text-hmi-dim">Elapsed</span>
          <span className="font-mono text-pv-sm text-signal">{value}s</span>
          <span className="mt-0.5 block font-mono text-micro text-hmi-dim">
            {clock(value)} / {clock(max)}
          </span>
        </div>

        {/* Step controls: one sample interval per press. */}
        <div className="flex shrink-0 gap-1">
          <StepButton label={`−${step}s`} onClick={() => stepBy(-step)} disabled={value <= 0} />
          <StepButton label={`+${step}s`} onClick={() => stepBy(step)} disabled={value >= max} />
        </div>

        {/* Carriage. */}
        <div className="min-w-[15rem] flex-1">
          <label htmlFor="sim-time" className="sr-only">
            Simulation time, seconds since transition start
          </label>
          <input
            id="sim-time"
            type="range"
            min={0}
            max={max}
            step={step}
            value={value}
            onChange={(event) => onChange(Number(event.target.value))}
            className="hmi-slider"
            style={{ '--hmi-slider-fill': `${fill}%` } as React.CSSProperties}
            aria-valuetext={`${value} seconds of ${max}`}
          />
          <div className="flex justify-between font-mono text-micro text-hmi-dim">
            <span>0s</span>
            <span>{Math.round(max / 2)}s</span>
            <span>{max}s</span>
          </div>
        </div>

        {/* Values at the current position. */}
        {readouts && readouts.length > 0 && (
          <dl className="flex shrink-0 divide-x divide-hmi-line border border-hmi-line bg-hmi-inset">
            {readouts.map((readout) => (
              <div key={readout.tag} className="px-3 py-1.5">
                <dt className="flex items-center gap-1.5">
                  <span
                    className="h-0 w-2.5 shrink-0 border-t-2"
                    style={{ borderTopColor: readout.color }}
                    aria-hidden="true"
                  />
                  <span className="font-mono text-micro text-hmi-dim">{readout.tag}</span>
                </dt>
                <dd className="mt-0.5 font-mono text-caption text-hmi-text">
                  {readout.value}
                  {readout.unit && (
                    <span className="ml-0.5 text-hmi-dim">{readout.unit}</span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  );
}

function StepButton({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded-control border border-hmi-bezel bg-hmi-header px-3 py-1.5 font-mono text-micro text-hmi-label transition-colors hover:border-signal hover:text-signal disabled:opacity-40 disabled:hover:border-hmi-bezel disabled:hover:text-hmi-label"
    >
      {label}
    </button>
  );
}
