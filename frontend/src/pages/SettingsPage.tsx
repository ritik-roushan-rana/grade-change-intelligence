import { useState } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import clsx from 'clsx';
import {
  useCacheStats,
  useClearFeedback,
  useClearServerCache,
  useFeedback,
  useModelInfo,
} from '../lib/queries';
import { fixed, percent, seconds } from '../lib/format';
import { eventTag } from '../lib/hmi';
import { useAppStore } from '../store/useAppStore';
import { Panel, ScreenHeader, Section } from '../components/ui/Panel';
import { Badge } from '../components/ui/Badge';
import { DataTable } from '../components/ui/DataTable';
import { ErrorState, Skeleton, Spinner } from '../components/ui/States';
import type { CacheEntry } from '../lib/types';

/**
 * Station maintenance display.
 *
 * Groups the state this app holds — browser query cache, session decisions, the
 * API's memoised scoring, and the persistent feedback log — and gives each an
 * explicit reset. Every control states what it drops and what survives, because
 * "clear cache" means four different things here and only one of them is
 * destructive.
 */
export function SettingsPage() {
  const queryClient = useQueryClient();

  const cache = useCacheStats();
  const feedback = useFeedback();
  const modelInfo = useModelInfo();

  const selectedEventId = useAppStore((state) => state.selectedEventId);
  const simTime = useAppStore((state) => state.simTime);
  const decisions = useAppStore((state) => state.decisions);
  const clearDecisions = useAppStore((state) => state.clearDecisions);
  const resetSelection = useAppStore((state) => state.resetSelection);

  const clearServerCache = useClearServerCache();
  const clearFeedback = useClearFeedback();

  const [note, setNote] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState('');

  const clientEntries = queryClient.getQueryCache().getAll().length;
  const decisionCount = Object.keys(decisions).length;
  const logEntries = feedback.data?.entries.length ?? 0;

  const announce = (message: string) => {
    setNote(message);
    window.setTimeout(() => setNote(null), 6000);
  };

  return (
    <>
      <ScreenHeader
        title="Station Settings"
        tag="DISP-05 · QCS.CFG"
        caption="Reset the state this station holds. Each control names exactly what it drops and what survives."
        aside={note ? <Badge variant="normal">{note}</Badge> : undefined}
      />

      {/* ── Session state (browser only) ── */}
      <Section
        title="Session"
        tag="CFG.SESSION"
        description="Held in this browser tab only. Nothing here touches the API or any stored data."
      >
        <div className="grid items-stretch gap-4 lg:grid-cols-2">
          <ControlPanel
            label="Display cache"
            tag="CFG.QUERYCACHE"
            state={`${clientEntries} cached response${clientEntries === 1 ? '' : 's'}`}
            explains="Timelines, predictions and recommendations already fetched, keyed by event and simulation time. This is what makes scrubbing the time slider instant. Clearing it forces every display to refetch."
            actions={[
              {
                label: 'Clear display cache',
                onClick: () => {
                  queryClient.clear();
                  announce('Display cache cleared — displays will refetch');
                },
              },
              {
                label: 'Refetch all displays',
                onClick: () => {
                  void queryClient.refetchQueries();
                  announce('Refetching every active display');
                },
              },
            ]}
          />

          <ControlPanel
            label="Operator decisions"
            tag="CFG.DECISIONS"
            state={`${decisionCount} suggestion${decisionCount === 1 ? '' : 's'} marked this session`}
            explains="Which suggestions this tab has already acknowledged or rejected, so their controls stay disabled. Clearing lets them be actioned again — it does not remove anything already written to the feedback log."
            actions={[
              {
                label: 'Clear decision marks',
                onClick: () => {
                  clearDecisions();
                  announce('Decision marks cleared — suggestions are actionable again');
                },
                disabled: decisionCount === 0,
              },
            ]}
          />

          <ControlPanel
            label="Selection"
            tag="CFG.SELECTION"
            state={`${eventTag(selectedEventId)} at T+${simTime}s`}
            explains="The event loaded on the monitor and the position of the replay transport. Resetting returns to the Moderate preset at the default 180s position."
            actions={[
              {
                label: 'Reset to defaults',
                onClick: () => {
                  resetSelection();
                  announce('Selection reset to GC-0046 at T+180s');
                },
              },
            ]}
          />

          <ControlPanel
            label="Full session reset"
            tag="CFG.RESET"
            state="Combines the three resets above"
            explains="Returns this tab to a first-load state: caches dropped, decision marks cleared, selection back to defaults. The feedback log and the trained models are untouched."
            actions={[
              {
                label: 'Reset session',
                onClick: () => {
                  queryClient.clear();
                  clearDecisions();
                  resetSelection();
                  announce('Session reset');
                },
              },
            ]}
          />
        </div>
      </Section>

      {/* ── Server state ── */}
      <Section
        title="Prediction Service"
        tag="CFG.SERVICE"
        description="State held by the API process. Shared by every connected station."
      >
        {cache.isError ? (
          <ErrorState
            error={cache.error}
            context="cache statistics"
            onRetry={() => void cache.refetch()}
          />
        ) : !cache.data ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <>
            <Panel label="Scoring cache" tag="CFG.SRVCACHE" padding="none">
              <DataTable<CacheEntry>
                rows={cache.data.caches}
                rowKey={(row) => row.name}
                columns={[
                  { key: 'label', header: 'Cache', render: (row) => row.label },
                  {
                    key: 'entries',
                    header: 'Entries',
                    align: 'right',
                    mono: true,
                    render: (row) => `${row.entries} / ${row.capacity}`,
                    sortValue: (row) => row.entries,
                  },
                  {
                    key: 'hits',
                    header: 'Hits',
                    align: 'right',
                    mono: true,
                    render: (row) => row.hits,
                    sortValue: (row) => row.hits,
                  },
                  {
                    key: 'misses',
                    header: 'Misses',
                    align: 'right',
                    mono: true,
                    render: (row) => row.misses,
                    sortValue: (row) => row.misses,
                  },
                  {
                    key: 'hit_rate',
                    header: 'Hit rate',
                    align: 'right',
                    mono: true,
                    render: (row) =>
                      row.hit_rate === null ? '—' : percent(row.hit_rate, 1),
                    sortValue: (row) => row.hit_rate ?? 0,
                  },
                ]}
              />
            </Panel>

            <div className="grid items-stretch gap-4 lg:grid-cols-2">
              <ControlPanel
                label="Server scoring cache"
                tag="CFG.SRVCACHE"
                state={`${cache.data.total_entries} memoised result${cache.data.total_entries === 1 ? '' : 's'}`}
                explains="Predictions and recommendations already computed for an (event, time) pair. Clearing means the next request re-runs the models — a few milliseconds, not a retrain. The trained models, recovery library and datasets are kept in memory."
                actions={[
                  {
                    label: clearServerCache.isPending ? 'Clearing…' : 'Clear server cache',
                    onClick: () => {
                      clearServerCache.mutate(undefined, {
                        onSuccess: (result) =>
                          announce(`Server cache cleared — ${result.total_cleared} entries dropped`),
                        onError: () => announce('Could not clear the server cache'),
                      });
                    },
                    disabled: clearServerCache.isPending || cache.data.total_entries === 0,
                  },
                ]}
                footer={
                  <span className="flex items-center gap-2">
                    <Badge variant="normal">Models retained</Badge>
                    <span className="font-mono text-micro text-hmi-dim">
                      warm-up was {seconds(cache.data.model_warmup_seconds)} — clearing this
                      does not repeat it
                    </span>
                  </span>
                }
              />

              <ControlPanel
                label="Loaded models"
                tag="CFG.MODELS"
                state={cache.data.models_loaded ? 'Trained and resident' : 'Not loaded'}
                explains="The Random Forest classifier, Gradient Boosting regressor and KNN recovery library are trained once when the service starts. There is deliberately no control to drop them: doing so would cost the entire warm-up again with nothing gained. Restart the service to retrain."
                actions={[]}
                footer={
                  modelInfo.data ? (
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
                      <Stat label="Accuracy" value={percent(modelInfo.data.evaluation.test_accuracy, 1)} />
                      <Stat label="F1" value={percent(modelInfo.data.evaluation.test_f1, 1)} />
                      <Stat label="Regressor R²" value={fixed(modelInfo.data.evaluation.test_r2, 3)} />
                      <Stat label="Recovery patterns" value={String(modelInfo.data.recovery_patterns)} />
                    </dl>
                  ) : (
                    <Spinner label="Reading model info" />
                  )
                }
              />
            </div>
          </>
        )}
      </Section>

      {/* ── Persistent data ── */}
      <Section
        title="Stored Data"
        tag="CFG.STORE"
        description="Written to disk by the service. Clearing this is not reversible."
      >
        <div
          className={clsx(
            'rounded-panel border bg-hmi-panel',
            confirmText === 'CLEAR' ? 'border-alarm-critical' : 'border-hmi-line',
          )}
        >
          <header className="flex items-center justify-between gap-3 border-b border-hmi-line bg-hmi-header px-4 py-2">
            <span className="text-tag uppercase text-hmi-label">Operator feedback log</span>
            <span className="font-mono text-micro text-hmi-dim">CFG.ACKLOG</span>
          </header>

          <div className="space-y-3 p-5">
            <p className="font-mono text-pv-sm text-hmi-text">
              {logEntries}{' '}
              <span className="text-caption text-hmi-dim">
                recorded decision{logEntries === 1 ? '' : 's'}
              </span>
            </p>

            <p className="text-caption text-hmi-label">
              This log is the record of which suggestions operators accepted or rejected —
              the evidence used to judge suggestion quality over time. Clearing it deletes
              that history permanently; the file keeps its header so logging continues
              normally afterwards.
            </p>

            <p className="text-caption text-hmi-label">
              Export first if you might need it. The Feedback Log display has a CSV
              download.
            </p>

            <div className="flex flex-wrap items-center gap-3 border-t border-hmi-line pt-3">
              <label htmlFor="confirm-clear" className="text-micro uppercase text-hmi-dim">
                Type CLEAR to enable
              </label>
              <input
                id="confirm-clear"
                value={confirmText}
                onChange={(event) => setConfirmText(event.target.value.toUpperCase())}
                placeholder="CLEAR"
                className="w-28 rounded-control border border-hmi-bezel bg-hmi-inset px-2 py-1 font-mono text-caption text-hmi-text placeholder:text-hmi-dim"
              />
              <button
                type="button"
                disabled={confirmText !== 'CLEAR' || clearFeedback.isPending || logEntries === 0}
                onClick={() =>
                  clearFeedback.mutate(undefined, {
                    onSuccess: (result) => {
                      announce(`Feedback log cleared — ${result.entries_removed} entries removed`);
                      setConfirmText('');
                    },
                    onError: () => announce('Could not clear the feedback log'),
                  })
                }
                className="rounded-control border border-alarm-critical bg-alarm-critical-fill px-3 py-1.5 font-mono text-micro font-semibold uppercase text-alarm-critical transition-colors hover:bg-alarm-critical hover:text-hmi-void disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-alarm-critical-fill disabled:hover:text-alarm-critical"
              >
                {clearFeedback.isPending ? 'Clearing…' : 'Clear feedback log'}
              </button>
            </div>
          </div>
        </div>
      </Section>
    </>
  );
}

interface Action {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

function ControlPanel({
  label,
  tag,
  state,
  explains,
  actions,
  footer,
}: {
  label: string;
  tag: string;
  state: string;
  explains: string;
  actions: Action[];
  footer?: ReactNode;
}) {
  return (
    <Panel label={label} tag={tag} fill>
      <p className="font-mono text-pv-xs text-hmi-text">{state}</p>
      <p className="mt-2 flex-1 text-caption text-hmi-label">{explains}</p>
      {footer && <div className="mt-3 border-t border-hmi-line pt-3">{footer}</div>}
      {actions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-hmi-line pt-3">
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              onClick={action.onClick}
              disabled={action.disabled}
              className="rounded-control border border-hmi-bezel bg-hmi-header px-3 py-1.5 font-mono text-micro uppercase text-hmi-label transition-colors hover:border-signal hover:text-signal disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-hmi-bezel disabled:hover:text-hmi-label"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </Panel>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="font-mono text-micro uppercase text-hmi-dim">{label}</dt>
      <dd className="font-mono text-caption text-hmi-text">{value}</dd>
    </div>
  );
}
