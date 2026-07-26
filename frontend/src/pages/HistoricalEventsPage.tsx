import { useMemo } from 'react';
import { useEvents, useOptimalSetpoints, useTimeline } from '../lib/queries';
import { fixed, seconds } from '../lib/format';
import { PEN, eventTag, gradeColor, tagFor } from '../lib/hmi';
import { useAppStore } from '../store/useAppStore';
import { Panel, ScreenHeader, Section } from '../components/ui/Panel';
import { Faceplate } from '../components/ui/Faceplate';
import { Badge } from '../components/ui/Badge';
import { Collapsible } from '../components/ui/Collapsible';
import { DataTable } from '../components/ui/DataTable';
import { ErrorState, Skeleton, SkeletonPanel } from '../components/ui/States';
import { EventsScatterPanel, MiniTrend } from '../components/charts/AnalysisCharts';
import { BasisWeightTrend } from '../components/charts/ProcessCharts';
import type { EventSummary, OperatorAction } from '../lib/types';

const DETAIL_TAGS = [
  { key: 'stock_flow', label: 'Stock Flow', color: PEN.stock, unit: '' },
  { key: 'steam_pressure', label: 'Steam Pressure', color: PEN.steam, unit: ' kPa' },
  { key: 'moisture_pct', label: 'Moisture', color: PEN.moisture, unit: '%' },
  { key: 'filler_flow', label: 'Filler Flow', color: PEN.filler, unit: '' },
] as const;

export function HistoricalEventsPage() {
  const selectedEventId = useAppStore((state) => state.selectedEventId);
  const selectEvent = useAppStore((state) => state.selectEvent);

  const events = useEvents();
  const timeline = useTimeline(selectedEventId);

  const selected = events.data?.events.find((event) => event.event_id === selectedEventId);
  const optimal = useOptimalSetpoints(selected?.grade);

  const transitionSamples = useMemo(
    () => (timeline.data?.samples ?? []).filter((sample) => sample.phase === 'transition'),
    [timeline.data],
  );

  const threshold = events.data?.off_spec_threshold_pct ?? 2.5;

  if (events.isError) {
    return (
      <>
        <Header count={119} />
        <ErrorState
          error={events.error}
          context="the event register"
          onRetry={() => void events.refetch()}
        />
      </>
    );
  }

  if (events.isPending || !events.data) {
    return (
      <>
        <Header count={119} />
        <SkeletonPanel lines={8} label="Population" />
        <SkeletonPanel lines={6} label="Register" />
      </>
    );
  }

  return (
    <>
      <Header count={events.data.events.length} />

      <Section title="Event Population" tag="GC.POP">
        <EventsScatterPanel
          events={events.data.events}
          threshold={threshold}
          selectedEventId={selectedEventId}
          onSelect={selectEvent}
        />
      </Section>

      <Section
        title="Event Register"
        tag="GC.REGISTER"
        description="Sort any column. The marked row is the event loaded on the monitor."
      >
        <DataTable<EventSummary>
          rows={events.data.events}
          rowKey={(row) => row.event_id}
          initialSort={{ key: 'event_id', direction: 'asc' }}
          isHighlighted={(row) => row.event_id === selectedEventId}
          onRowClick={(row) => selectEvent(row.event_id)}
          maxHeight="28rem"
          columns={[
            {
              key: 'event_id',
              header: 'Event tag',
              mono: true,
              render: (row) => eventTag(row.event_id),
              sortValue: (row) => row.event_id,
            },
            {
              key: 'grade',
              header: 'Target grade',
              sortValue: (row) => row.grade,
              render: (row) => (
                <span className="inline-flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5"
                    style={{ backgroundColor: gradeColor(row.grade) }}
                    aria-hidden="true"
                  />
                  {row.grade}
                </span>
              ),
            },
            {
              key: 'max_deviation_pct',
              header: 'Dev.max',
              align: 'right',
              mono: true,
              render: (row) => `${fixed(row.max_deviation_pct, 1)}%`,
              sortValue: (row) => row.max_deviation_pct,
            },
            {
              key: 'time_to_stabilize_sec',
              header: 'Stab',
              align: 'right',
              mono: true,
              render: (row) => seconds(row.time_to_stabilize_sec),
              sortValue: (row) => row.time_to_stabilize_sec,
            },
            {
              key: 'n_operator_actions',
              header: 'Op.act',
              align: 'right',
              mono: true,
              render: (row) => row.n_operator_actions,
              sortValue: (row) => row.n_operator_actions,
            },
            {
              key: 'went_off_spec',
              header: 'Outcome',
              sortValue: (row) => (row.went_off_spec ? 1 : 0),
              render: (row) =>
                row.went_off_spec ? (
                  <Badge variant="critical">Off-spec</Badge>
                ) : (
                  <Badge variant="normal">Held spec</Badge>
                ),
            },
          ]}
        />
      </Section>

      <Section title="Event Detail" tag={eventTag(selectedEventId)}>
        {selected && (
          <div className="grid items-stretch gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Faceplate
              label="Max deviation"
              tag="BW.DEV.MAX"
              value={fixed(selected.max_deviation_pct, 1)}
              unit="%"
              tone={selected.went_off_spec ? 'bad' : 'good'}
              detail={selected.went_off_spec ? 'BREACHED SPEC' : 'WITHIN SPEC'}
            />
            <Faceplate
              label="Stabilization"
              tag="GC.STAB"
              value={selected.time_to_stabilize_sec}
              unit="s"
              detail="TIME TO SETTLE"
            />
            <Faceplate
              label="Operator actions"
              tag="OP.ACT"
              value={selected.n_operator_actions}
              detail="MANUAL INTERVENTIONS"
            />
            <Faceplate
              label="Target grade"
              tag="GRD.TGT"
              value={selected.grade.replace('Grade-', '')}
              detail={selected.grade}
            />
          </div>
        )}

        {timeline.isError ? (
          <ErrorState
            error={timeline.error}
            context="the event timeline"
            onRetry={() => void timeline.refetch()}
          />
        ) : timeline.isPending || !timeline.data ? (
          <Skeleton className="h-72 w-full" />
        ) : (
          <>
            <BasisWeightTrend samples={transitionSamples} threshold={threshold} height={300} />

            <div className="grid gap-3 md:grid-cols-2">
              {DETAIL_TAGS.map((variable) => (
                <MiniTrend
                  key={variable.key}
                  samples={transitionSamples}
                  dataKey={variable.key}
                  color={variable.color}
                  label={variable.label}
                  tag={tagFor(variable.key)}
                  unit={variable.unit || undefined}
                />
              ))}
            </div>

            {timeline.data.operator_actions.length > 0 && (
              <Panel label="Operator action log" tag="OP.LOG" padding="none">
                <DataTable<OperatorAction>
                  rows={timeline.data.operator_actions}
                  rowKey={(row) => `${row.time_since_transition_start_sec}-${row.operator_action}`}
                  initialSort={{ key: 'time', direction: 'asc' }}
                  columns={[
                    {
                      key: 'time',
                      header: 'Elapsed',
                      mono: true,
                      align: 'right',
                      render: (row) => `T+${row.time_since_transition_start_sec}s`,
                      sortValue: (row) => row.time_since_transition_start_sec,
                    },
                    {
                      key: 'action',
                      header: 'Action',
                      render: (row) => row.operator_action,
                      sortValue: (row) => row.operator_action,
                    },
                    {
                      key: 'deviation',
                      header: 'BW.DEV',
                      align: 'right',
                      mono: true,
                      render: (row) => `${fixed(row.basis_weight_deviation_pct, 2)}%`,
                      sortValue: (row) => row.basis_weight_deviation_pct,
                    },
                  ]}
                />
              </Panel>
            )}
          </>
        )}

        <Collapsible
          title={`Optimal setpoints · ${selected?.grade ?? ''}`}
          tag="RCP.OPT"
        >
          {optimal.isError ? (
            <ErrorState
              error={optimal.error}
              context="optimal setpoints"
              onRetry={() => void optimal.refetch()}
            />
          ) : !optimal.data ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              <dl className="divide-y divide-hmi-line border border-hmi-line">
                {optimal.data.setpoints.map((setpoint) => (
                  <div
                    key={setpoint.variable}
                    className="flex items-baseline justify-between gap-4 px-3 py-2"
                  >
                    <dt className="flex items-baseline gap-2">
                      <span className="font-mono text-micro text-hmi-dim">
                        {tagFor(setpoint.variable)}
                      </span>
                      <span className="text-caption uppercase tracking-wide text-hmi-label">
                        {setpoint.label}
                      </span>
                    </dt>
                    <dd className="font-mono text-caption text-hmi-text">
                      {fixed(setpoint.value)}
                      {setpoint.unit ? ` ${setpoint.unit}` : ''}
                    </dd>
                  </div>
                ))}
              </dl>
              <div className="space-y-1.5 font-mono text-micro text-hmi-dim">
                <p>SRC: {optimal.data.source}</p>
                <p>
                  STAB.AVG (FASTEST):{' '}
                  <span className="text-hmi-label">
                    {seconds(optimal.data.avg_stabilize_time_sec)}
                  </span>
                </p>
                <p>
                  BW.SP:{' '}
                  <span className="text-hmi-label">
                    {fixed(optimal.data.basis_weight_target_gsm, 1)} gsm
                  </span>
                </p>
              </div>
            </div>
          )}
        </Collapsible>
      </Section>
    </>
  );
}

function Header({ count }: { count: number }) {
  return (
    <ScreenHeader
      title="Grade Change Event History"
      tag="DISP-03 · QCS.HIST"
      caption={`All ${count} recorded grade changes. Select an event here or in the rail to load it on the monitor.`}
    />
  );
}
