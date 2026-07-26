import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
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
import { ALARM, PEN, eventTag, gradeColor } from '../../lib/hmi';
import { fixed } from '../../lib/format';
import type { EventSummary, GradePairDetail, TimelineSample } from '../../lib/types';

/**
 * Grade-pair difficulty. Bar length is average stabilization time; fill steps
 * through the alarm scale by average deviation, so "worse" looks the same here
 * as it does on the alarm banner.
 */
export function GradePairTrend({ rows, height = 300 }: { rows: GradePairDetail[]; height?: number }) {
  const data = [...rows].sort((a, b) => b.avg_stabilize - a.avg_stabilize);
  const maxDeviation = Math.max(...data.map((row) => row.avg_deviation), 1);

  const fillFor = (deviation: number) => {
    const ratio = deviation / maxDeviation;
    if (ratio > 0.9) return ALARM.critical.hex;
    if (ratio > 0.75) return ALARM.high.hex;
    if (ratio > 0.6) return ALARM.medium.hex;
    return ALARM.low.hex;
  };

  return (
    <TrendPanel
      title="Grade-Pair Difficulty — Avg Stabilization"
      tag="CHART / GC.PAIR"
      height={height}
      pens={[
        { tag: 'CRIT', name: 'Highest avg deviation', color: ALARM.critical.hex },
        { tag: 'HIGH', name: 'Elevated', color: ALARM.high.hex },
        { tag: 'CAUT', name: 'Moderate', color: ALARM.medium.hex },
        { tag: 'NORM', name: 'Lowest', color: ALARM.low.hex },
      ]}
      caption="Bar length is mean time to stabilize; fill steps through the alarm scale by mean maximum deviation for that transition."
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ ...CHART_MARGIN, bottom: 56 }}>
          <CartesianGrid {...GRID_PROPS} vertical={false} />
          <XAxis
            dataKey="grade_pair"
            {...AXIS_PROPS}
            interval={0}
            angle={-30}
            textAnchor="end"
            height={64}
            tick={{ ...AXIS_PROPS.tick, fontSize: 9 }}
          />
          <YAxis {...AXIS_PROPS} width={52} />
          <Tooltip content={<HmiTooltip labelFormatter={(label) => String(label)} digits={1} />} />
          <Bar dataKey="avg_stabilize" name="STAB.AVG" fillOpacity={0.85}>
            {data.map((row) => (
              <Cell key={row.grade_pair} fill={fillFor(row.avg_deviation)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </TrendPanel>
  );
}

/**
 * All events: deviation against stabilization time, one plot per grade. Marker
 * size is the operator-intervention count; the selected event is ringed.
 */
export function EventsScatterPanel({
  events,
  threshold,
  selectedEventId,
  onSelect,
  height = 400,
}: {
  events: EventSummary[];
  threshold: number;
  selectedEventId: number;
  onSelect: (eventId: number) => void;
  height?: number;
}) {
  const grades = [...new Set(events.map((event) => event.grade))].sort();

  return (
    <TrendPanel
      title="All Events — Deviation vs Stabilization"
      tag="CHART / GC.POP"
      height={height}
      pens={grades.map((grade) => ({
        tag: grade.replace('Grade-', '').toUpperCase(),
        name: grade,
        color: gradeColor(grade),
      }))}
      caption="Marker size is the number of operator interventions. Select a marker to load that event."
    >
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ ...CHART_MARGIN, bottom: 16 }}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis
            type="number"
            dataKey="time_to_stabilize_sec"
            name="STAB"
            {...AXIS_PROPS}
            tickFormatter={timeTick}
          />
          <YAxis
            type="number"
            dataKey="max_deviation_pct"
            name="DEV.MAX"
            {...AXIS_PROPS}
            width={52}
          />
          <ZAxis type="number" dataKey="n_operator_actions" range={[40, 320]} name="OP.ACT" />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const event = payload[0].payload as EventSummary;
              return (
                <div className="rounded-control border border-hmi-bezel bg-hmi-header px-2.5 py-1.5">
                  <p className="border-b border-hmi-line pb-1 font-mono text-micro text-hmi-text">
                    {eventTag(event.event_id)} · {event.grade}
                  </p>
                  <ul className="mt-1 space-y-0.5 font-mono text-caption text-hmi-label">
                    <li>
                      DEV.MAX{' '}
                      <span className="text-hmi-text">{fixed(event.max_deviation_pct, 1)}%</span>
                    </li>
                    <li>
                      STAB <span className="text-hmi-text">{event.time_to_stabilize_sec}s</span>
                    </li>
                    <li>
                      OP.ACT <span className="text-hmi-text">{event.n_operator_actions}</span>
                    </li>
                  </ul>
                </div>
              );
            }}
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
          {grades.map((grade) => (
            <Scatter
              key={grade}
              name={grade}
              data={events.filter((event) => event.grade === grade)}
              fill={gradeColor(grade)}
              onClick={(point: unknown) => {
                const event = (point as { payload?: EventSummary })?.payload;
                if (event) onSelect(event.event_id);
              }}
              shape={(props: unknown) => {
                // Recharts hands the shape renderer a wide internal prop bag;
                // only placement and the row behind the point matter here.
                const { cx, cy, payload } = props as {
                  cx: number;
                  cy: number;
                  payload: EventSummary;
                };
                const selected = payload.event_id === selectedEventId;
                const size = 3 + Math.min(payload.n_operator_actions, 10) * 0.6;
                return (
                  <g style={{ cursor: 'pointer' }}>
                    <rect
                      x={cx - size}
                      y={cy - size}
                      width={size * 2}
                      height={size * 2}
                      fill={gradeColor(payload.grade)}
                      fillOpacity={selected ? 1 : 0.55}
                    />
                    {selected && (
                      <rect
                        x={cx - size - 3}
                        y={cy - size - 3}
                        width={size * 2 + 6}
                        height={size * 2 + 6}
                        fill="none"
                        stroke={PEN.scan}
                        strokeWidth={1}
                      />
                    )}
                  </g>
                );
              }}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </TrendPanel>
  );
}

/** Compact single-tag recorder, used for the event detail strip. */
export function MiniTrend({
  samples,
  dataKey,
  color,
  label,
  tag,
  unit,
  height = 170,
}: {
  samples: TimelineSample[];
  dataKey: keyof TimelineSample;
  color: string;
  label: string;
  tag: string;
  unit?: string;
  height?: number;
}) {
  const data = samples.map((sample) => ({
    t: sample.time_since_transition_start_sec,
    value: sample[dataKey] as number,
  }));
  const last = data.length - 1;

  return (
    <TrendPanel
      title={label}
      tag={`TREND / ${tag}`}
      height={height}
      pens={[{ tag, name: unit ? unit.trim() : 'Measured', color }]}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={CHART_MARGIN}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="t" {...AXIS_PROPS} tickFormatter={timeTick} />
          <YAxis {...AXIS_PROPS} width={48} domain={['auto', 'auto']} />
          <Tooltip content={<HmiTooltip labelFormatter={tooltipTime} digits={3} />} />
          <Line
            type="linear"
            dataKey="value"
            name={tag}
            stroke={color}
            strokeWidth={1.75}
            dot={penTip(color, last)}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </TrendPanel>
  );
}
