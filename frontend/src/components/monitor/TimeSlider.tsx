import { clock } from '../../lib/format';
import { Spinner } from '../ui/States';

interface TimeSliderProps {
  value: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  /** True while the debounced value is still catching up to the carriage. */
  settling: boolean;
}

/**
 * Recorder transport: positions the pen along the paper.
 *
 * The carriage follows the pointer on every input event, but the value that
 * drives API calls is debounced upstream, so a full-length drag issues one
 * request rather than one per pixel.
 */
export function TimeSlider({ value, max, step, onChange, settling }: TimeSliderProps) {
  const fill = max > 0 ? (value / max) * 100 : 0;
  const stepBy = (delta: number) => onChange(Math.max(0, Math.min(max, value + delta)));

  return (
    <section className="rounded-panel border border-hmi-line bg-hmi-panel">
      <header className="flex items-center justify-between gap-3 border-b border-hmi-line bg-hmi-header px-3 py-1.5">
        <h3 className="text-tag uppercase text-hmi-label">Transition replay · transport</h3>
        <div className="flex items-center gap-3">
          {settling && <Spinner />}
          <span className="font-mono text-micro text-hmi-dim">GC.ELAP</span>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-4 px-3 py-3">
        {/* Elapsed readout, sized like a transport counter. */}
        <div className="min-w-[8.5rem]">
          <span className="block font-mono text-micro uppercase text-hmi-dim">Elapsed</span>
          <span className="font-mono text-pv-sm text-signal">{value}s</span>
          <span className="ml-2 font-mono text-caption text-hmi-dim">
            {clock(value)} / {clock(max)}
          </span>
        </div>

        {/* Step controls: one sample interval per press. */}
        <div className="flex gap-1">
          <StepButton label={`−${step}s`} onClick={() => stepBy(-step)} disabled={value <= 0} />
          <StepButton label={`+${step}s`} onClick={() => stepBy(step)} disabled={value >= max} />
        </div>

        <div className="min-w-[16rem] flex-1">
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
      className="rounded-control border border-hmi-bezel bg-hmi-header px-2 py-1 font-mono text-micro text-hmi-label transition-colors hover:border-signal hover:text-signal disabled:opacity-40 disabled:hover:border-hmi-bezel disabled:hover:text-hmi-label"
    >
      {label}
    </button>
  );
}
