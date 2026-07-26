import clsx from 'clsx';
import { fixed, percent, signed } from '../../lib/format';
import { alarmStyle, penFor, tagFor } from '../../lib/hmi';
import type { Decision, Recommendation } from '../../lib/types';
import { Badge } from '../ui/Badge';

interface RecommendationCardProps {
  recommendation: Recommendation;
  /** 1-based position, printed as the instruction sequence number. */
  index: number;
  decision: Decision | undefined;
  pending: boolean;
  onDecide: (decision: Decision) => void;
  error?: string | null;
}

/**
 * An operator instruction ticket.
 *
 * Anatomy follows a real corrective-action prompt: tag code and sequence number
 * in the header, the setpoint move as a before/after faceplate pair, the limit
 * check as an annunciator tile, the reasoning as prose, and hard-edged
 * ACKNOWLEDGE / REJECT controls at the foot.
 */
export function RecommendationCard({
  recommendation,
  index,
  decision,
  pending,
  onDecide,
  error,
}: RecommendationCardProps) {
  const rising = recommendation.change > 0;
  const tag = tagFor(recommendation.variable);
  const pen = penFor(recommendation.variable);
  const { recipe_limit: limit } = recommendation;
  const alarm = alarmStyle(recommendation.risk_level);

  return (
    <article className="flex h-full flex-col rounded-panel border border-hmi-line bg-hmi-panel">
      {/* Header: instruction sequence, tag, and the pen colour of the variable
          it moves, so the ticket ties visually to the trend above. */}
      <header className="flex items-center gap-2 border-b border-hmi-line bg-hmi-header px-4 py-2">
        <span
          className="h-3 w-1 shrink-0"
          style={{ backgroundColor: pen }}
          aria-hidden="true"
        />
        <span className="font-mono text-micro text-hmi-dim">
          ACT-{String(index).padStart(2, '0')}
        </span>
        <span className="min-w-0 flex-1 truncate text-tag uppercase text-hmi-text">
          {recommendation.label}
        </span>
        <span className="shrink-0 font-mono text-micro text-hmi-dim">{tag}</span>
      </header>

      <div className="flex flex-1 flex-col p-5">
        {/* Before / after faceplate pair. */}
        <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-2">
          <ValueCell label="Current" value={fixed(recommendation.current_value)} />
          <div className="flex items-center justify-center px-1">
            <span
              className={clsx(
                'font-mono text-pv-xs',
                rising ? 'text-alarm-normal' : 'text-alarm-high',
              )}
              aria-hidden="true"
            >
              {rising ? '▶' : '▶'}
            </span>
          </div>
          <ValueCell
            label="Recommended"
            value={fixed(recommendation.recommended_value)}
            tone={rising ? 'good' : 'warn'}
            emphasis
          />
        </div>

        <p className="mt-2 flex items-baseline justify-between gap-2 font-mono text-caption">
          <span className="text-hmi-dim uppercase">Delta</span>
          <span className={clsx(rising ? 'text-alarm-normal' : 'text-alarm-high')}>
            {signed(recommendation.change)} {recommendation.unit} {rising ? '▲' : '▼'}
          </span>
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-hmi-line pt-3">
          {limit.clamped ? (
            <Badge variant="medium">
              ⚠ Clamped · {limit.min}–{limit.max}
            </Badge>
          ) : limit.min !== null ? (
            <Badge variant="normal">
              ✓ In limits · {limit.min}–{limit.max}
            </Badge>
          ) : null}
          <Badge variant="neutral">
            Match {percent(recommendation.similarity_match, 0)}
          </Badge>
          <Badge variant={alarmVariant(recommendation.risk_level)}>{alarm.label}</Badge>
        </div>

        {/* Reasoning is the one place prose is allowed. */}
        <p className="mt-3 flex-1 text-caption text-hmi-label">{recommendation.rationale}</p>

        <p className="mt-3 font-mono text-micro text-hmi-dim">SRC: {recommendation.source}</p>
      </div>

      {/* Operator acknowledge / reject controls. */}
      <footer className="border-t border-hmi-line">
        {decision ? (
          <p
            className={clsx(
              'hmi-reverse flex items-center gap-2 px-4 py-2.5 font-mono text-micro uppercase',
              decision === 'accept' ? 'bg-alarm-normal' : 'bg-hmi-bezel !text-hmi-text',
            )}
          >
            <span aria-hidden="true">{decision === 'accept' ? '✓' : '✗'}</span>
            {decision === 'accept' ? 'Acknowledged' : 'Rejected'} · logged
          </p>
        ) : (
          <div className="grid grid-cols-2 divide-x divide-hmi-line">
            <button
              type="button"
              disabled={pending}
              onClick={() => onDecide('accept')}
              className="hmi-reverse bg-signal px-4 py-2.5 font-mono text-micro font-semibold uppercase transition-colors hover:bg-signal-bright disabled:cursor-wait disabled:opacity-60"
            >
              ✓ Acknowledge
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={() => onDecide('reject')}
              className="bg-hmi-header px-4 py-2.5 font-mono text-micro font-semibold uppercase text-hmi-label transition-colors hover:bg-alarm-critical-fill hover:text-alarm-critical disabled:cursor-wait disabled:opacity-60"
            >
              ✗ Reject
            </button>
          </div>
        )}
        {error && (
          <p className="border-t border-hmi-line px-4 py-2 font-mono text-micro text-alarm-critical">
            {error}
          </p>
        )}
      </footer>
    </article>
  );
}

function ValueCell({
  label,
  value,
  tone = 'neutral',
  emphasis = false,
}: {
  label: string;
  value: string;
  tone?: 'neutral' | 'good' | 'warn';
  emphasis?: boolean;
}) {
  const toneClass =
    tone === 'good' ? 'text-alarm-normal' : tone === 'warn' ? 'text-alarm-high' : 'text-hmi-text';
  return (
    <div
      className={clsx(
        'rounded-control border bg-hmi-inset px-2 py-1.5',
        emphasis ? 'border-hmi-bezel' : 'border-hmi-line',
      )}
    >
      <span className="block font-mono text-micro uppercase text-hmi-dim">{label}</span>
      <span className={clsx('font-mono text-pv-sm', toneClass)}>{value}</span>
    </div>
  );
}

function alarmVariant(level: string): 'critical' | 'high' | 'medium' | 'normal' {
  if (level === 'critical') return 'critical';
  if (level === 'high') return 'high';
  if (level === 'medium') return 'medium';
  return 'normal';
}
