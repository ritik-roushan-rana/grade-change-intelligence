import clsx from 'clsx';
import type { ReactNode } from 'react';
import { alarmStyle, eventTag } from '../../lib/hmi';
import { clock, fixed, percent, seconds, signed } from '../../lib/format';
import type { PredictionResponse } from '../../lib/types';

interface AlarmBannerProps {
  prediction: PredictionResponse;
  grade: string;
  elapsedSec: number;
  totalSec: number;
}

/**
 * Persistent alarm strip, in the manner of a DCS annunciator: full width, solid
 * alarm-colour fill, reverse-contrast text, with the governing tag and its
 * numbers printed across it in fields divided by hairlines.
 *
 * This is the screen's dominant anchor. It is deliberately *not* animated — the
 * app has exactly one moving element and it is the recorder pen on the trends.
 */
export function AlarmBanner({ prediction, grade, elapsedSec, totalSec }: AlarmBannerProps) {
  const alarm = alarmStyle(prediction.risk_level);
  const threshold = prediction.off_spec_threshold_pct;

  return (
    <section
      className={clsx('rounded-panel border', alarm.fill, alarm.border)}
      role="status"
      aria-live="polite"
      aria-label={`Alarm state ${alarm.label} on grade change ${prediction.event_id}`}
    >
      <div className="hmi-reverse flex flex-wrap items-stretch divide-x divide-black/25">
        {/* Annunciator tile: the state itself. */}
        <div className="flex min-w-[13rem] flex-col justify-center px-5 py-4">
          <span className="font-mono text-micro uppercase opacity-70">Alarm state</span>
          <span className="font-mono text-banner">{alarm.label}</span>
        </div>

        <Field label="Tag" value="QCS-GC.RISK" wide />
        <Field
          label={`Deviation · limit ${threshold}%`}
          value={`${fixed(prediction.current_deviation_pct)}%`}
          note={`${signed(prediction.deviation_vs_spec_pct)}% vs spec`}
          wide
        />
        <Field
          label="Projected 60s"
          value={`${fixed(prediction.projected_deviation_pct)}%`}
          note={
            prediction.projected_deviation_pct > threshold ? 'above limit' : 'within limit'
          }
        />
        <Field label="P(off-spec)" value={percent(prediction.risk_probability, 1)} />
        <Field
          label="Time to breach"
          value={
            prediction.time_to_breach_sec === null
              ? 'N/A'
              : seconds(prediction.time_to_breach_sec)
          }
          note={prediction.time_to_breach_sec === null ? 'not trending to limit' : undefined}
        />
        <Field
          label={prediction.status.label}
          value={prediction.status.value}
          note={prediction.status.detail ?? undefined}
          wide
        />

        {/* Right-hand identification block, as on a real console header. */}
        <div className="ml-auto flex flex-col justify-center px-5 py-4 text-right">
          <span className="font-mono text-micro uppercase opacity-70">
            {eventTag(prediction.event_id)} · {grade}
          </span>
          <span className="font-mono text-pv-xs">
            T+{elapsedSec}s <span className="opacity-70">/ {clock(totalSec)}</span>
          </span>
        </div>
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  note,
  wide = false,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  wide?: boolean;
}) {
  return (
    <div
      className={clsx(
        'flex flex-col justify-center px-5 py-4',
        wide ? 'min-w-[10rem]' : 'min-w-[7.5rem]',
      )}
    >
      <span className="font-mono text-micro uppercase opacity-70">{label}</span>
      <span className="font-mono text-pv-xs">{value}</span>
      {note && <span className="font-mono text-micro opacity-70">{note}</span>}
    </div>
  );
}
