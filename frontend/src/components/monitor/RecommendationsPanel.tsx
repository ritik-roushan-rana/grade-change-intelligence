import { useState } from 'react';
import { useSubmitFeedback } from '../../lib/queries';
import { ApiError } from '../../lib/api';
import { seconds } from '../../lib/format';
import { eventTag } from '../../lib/hmi';
import { useAppStore } from '../../store/useAppStore';
import type { Decision, RecommendationsResponse } from '../../lib/types';
import { Panel, Section } from '../ui/Panel';
import { RecommendationCard } from './RecommendationCard';
import { ErrorState, SkeletonPanel } from '../ui/States';

interface RecommendationsPanelProps {
  eventId: number;
  t: number;
  data: RecommendationsResponse | undefined;
  isPending: boolean;
  error: unknown;
  onRetry: () => void;
}

const SECTION_TAG = 'ACT.QUEUE';

export function RecommendationsPanel({
  eventId,
  t,
  data,
  isPending,
  error,
  onRetry,
}: RecommendationsPanelProps) {
  const decisions = useAppStore((state) => state.decisions);
  const pending = useAppStore((state) => state.pending);
  const markPending = useAppStore((state) => state.markPending);
  const recordDecision = useAppStore((state) => state.recordDecision);
  const clearPending = useAppStore((state) => state.clearPending);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const submitFeedback = useSubmitFeedback();

  const decide = (recommendationId: string, decision: Decision) => {
    // Optimistic: the store flips to pending immediately, so the controls react
    // on the same frame as the press rather than after the round trip.
    markPending(recommendationId);
    setErrors((current) => {
      const next = { ...current };
      delete next[recommendationId];
      return next;
    });

    submitFeedback.mutate(
      { event_id: eventId, timestamp: t, recommendation_id: recommendationId, decision },
      {
        onSuccess: () => recordDecision(recommendationId, decision),
        onError: (mutationError) => {
          clearPending(recommendationId);
          setErrors((current) => ({
            ...current,
            [recommendationId]:
              mutationError instanceof ApiError
                ? mutationError.message
                : 'Could not record that decision.',
          }));
        },
      },
    );
  };

  if (error) {
    return (
      <Section title="Corrective Actions" tag={SECTION_TAG}>
        <ErrorState error={error} context="corrective actions" onRetry={onRetry} />
      </Section>
    );
  }

  if (isPending || !data) {
    return (
      <Section title="Corrective Actions" tag={SECTION_TAG}>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <SkeletonPanel lines={5} label="Action" />
          <SkeletonPanel lines={5} label="Action" />
          <SkeletonPanel lines={5} label="Action" />
        </div>
      </Section>
    );
  }

  if (!data.available) {
    return (
      <Section title="Corrective Actions" tag={SECTION_TAG}>
        <Panel label="No action" tag={SECTION_TAG}>
          <p className="text-caption text-hmi-label">{data.message}</p>
        </Panel>
      </Section>
    );
  }

  if (data.action === 'maintain') {
    return (
      <Section title="Corrective Actions" tag={SECTION_TAG}>
        <div className="rounded-panel border border-alarm-normal/50 bg-hmi-panel">
          <header className="flex items-center justify-between border-b border-alarm-normal/40 bg-alarm-normal-fill px-3 py-1.5">
            <span className="text-tag uppercase text-alarm-normal">No action required</span>
            <span className="font-mono text-micro text-alarm-normal/80">HOLD</span>
          </header>
          <p className="px-4 py-3 text-body text-hmi-text">{data.message}</p>
        </div>
      </Section>
    );
  }

  return (
    <Section
      title="Corrective Actions"
      tag={SECTION_TAG}
      description={data.message}
      aside={
        data.estimated_recovery_time_sec ? (
          <span className="font-mono text-micro uppercase text-alarm-normal">
            Est. recovery {seconds(data.estimated_recovery_time_sec)}
            <span className="text-hmi-dim"> · from similar events</span>
          </span>
        ) : undefined
      }
    >
      {data.recommendations.length === 0 ? (
        <Panel label="No action" tag={SECTION_TAG}>
          <p className="text-caption text-hmi-label">
            No setpoint change cleared the engine's minimum-move threshold at this process
            state.
          </p>
        </Panel>
      ) : (
        <div className="grid items-stretch gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.recommendations.map((recommendation, index) => (
            <RecommendationCard
              key={recommendation.id}
              recommendation={recommendation}
              index={index + 1}
              decision={decisions[recommendation.id]}
              pending={Boolean(pending[recommendation.id])}
              onDecide={(decision) => decide(recommendation.id, decision)}
              error={errors[recommendation.id] ?? null}
            />
          ))}
        </div>
      )}

      {data.similar_events_used && data.similar_events_used.length > 0 && (
        <p className="font-mono text-micro text-hmi-dim">
          MATCHED:{' '}
          {data.similar_events_used.map((id) => eventTag(id)).join(' · ')} — SRC: {data.source}
        </p>
      )}
    </Section>
  );
}
