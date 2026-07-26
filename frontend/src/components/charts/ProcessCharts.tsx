import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
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
  TrendPanel,
  penTip,
  timeTick,
  tooltipTime,
} from './chartTheme';
import { PEN } from '../../lib/hmi';
import type { TimelineSample } from '../../lib/types';

/**
 * Measured process trends. Each is a self-framing recorder panel: pen bar on
 * top, trace on graph paper, nib at the newest sample.
 */

interface TrendProps {
  samples: TimelineSample[];
  threshold: number;
  height?: number;
}

/** BW.PV against BW.SP with the ±spec envelope. */
export function BasisWeightTrend({ samples, threshold, height = 280 }: TrendProps) {
  const factor = threshold / 100;
  const data = samples.map((sample) => ({
    t: sample.time_since_transition_start_sec,
    pv: sample.basis_weight_gsm,
    sp: sample.basis_weight_target_gsm,
    hi: sample.basis_weight_target_gsm * (1 + factor),
    lo: sample.basis_weight_target_gsm * (1 - factor),
  }));
  const last = data.length - 1;

  return (
    <TrendPanel
      title="Basis Weight vs Target"
      tag="TREND / BW.PV"
      height={height}
      pens={[
        { tag: 'BW.PV', name: 'Basis weight gsm', color: PEN.bw },
        { tag: 'BW.SP', name: 'Target', color: PEN.target, dashed: true },
        { tag: 'BW.LIM', name: `±${threshold}% spec`, color: PEN.limit, dashed: true },
      ]}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={CHART_MARGIN}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="t" {...AXIS_PROPS} tickFormatter={timeTick} />
          <YAxis {...AXIS_PROPS} width={48} domain={['auto', 'auto']} />
          <Tooltip content={<HmiTooltip labelFormatter={tooltipTime} />} />
          <Line
            type="linear"
            dataKey="hi"
            name="BW.LIM HI"
            stroke={PEN.limit}
            strokeWidth={1}
            strokeDasharray="3 3"
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="linear"
            dataKey="lo"
            name="BW.LIM LO"
            stroke={PEN.limit}
            strokeWidth={1}
            strokeDasharray="3 3"
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="linear"
            dataKey="sp"
            name="BW.SP"
            stroke={PEN.target}
            strokeWidth={1.25}
            strokeDasharray="5 3"
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="linear"
            dataKey="pv"
            name="BW.PV"
            stroke={PEN.bw}
            strokeWidth={1.75}
            dot={penTip(PEN.bw, last)}
            activeDot={{ r: 3, fill: PEN.bw, stroke: 'none' }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </TrendPanel>
  );
}

/** BW.DEV with the off-spec limit. */
export function DeviationTrend({ samples, threshold, height = 280 }: TrendProps) {
  const data = samples.map((sample) => ({
    t: sample.time_since_transition_start_sec,
    dev: sample.basis_weight_deviation_pct,
  }));
  const last = data.length - 1;

  return (
    <TrendPanel
      title="Deviation From Spec"
      tag="TREND / BW.DEV"
      height={height}
      pens={[
        { tag: 'BW.DEV', name: 'Deviation %', color: PEN.deviation },
        { tag: 'BW.LIM', name: `${threshold}% off-spec`, color: PEN.limit, dashed: true },
      ]}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={CHART_MARGIN}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="t" {...AXIS_PROPS} tickFormatter={timeTick} />
          <YAxis {...AXIS_PROPS} width={48} />
          <Tooltip content={<HmiTooltip labelFormatter={tooltipTime} />} />
          <Area
            type="linear"
            dataKey="dev"
            name="BW.DEV"
            stroke={PEN.deviation}
            strokeWidth={1.75}
            fill={PEN.deviation}
            fillOpacity={0.09}
            dot={penTip(PEN.deviation, last)}
            activeDot={{ r: 3, fill: PEN.deviation, stroke: 'none' }}
            isAnimationActive={false}
          />
          <ReferenceLine
            y={threshold}
            stroke={PEN.limit}
            strokeWidth={1}
            strokeDasharray="3 3"
            label={{
              value: `HI LIMIT ${threshold}%`,
              position: 'insideTopRight',
              fill: PEN.limit,
              fontSize: 9,
              fontFamily: 'IBM Plex Mono, monospace',
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </TrendPanel>
  );
}

/** ST.PV (left) against MOI.PV (right). */
export function SteamMoistureTrend({
  samples,
  height = 240,
}: {
  samples: TimelineSample[];
  height?: number;
}) {
  const data = samples.map((sample) => ({
    t: sample.time_since_transition_start_sec,
    steam: sample.steam_pressure,
    moisture: sample.moisture_pct,
  }));
  const last = data.length - 1;

  return (
    <TrendPanel
      title="Steam Pressure & Moisture"
      tag="TREND / ST-MOI"
      height={height}
      pens={[
        { tag: 'ST.PV', name: 'Steam kPa', color: PEN.steam },
        { tag: 'MOI.PV', name: 'Moisture %', color: PEN.moisture },
      ]}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={CHART_MARGIN}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="t" {...AXIS_PROPS} tickFormatter={timeTick} />
          <YAxis
            yAxisId="steam"
            {...AXIS_PROPS}
            width={48}
            domain={['auto', 'auto']}
            tick={{ ...AXIS_PROPS.tick, fill: PEN.steam }}
          />
          <YAxis
            yAxisId="moisture"
            orientation="right"
            {...AXIS_PROPS}
            width={44}
            domain={['auto', 'auto']}
            tick={{ ...AXIS_PROPS.tick, fill: PEN.moisture }}
          />
          <Tooltip content={<HmiTooltip labelFormatter={tooltipTime} digits={3} />} />
          <Line
            yAxisId="steam"
            type="linear"
            dataKey="steam"
            name="ST.PV"
            stroke={PEN.steam}
            strokeWidth={1.75}
            dot={penTip(PEN.steam, last)}
            isAnimationActive={false}
          />
          <Line
            yAxisId="moisture"
            type="linear"
            dataKey="moisture"
            name="MOI.PV"
            stroke={PEN.moisture}
            strokeWidth={1.75}
            dot={penTip(PEN.moisture, last)}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </TrendPanel>
  );
}

/** SF.PV (left) against MS.PV (right). */
export function StockSpeedTrend({
  samples,
  height = 240,
}: {
  samples: TimelineSample[];
  height?: number;
}) {
  const data = samples.map((sample) => ({
    t: sample.time_since_transition_start_sec,
    stock: sample.stock_flow,
    speed: sample.machine_speed,
  }));
  const last = data.length - 1;

  return (
    <TrendPanel
      title="Stock Flow & Machine Speed"
      tag="TREND / SF-MS"
      height={height}
      pens={[
        { tag: 'SF.PV', name: 'Stock flow', color: PEN.stock },
        { tag: 'MS.PV', name: 'Speed m/min', color: PEN.speed },
      ]}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={CHART_MARGIN}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="t" {...AXIS_PROPS} tickFormatter={timeTick} />
          <YAxis
            yAxisId="stock"
            {...AXIS_PROPS}
            width={48}
            domain={['auto', 'auto']}
            tick={{ ...AXIS_PROPS.tick, fill: PEN.stock }}
          />
          <YAxis
            yAxisId="speed"
            orientation="right"
            {...AXIS_PROPS}
            width={48}
            domain={['auto', 'auto']}
            tick={{ ...AXIS_PROPS.tick, fill: PEN.speed }}
          />
          <Tooltip content={<HmiTooltip labelFormatter={tooltipTime} />} />
          <Line
            yAxisId="stock"
            type="linear"
            dataKey="stock"
            name="SF.PV"
            stroke={PEN.stock}
            strokeWidth={1.75}
            dot={penTip(PEN.stock, last)}
            isAnimationActive={false}
          />
          <Line
            yAxisId="speed"
            type="linear"
            dataKey="speed"
            name="MS.PV"
            stroke={PEN.speed}
            strokeWidth={1.75}
            dot={penTip(PEN.speed, last)}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </TrendPanel>
  );
}
