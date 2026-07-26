import { useLocation } from 'react-router-dom';
import clsx from 'clsx';
import { displayFor } from '../../lib/displays';
import { usePrediction } from '../../lib/queries';
import { alarmStyle, eventTag } from '../../lib/hmi';
import { fixed } from '../../lib/format';
import { useAppStore } from '../../store/useAppStore';

/**
 * Persistent console header, spanning the full width above the rail and the
 * display area.
 *
 * Deliberately thin and tag-styled rather than a web navbar: system
 * identification on the left, the active display in the middle, and a compact
 * alarm chip on the right so the governing state of the selected event stays
 * visible on every screen — including after scrolling past the in-page
 * annunciator, or while reading the correlation and history displays.
 */
export function TopBar() {
  const { pathname } = useLocation();
  const display = displayFor(pathname);
  const eventId = useAppStore((state) => state.selectedEventId);
  const simTime = useAppStore((state) => state.simTime);
  const { data: prediction } = usePrediction(eventId, simTime);

  const alarm = prediction?.available ? alarmStyle(prediction.risk_level) : null;

  return (
    <header className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-b border-hmi-bezel bg-hmi-header px-4 py-2">
      {/* System identification. */}
      <div className="flex items-baseline gap-2">
        <span className="h-2.5 w-2.5 shrink-0 bg-signal" aria-hidden="true" />
        <span className="text-tag uppercase text-hmi-text">Honeywell QCS</span>
        <span className="text-tag uppercase text-hmi-label">
          · Grade Change Intelligence
        </span>
      </div>

      <span className="hidden h-4 w-px bg-hmi-bezel sm:block" aria-hidden="true" />

      {/* Active display. */}
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-micro text-hmi-dim">{display.code}</span>
        <span className="text-tag uppercase text-hmi-label">{display.name}</span>
      </div>

      {/* Global alarm chip for the selected event. */}
      <div className="ml-auto flex items-center gap-3">
        <span className="font-mono text-micro text-hmi-dim">
          {eventTag(eventId)} · T+{simTime}s
        </span>
        {alarm && prediction ? (
          <span
            className={clsx(
              'hmi-reverse inline-flex items-center gap-2 rounded-control px-2 py-0.5 font-mono text-micro font-semibold uppercase',
              alarm.fill,
            )}
          >
            {alarm.label}
            <span className="opacity-75">
              BW.DEV {fixed(prediction.current_deviation_pct)}%
            </span>
          </span>
        ) : (
          <span className="rounded-control border border-hmi-bezel px-2 py-0.5 font-mono text-micro uppercase text-hmi-dim">
            No signal
          </span>
        )}
      </div>
    </header>
  );
}
