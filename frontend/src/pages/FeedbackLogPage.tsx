import { useMemo } from 'react';
import { useFeedback } from '../lib/queries';
import { fixed, percent, signed, timestamp } from '../lib/format';
import { alarmStyle, eventTag, tagFor } from '../lib/hmi';
import { Panel, ScreenHeader, Section } from '../components/ui/Panel';
import { Faceplate } from '../components/ui/Faceplate';
import { Badge } from '../components/ui/Badge';
import { DataTable } from '../components/ui/DataTable';
import { EmptyState, ErrorState, SkeletonPanel } from '../components/ui/States';
import type { FeedbackEntry } from '../lib/types';

const asNumber = (value: number | string): number =>
  typeof value === 'number' ? value : Number.parseFloat(value);

export function FeedbackLogPage() {
  const { data, isPending, isError, error, refetch } = useFeedback();

  const csvHref = useMemo(() => {
    if (!data || data.entries.length === 0) return null;
    const escape = (value: unknown) => {
      const text = value === null || value === undefined ? '' : String(value);
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };
    const rows = [
      data.columns.join(','),
      ...data.entries.map((entry) =>
        data.columns.map((column) => escape(entry[column as keyof FeedbackEntry])).join(','),
      ),
    ];
    return `data:text/csv;charset=utf-8,${encodeURIComponent(rows.join('\n'))}`;
  }, [data]);

  if (isError) {
    return (
      <>
        <Header />
        <ErrorState error={error} context="the feedback log" onRetry={() => void refetch()} />
      </>
    );
  }

  if (isPending || !data) {
    return (
      <>
        <Header />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SkeletonPanel lines={1} label="Count" />
          <SkeletonPanel lines={1} label="Count" />
          <SkeletonPanel lines={1} label="Count" />
          <SkeletonPanel lines={1} label="Count" />
        </div>
        <SkeletonPanel lines={6} label="Log" />
      </>
    );
  }

  if (data.entries.length === 0) {
    return (
      <>
        <Header />
        <EmptyState
          title="No decisions logged"
          tag="ACK.LOG"
          hint="Acknowledge or reject a corrective action on DISP-01 to start the log."
        />
      </>
    );
  }

  const { stats } = data;

  return (
    <>
      <Header />

      <div className="grid items-stretch gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Faceplate
          label="Total decisions"
          tag="ACK.N"
          value={stats.total_decisions}
          detail="OPERATOR RESPONSES"
        />
        <Faceplate
          label="Acknowledged"
          tag="ACK.OK"
          value={stats.accepted}
          tone="good"
          detail="ACTION APPLIED"
        />
        <Faceplate
          label="Rejected"
          tag="ACK.REJ"
          value={stats.rejected}
          tone="warn"
          detail="OPERATOR OVERRODE"
        />
        <Faceplate
          label="Accept rate"
          tag="ACK.RATE"
          value={percent(stats.accept_rate, 0)}
          range={{ min: 0, max: 100, current: stats.accept_rate * 100 }}
          detail={`${stats.accepted} OF ${stats.total_decisions}`}
        />
      </div>

      <Section
        title="Decision History"
        tag="ACK.LOG"
        aside={
          csvHref && (
            <a
              href={csvHref}
              download="feedback_log.csv"
              className="rounded-control border border-hmi-bezel bg-hmi-header px-2.5 py-1 font-mono text-micro uppercase text-hmi-label transition-colors hover:border-signal hover:text-signal"
            >
              ⬇ Export CSV
            </a>
          )
        }
      >
        <DataTable<FeedbackEntry>
          rows={data.entries}
          rowKey={(row) => `${row.timestamp}-${row.variable}`}
          initialSort={{ key: 'timestamp', direction: 'desc' }}
          maxHeight="32rem"
          columns={[
            {
              key: 'timestamp',
              header: 'Logged at',
              mono: true,
              render: (row) => timestamp(row.timestamp),
              sortValue: (row) => row.timestamp,
            },
            {
              key: 'event_id',
              header: 'Event',
              mono: true,
              render: (row) => eventTag(row.event_id),
              sortValue: (row) => row.event_id,
            },
            {
              key: 'risk_level',
              header: 'Alarm at decision',
              sortValue: (row) => row.risk_level,
              render: (row) => (
                <span className={`font-mono ${alarmStyle(row.risk_level).text}`}>
                  {alarmStyle(row.risk_level).label}
                </span>
              ),
            },
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
              sortValue: (row) => row.variable,
              render: (row) =>
                row.variable
                  .split('_')
                  .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
                  .join(' '),
            },
            {
              key: 'change',
              header: 'Setpoint move',
              align: 'right',
              mono: true,
              sortValue: (row) => asNumber(row.change),
              render: (row) => (
                <span className="whitespace-nowrap">
                  {fixed(asNumber(row.current_value))} ▶ {fixed(asNumber(row.recommended_value))}
                  <span
                    className={
                      asNumber(row.change) > 0 ? 'text-alarm-normal' : 'text-alarm-high'
                    }
                  >
                    {' '}
                    ({signed(asNumber(row.change))})
                  </span>
                </span>
              ),
            },
            {
              key: 'decision',
              header: 'Decision',
              sortValue: (row) => row.decision,
              render: (row) =>
                row.decision === 'accept' ? (
                  <Badge variant="normal">✓ Ack</Badge>
                ) : (
                  <Badge variant="high">✗ Rejected</Badge>
                ),
            },
            {
              key: 'source',
              header: 'Source',
              className: 'max-w-cell truncate whitespace-normal',
              render: (row) => <span className="text-hmi-dim">{row.source}</span>,
              sortValue: (row) => row.source,
            },
          ]}
        />
      </Section>

      {Object.keys(stats.by_variable).length > 0 && (
        <Section
          title="Decisions by Tag"
          tag="ACK.BYTAG"
          description="Which suggestion types operators trust, and which they override."
        >
          <Panel label="Breakdown" tag="ACK.BYTAG" padding="none">
            <ul className="divide-y divide-hmi-line">
              {Object.entries(stats.by_variable).map(([key, count]) => {
                const cleaned = key.replace(/[()']/g, '');
                const [variable, decision] = cleaned.split(/,\s*/);
                return (
                  <li
                    key={key}
                    className="flex items-baseline justify-between gap-3 px-3 py-2"
                  >
                    <span className="flex items-baseline gap-2">
                      <span className="font-mono text-micro text-hmi-dim">
                        {tagFor(variable ?? '')}
                      </span>
                      <span className="font-mono text-caption uppercase text-hmi-label">
                        {decision ?? ''}
                      </span>
                    </span>
                    <span className="font-mono text-caption text-hmi-text">{count}</span>
                  </li>
                );
              })}
            </ul>
          </Panel>
        </Section>
      )}
    </>
  );
}

function Header() {
  return (
    <ScreenHeader
      title="Operator Feedback Log"
      tag="DISP-04 · QCS.ACK"
      caption="Acknowledge/reject decisions on corrective actions — tracks suggestion quality over time."
    />
  );
}
