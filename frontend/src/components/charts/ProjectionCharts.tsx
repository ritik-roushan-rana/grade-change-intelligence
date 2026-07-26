import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AXIS_PROPS,
  CHART_MARGIN,
  GRID_PROPS,
  HmiTooltip,
  NOW_LINE,
  TrendPanel,
  penTip,
  timeTick,
  tooltipTime,
} from './chartTheme';
import { PEN } from '../../lib/hmi';
import type { ProjectionResponse } from '../../lib/types';

interface Merged {
  t: number;
  actualDeviation?: number;
  projectedDeviation?: number;
  actualMoisture?: number;
  projectedMoisture?: number;
  actualSteam?: number;
  projectedSteam?: number;
}

/**
 * Stitch measured history and forward extrapolation into one x-ordered series.
 *
 * The NOW sample is written into both halves so the projected trace starts
 * exactly where the measured pen stops, with no gap across the scan line.
 */
function mergeSeries(projection: ProjectionResponse): Merged[] {
  const rows = new Map<number, Merged>();

  for (const point of projection.actual) {
    rows.set(point.t, {
      t: point.t,
      actualDeviation: point.deviation_pct,
      actualMoisture: point.moisture_pct,
      actualSteam: point.steam_pressure,
    });
  }

  const now = projection.now;
  if (now) {
    rows.set(now.t, {
      ...(rows.get(now.t) ?? { t: now.t }),
      projectedDeviation: now.deviation_pct,
      projectedMoisture: now.moisture_pct,
      projectedSteam: now.steam_pressure,
    });
  }

  for (const point of projection.projected) {
    rows.set(point.t, {
      ...(rows.get(point.t) ?? { t: point.t }),
      projectedDeviation: point.deviation_pct,
      projectedMoisture: point.moisture_pct,
      projectedSteam: point.steam_pressure,
    });
  }

  return [...rows.values()].sort((a, b) => a.t - b.t);
}

/**
 * The NOW scan line: where the recorder pen currently rests. Everything left of
 * it is measured paper, everything right is extrapolation.
 */
function nowMarker(t: number) {
  return (
    <ReferenceLine
      x={t}
      {...NOW_LINE}
      label={{
        value: 'NOW',
        position: 'top',
        fill: PEN.scan,
        fontSize: 9,
        fontFamily: 'IBM Plex Mono, monospace',
      }}
    />
  );
}

/** Measured deviation, forward projection, and the off-spec limit. */
export function DeviationProjectionTrend({
  projection,
  height = 280,
}: {
  projection: ProjectionResponse;
  height?: number;
}) {
  const data = mergeSeries(projection);
  const lastActual = data.reduce(
    (found, row, index) => (row.actualDeviation !== undefined ? index : found),
    -1,
  );

  return (
    <TrendPanel
      title="Basis Weight Deviation — Trend Projection"
      tag="TREND / BW.DEV.PROJ"
      height={height}
      pens={[
        { tag: 'BW.DEV', name: 'Measured', color: PEN.deviation },
        { tag: 'BW.PROJ', name: 'Projected', color: PEN.projection, dashed: true },
        {
          tag: 'BW.LIM',
          name: `${projection.off_spec_threshold_pct}% off-spec`,
          color: PEN.limit,
          dashed: true,
        },
      ]}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={CHART_MARGIN}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis
            dataKey="t"
            type="number"
            domain={['dataMin', 'dataMax']}
            {...AXIS_PROPS}
            tickFormatter={timeTick}
          />
          <YAxis {...AXIS_PROPS} width={48} />
          <Tooltip content={<HmiTooltip labelFormatter={tooltipTime} />} />
          <Area
            type="linear"
            dataKey="projectedDeviation"
            name="BW.PROJ"
            stroke={PEN.projection}
            strokeWidth={1.5}
            strokeDasharray="5 3"
            fill={PEN.projection}
            fillOpacity={0.07}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            type="linear"
            dataKey="actualDeviation"
            name="BW.DEV"
            stroke={PEN.deviation}
            strokeWidth={1.75}
            dot={penTip(PEN.deviation, lastActual)}
            isAnimationActive={false}
          />
          <ReferenceLine
            y={projection.off_spec_threshold_pct}
            stroke={PEN.limit}
            strokeWidth={1}
            strokeDasharray="3 3"
            label={{
              value: `HI LIMIT ${projection.off_spec_threshold_pct}%`,
              position: 'insideTopRight',
              fill: PEN.limit,
              fontSize: 9,
              fontFamily: 'IBM Plex Mono, monospace',
            }}
          />
          {projection.now && nowMarker(projection.now.t)}
        </ComposedChart>
      </ResponsiveContainer>
    </TrendPanel>
  );
}

/** The correlated pair: MOI.PV (left) and ST.PV (right), measured + projected. */
export function CorrelatedProjectionTrend({
  projection,
  height = 280,
}: {
  projection: ProjectionResponse;
  height?: number;
}) {
  const data = mergeSeries(projection);
  const lastMoisture = data.reduce(
    (found, row, index) => (row.actualMoisture !== undefined ? index : found),
    -1,
  );
  const lastSteam = data.reduce(
    (found, row, index) => (row.actualSteam !== undefined ? index : found),
    -1,
  );

  return (
    <TrendPanel
      title="Correlated Parameters — Trend Projection"
      tag="TREND / MOI-ST.PROJ"
      height={height}
      pens={[
        { tag: 'MOI.PV', name: 'Moisture %', color: PEN.moisture },
        { tag: 'MOI.PROJ', name: 'Projected', color: PEN.moisture, dashed: true },
        { tag: 'ST.PV', name: 'Steam kPa', color: PEN.steam },
        { tag: 'ST.PROJ', name: 'Projected', color: PEN.steam, dashed: true },
      ]}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={CHART_MARGIN}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis
            dataKey="t"
            type="number"
            domain={['dataMin', 'dataMax']}
            {...AXIS_PROPS}
            tickFormatter={timeTick}
          />
          <YAxis
            yAxisId="moisture"
            {...AXIS_PROPS}
            width={46}
            domain={['auto', 'auto']}
            tick={{ ...AXIS_PROPS.tick, fill: PEN.moisture }}
          />
          <YAxis
            yAxisId="steam"
            orientation="right"
            {...AXIS_PROPS}
            width={46}
            domain={['auto', 'auto']}
            tick={{ ...AXIS_PROPS.tick, fill: PEN.steam }}
          />
          <Tooltip content={<HmiTooltip labelFormatter={tooltipTime} digits={3} />} />
          <Line
            yAxisId="moisture"
            type="linear"
            dataKey="actualMoisture"
            name="MOI.PV"
            stroke={PEN.moisture}
            strokeWidth={1.75}
            dot={penTip(PEN.moisture, lastMoisture)}
            isAnimationActive={false}
          />
          <Line
            yAxisId="moisture"
            type="linear"
            dataKey="projectedMoisture"
            name="MOI.PROJ"
            stroke={PEN.moisture}
            strokeWidth={1.25}
            strokeDasharray="5 3"
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            yAxisId="steam"
            type="linear"
            dataKey="actualSteam"
            name="ST.PV"
            stroke={PEN.steam}
            strokeWidth={1.75}
            dot={penTip(PEN.steam, lastSteam)}
            isAnimationActive={false}
          />
          <Line
            yAxisId="steam"
            type="linear"
            dataKey="projectedSteam"
            name="ST.PROJ"
            stroke={PEN.steam}
            strokeWidth={1.25}
            strokeDasharray="5 3"
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          {projection.now && nowMarker(projection.now.t)}
        </ComposedChart>
      </ResponsiveContainer>
    </TrendPanel>
  );
}
