import { useEffect, useMemo, useRef, useState } from 'react';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useDelayedFlag } from '../hooks/useDelayedFlag';
import {
  usePrediction,
  useProjection,
  useRecipeLimits,
  useRecommendations,
  useTimeline,
} from '../lib/queries';
import { fixed, signed } from '../lib/format';
import { alarmStyle, eventTag, tagFor } from '../lib/hmi';
import { DEFAULT_SIM_TIME, SIM_TIME_STEP, useAppStore } from '../store/useAppStore';
import { Panel, ScreenHeader, Section } from '../components/ui/Panel';
import { Faceplate } from '../components/ui/Faceplate';
import { Collapsible } from '../components/ui/Collapsible';
import { DataTable } from '../components/ui/DataTable';
import { Badge } from '../components/ui/Badge';
import { ErrorState, Notice, Skeleton, SkeletonPanel, Spinner } from '../components/ui/States';
import {
  BasisWeightTrend,
  DeviationTrend,
  SteamMoistureTrend,
  StockSpeedTrend,
} from '../components/charts/ProcessCharts';
import {
  CorrelatedProjectionTrend,
  DeviationProjectionTrend,
} from '../components/charts/ProjectionCharts';
import { TimeSlider } from '../components/monitor/TimeSlider';
import { AlarmBanner } from '../components/monitor/AlarmBanner';
import { RecommendationsPanel } from '../components/monitor/RecommendationsPanel';
import type { RecipeLimitVariable } from '../lib/types';

export function LiveMonitorPage() {
  const eventId = useAppStore((state) => state.selectedEventId);
  const storedSimTime = useAppStore((state) => state.simTime);
  const setSimTime = useAppStore((state) => state.setSimTime);

  // The carriage position updates on every input event; `simTime` is the settled
  // value queries key off, so a drag fires one request, not hundreds.
  const [draft, setDraft] = useState(storedSimTime);
  const simTime = useDebouncedValue(draft, 150);

  const timeline = useTimeline(eventId);
  const maxTime = timeline.data?.max_time_sec ?? 0;
  const threshold = timeline.data?.off_spec_threshold_pct ?? 2.5;

  // Rewind on event change, clamp if the new event is shorter. Keyed on a ref so
  // navigating away and back preserves the operator's position.
  const lastEventRef = useRef(eventId);
  useEffect(() => {
    if (lastEventRef.current !== eventId) {
      lastEventRef.current = eventId;
      setDraft(maxTime > 0 ? Math.min(DEFAULT_SIM_TIME, maxTime) : DEFAULT_SIM_TIME);
    } else if (maxTime > 0 && draft > maxTime) {
      setDraft(maxTime);
    }
  }, [eventId, maxTime, draft]);

  useEffect(() => {
    setSimTime(simTime);
  }, [simTime, setSimTime]);

  const prediction = usePrediction(eventId, simTime);
  const projection = useProjection(eventId, simTime);
  const recommendations = useRecommendations(eventId, simTime);
  const grade = prediction.data?.grade;
  const recipeLimits = useRecipeLimits(grade, eventId, simTime);

  // Everything the operator has seen so far: transition samples up to now.
  const elapsedSamples = useMemo(() => {
    const samples = timeline.data?.samples ?? [];
    return samples.filter(
      (sample) =>
        sample.phase === 'transition' && sample.time_since_transition_start_sec <= simTime,
    );
  }, [timeline.data, simTime]);

  const settling = draft !== simTime;
  const refreshing =
    prediction.isFetching || projection.isFetching || recommendations.isFetching;
  const showActivity = useDelayedFlag(refreshing, 300);

  if (timeline.isError) {
    return (
      <>
        <Header eventId={eventId} />
        <ErrorState
          error={timeline.error}
          context="the process timeline"
          onRetry={() => void timeline.refetch()}
        />
      </>
    );
  }

  if (timeline.isPending || !timeline.data) {
    return (
      <>
        <Header eventId={eventId} />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-16 w-full" />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SkeletonPanel lines={2} label="Faceplate" />
          <SkeletonPanel lines={2} label="Faceplate" />
          <SkeletonPanel lines={2} label="Faceplate" />
          <SkeletonPanel lines={2} label="Faceplate" />
        </div>
      </>
    );
  }

  const alarm = prediction.data?.available ? alarmStyle(prediction.data.risk_level) : null;

  return (
    <>
      <Header
        eventId={eventId}
        aside={showActivity ? <Spinner label="Scoring" /> : undefined}
      />

      {/* ── Alarm annunciator ── */}
      {prediction.isError ? (
        <ErrorState
          error={prediction.error}
          context="the risk prediction"
          onRetry={() => void prediction.refetch()}
        />
      ) : !prediction.data ? (
        <Skeleton className="h-20 w-full" />
      ) : !prediction.data.available ? (
        <Notice tag="HOLD">{prediction.data.message}</Notice>
      ) : (
        <AlarmBanner
          prediction={prediction.data}
          grade={prediction.data.grade}
          elapsedSec={simTime}
          totalSec={maxTime}
        />
      )}

      {/* ── Transport ── */}
      <TimeSlider
        value={draft}
        max={maxTime}
        step={SIM_TIME_STEP}
        onChange={setDraft}
        settling={settling}
      />

      {/* ── Prediction narrative ── */}
      {prediction.data?.available && (
        <Panel
          label="Prediction basis"
          tag="QCS-GC.EXPL"
          className={alarm ? `border-l-2 ${alarm.border}` : undefined}
        >
          <p className="text-body text-hmi-text">{prediction.data.explanation}</p>
          <p className="mt-2 font-mono text-micro text-hmi-dim">
            SRC: {prediction.data.source}
          </p>
        </Panel>
      )}

      {/* ── Faceplate strip: live process variables against operating range ── */}
      <Section
        title="Process Faceplates"
        tag="PV.GROUP"
        description={
          recipeLimits.data?.annotated
            ? 'Each faceplate shows the measured value with its position inside the grade recipe range. The red tick marks the nearest operating limit.'
            : undefined
        }
      >
        {recipeLimits.isError ? (
          <ErrorState
            error={recipeLimits.error}
            context="process faceplates"
            onRetry={() => void recipeLimits.refetch()}
          />
        ) : !recipeLimits.data ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <SkeletonPanel lines={2} label="Faceplate" />
            <SkeletonPanel lines={2} label="Faceplate" />
            <SkeletonPanel lines={2} label="Faceplate" />
            <SkeletonPanel lines={2} label="Faceplate" />
          </div>
        ) : (
          <div className="grid items-stretch gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {recipeLimits.data.variables.map((variable) => (
              <Faceplate
                key={variable.variable}
                label={variable.label}
                tag={tagFor(variable.variable)}
                value={fixed(variable.current_value)}
                unit={variable.unit}
                tone={variable.within_limits === false ? 'warn' : 'neutral'}
                range={
                  variable.current_value === null
                    ? undefined
                    : {
                        min: variable.min,
                        max: variable.max,
                        current: variable.current_value,
                        limit: variable.current_value > variable.max ? variable.max : variable.min,
                      }
                }
                detail={
                  variable.within_limits === false
                    ? `OUT OF RANGE ${signed(variable.violation)}`
                    : 'IN RANGE'
                }
              />
            ))}
          </div>
        )}
      </Section>

      {/* ── Measured trends ── */}
      <Section
        title="Process Trends"
        tag="TREND.GROUP"
        description={`Measured data to T+${simTime}s of a ${maxTime}s transition. The pen nib marks the present sample.`}
      >
        <div className="grid gap-3 xl:grid-cols-2">
          <BasisWeightTrend samples={elapsedSamples} threshold={threshold} />
          <DeviationTrend samples={elapsedSamples} threshold={threshold} />
        </div>

        <Collapsible title="Secondary process variables" tag="TREND / AUX">
          <div className="grid gap-3 xl:grid-cols-2">
            <SteamMoistureTrend samples={elapsedSamples} />
            <StockSpeedTrend samples={elapsedSamples} />
          </div>
        </Collapsible>
      </Section>

      {/* ── Future state ── */}
      <Section
        title="Future-State Projection"
        tag="PROJ.GROUP"
        description="Where the transition is heading if the present rate of change holds."
      >
        {projection.isError ? (
          <ErrorState
            error={projection.error}
            context="the projection"
            onRetry={() => void projection.refetch()}
          />
        ) : !projection.data ? (
          <div className="grid gap-3 xl:grid-cols-2">
            <SkeletonPanel lines={6} label="Trend" />
            <SkeletonPanel lines={6} label="Trend" />
          </div>
        ) : !projection.data.available ? (
          <Notice tag="NO DATA">{projection.data.message}</Notice>
        ) : (
          <>
            <div className="grid gap-3 xl:grid-cols-2">
              <DeviationProjectionTrend projection={projection.data} />
              <CorrelatedProjectionTrend projection={projection.data} />
            </div>

            {projection.data.rates && (
              <div className="grid items-stretch gap-3 sm:grid-cols-3">
                <Faceplate
                  label="Deviation rate / 60s"
                  tag="BW.ROC"
                  value={signed(projection.data.rates.deviation_pct_per_60s)}
                  unit="%"
                  tone={projection.data.rates.deviation_pct_per_60s > 0 ? 'bad' : 'good'}
                  detail={
                    projection.data.rates.deviation_pct_per_60s > 0 ? 'WORSENING' : 'IMPROVING'
                  }
                />
                <Faceplate
                  label="Moisture rate / 60s"
                  tag="MOI.ROC"
                  value={signed(projection.data.rates.moisture_pct_per_60s, 3)}
                  unit="%"
                  detail="TREND SLOPE"
                />
                <Faceplate
                  label="Steam rate / 60s"
                  tag="ST.ROC"
                  value={signed(projection.data.rates.steam_kpa_per_60s)}
                  unit="kPa"
                  detail="TREND SLOPE"
                />
              </div>
            )}

            <p className="border-l-2 border-hmi-bezel pl-3 text-caption text-hmi-dim">
              {projection.data.caveat}
            </p>
          </>
        )}
      </Section>

      {/* ── Recipe limits (tabular audit view) ── */}
      <Collapsible
        title={`Recipe limits${grade ? ` · ${grade}` : ''}`}
        tag="RCP.LIMITS"
      >
        {recipeLimits.isError ? (
          <ErrorState
            error={recipeLimits.error}
            context="recipe limits"
            onRetry={() => void recipeLimits.refetch()}
          />
        ) : !recipeLimits.data ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <>
            <DataTable<RecipeLimitVariable>
              rows={recipeLimits.data.variables}
              rowKey={(row) => row.variable}
              columns={[
                {
                  key: 'tag',
                  header: 'Tag',
                  mono: true,
                  render: (row) => tagFor(row.variable),
                  sortValue: (row) => tagFor(row.variable),
                },
                {
                  key: 'variable',
                  header: 'Variable',
                  render: (row) => row.label,
                  sortValue: (row) => row.label,
                },
                {
                  key: 'min',
                  header: 'Min',
                  align: 'right',
                  mono: true,
                  render: (row) => fixed(row.min),
                  sortValue: (row) => row.min,
                },
                {
                  key: 'current',
                  header: 'Current',
                  align: 'right',
                  mono: true,
                  render: (row) => fixed(row.current_value),
                  sortValue: (row) => row.current_value ?? 0,
                },
                {
                  key: 'max',
                  header: 'Max',
                  align: 'right',
                  mono: true,
                  render: (row) => fixed(row.max),
                  sortValue: (row) => row.max,
                },
                {
                  key: 'status',
                  header: 'Status',
                  render: (row) =>
                    row.within_limits === null ? (
                      <span className="font-mono text-hmi-dim">—</span>
                    ) : row.within_limits ? (
                      <Badge variant="normal">✓ OK</Badge>
                    ) : (
                      <Badge variant="medium">⚠ {signed(row.violation)}</Badge>
                    ),
                },
              ]}
            />
            <p className="mt-3 font-mono text-micro text-hmi-dim">
              SRC: {recipeLimits.data.source}
            </p>
          </>
        )}
      </Collapsible>

      {/* ── Corrective actions ── */}
      <RecommendationsPanel
        eventId={eventId}
        t={simTime}
        data={recommendations.data}
        isPending={recommendations.isPending}
        error={recommendations.error}
        onRetry={() => void recommendations.refetch()}
      />

      {/* ── Model attribution ── */}
      {prediction.data?.available && prediction.data.contributing_factors.length > 0 && (
        <Collapsible title="Contributing factors · feature importance" tag="MDL.ATTR">
          <DataTable
            rows={prediction.data.contributing_factors}
            rowKey={(row) => row.variable}
            columns={[
              {
                key: 'tag',
                header: 'Tag',
                mono: true,
                render: (row) => tagFor(row.variable),
                sortValue: (row) => tagFor(row.variable),
              },
              {
                key: 'variable',
                header: 'Variable',
                render: (row) => row.label,
                sortValue: (row) => row.label,
              },
              {
                key: 'importance',
                header: 'Importance',
                align: 'right',
                mono: true,
                render: (row) => fixed(row.importance, 3),
                sortValue: (row) => row.importance,
              },
              {
                key: 'value',
                header: 'Current value',
                align: 'right',
                mono: true,
                render: (row) => fixed(row.current_value, 3),
                sortValue: (row) => row.current_value,
              },
            ]}
            initialSort={{ key: 'importance', direction: 'desc' }}
          />
        </Collapsible>
      )}
    </>
  );
}

function Header({ eventId, aside }: { eventId: number; aside?: React.ReactNode }) {
  return (
    <ScreenHeader
      title="Live Grade Change Monitor"
      tag={`DISP-01 · ${eventTag(eventId)}`}
      caption="In-progress grade change with model risk prediction and corrective setpoint guidance."
      aside={aside}
    />
  );
}
