import { NavLink } from 'react-router-dom';
import clsx from 'clsx';
import { useEvents, useModelInfo } from '../../lib/queries';
import { DEMO_PRESETS, useAppStore } from '../../store/useAppStore';
import { fixed, percent, seconds } from '../../lib/format';
import { eventTag } from '../../lib/hmi';
import { Skeleton } from '../ui/States';

/** Display directory, numbered the way console screens are. */
const DISPLAYS = [
  { to: '/', code: 'DISP-01', label: 'Live Monitor' },
  { to: '/correlations', code: 'DISP-02', label: 'Correlations' },
  { to: '/events', code: 'DISP-03', label: 'Event History' },
  { to: '/feedback', code: 'DISP-04', label: 'Feedback Log' },
] as const;

/**
 * Console navigation rail. Hairline-divided blocks, uppercase labels, every
 * value monospaced — the left-hand column of an operator station rather than a
 * web sidebar.
 */
export function Sidebar() {
  const { data, isPending, isError } = useEvents();
  const { data: modelInfo } = useModelInfo();
  const selectedEventId = useAppStore((state) => state.selectedEventId);
  const selectEvent = useAppStore((state) => state.selectEvent);

  const events = data?.events ?? [];
  const selected = events.find((event) => event.event_id === selectedEventId);

  return (
    <aside className="flex h-full w-full flex-col overflow-y-auto border-r border-hmi-bezel bg-hmi-panel lg:w-[268px] lg:shrink-0">
      {/* Station identification. */}
      <div className="border-b border-hmi-bezel bg-hmi-header px-4 py-3">
        <p className="font-mono text-micro uppercase text-signal">Honeywell QCS</p>
        <h1 className="mt-1 text-panel uppercase leading-tight text-hmi-text">
          Grade Change
          <br />
          Intelligence
        </h1>
        <p className="mt-1.5 font-mono text-micro text-hmi-dim">PM-01 · MD CONTROL</p>
      </div>

      {/* Display directory. */}
      <nav aria-label="Displays" className="border-b border-hmi-line">
        {DISPLAYS.map((display) => (
          <NavLink
            key={display.to}
            to={display.to}
            end={display.to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-baseline gap-2 border-l-2 px-4 py-2 transition-colors',
                isActive
                  ? 'border-l-signal bg-signal-fill text-hmi-text'
                  : 'border-l-transparent text-hmi-label hover:bg-hmi-header hover:text-hmi-text',
              )
            }
          >
            <span className="font-mono text-micro text-hmi-dim">{display.code}</span>
            <span className="text-caption uppercase tracking-wide">{display.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Scenario presets. */}
      <div className="border-b border-hmi-line px-4 py-3">
        <p className="text-tag uppercase text-hmi-label">Scenario presets</p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          {(['moderate', 'extreme'] as const).map((key) => {
            const preset = DEMO_PRESETS[key];
            const active = selectedEventId === preset.eventId;
            return (
              <button
                key={key}
                type="button"
                title={preset.hint}
                onClick={() => selectEvent(preset.eventId)}
                className={clsx(
                  'rounded-control border px-2 py-1.5 text-left transition-colors',
                  active
                    ? 'border-signal bg-signal-fill text-signal'
                    : 'border-hmi-bezel bg-hmi-header text-hmi-label hover:border-signal/60 hover:text-hmi-text',
                )}
              >
                <span className="block text-micro uppercase">{preset.label}</span>
                <span className="block font-mono text-micro text-hmi-dim">
                  {eventTag(preset.eventId)}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Event selection + summary. */}
      <div className="border-b border-hmi-line px-4 py-3">
        <label htmlFor="event-select" className="block text-tag uppercase text-hmi-label">
          Grade change event
        </label>
        {isPending ? (
          <Skeleton className="mt-2 h-8 w-full" />
        ) : isError ? (
          <p className="mt-2 font-mono text-micro text-alarm-critical">EVENT LIST UNAVAILABLE</p>
        ) : (
          <select
            id="event-select"
            value={selectedEventId}
            onChange={(event) => selectEvent(Number(event.target.value))}
            className="mt-2 w-full rounded-control border border-hmi-bezel bg-hmi-inset px-2 py-1.5 font-mono text-caption text-hmi-text transition-colors hover:border-signal/60"
          >
            {events.map((event) => (
              <option key={event.event_id} value={event.event_id}>
                {eventTag(event.event_id)} — {event.grade}
              </option>
            ))}
          </select>
        )}

        {selected && (
          <dl className="mt-3 space-y-1 border-t border-hmi-line pt-2">
            <Row label="Grade" value={selected.grade} />
            <Row label="Dev.max" value={`${fixed(selected.max_deviation_pct, 1)}%`} />
            <Row label="Stab" value={seconds(selected.time_to_stabilize_sec)} />
            <Row label="Op.act" value={String(selected.n_operator_actions)} />
          </dl>
        )}
      </div>

      {/* Model provenance. */}
      <div className="mt-auto px-4 py-3">
        <p className="text-tag uppercase text-hmi-label">Model · held-out test</p>
        {modelInfo ? (
          <dl className="mt-2 space-y-1">
            <Row label="Accuracy" value={percent(modelInfo.evaluation.test_accuracy, 1)} />
            <Row label="F1" value={percent(modelInfo.evaluation.test_f1, 1)} />
            <Row label="R²" value={fixed(modelInfo.evaluation.test_r2, 3)} />
          </dl>
        ) : (
          <Skeleton className="mt-2 h-12 w-full" />
        )}
        <p className="mt-3 border-t border-hmi-line pt-2 font-mono text-micro leading-relaxed text-hmi-dim">
          RF + GB · KNN RECOVERY
          <br />
          HACKATHON 2026
        </p>
      </div>
    </aside>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="font-mono text-micro uppercase text-hmi-dim">{label}</dt>
      <dd className="font-mono text-caption text-hmi-text">{value}</dd>
    </div>
  );
}
