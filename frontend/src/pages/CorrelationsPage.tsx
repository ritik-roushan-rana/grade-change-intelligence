import { useCorrelations } from '../lib/queries';
import { fixed } from '../lib/format';
import { impactStyle, tagFor } from '../lib/hmi';
import { Panel, ScreenHeader, Section } from '../components/ui/Panel';
import { Faceplate } from '../components/ui/Faceplate';
import { Badge } from '../components/ui/Badge';
import { Collapsible } from '../components/ui/Collapsible';
import { ErrorState, SkeletonPanel } from '../components/ui/States';
import { GradePairTrend } from '../components/charts/AnalysisCharts';
import type { CorrelationFinding, FeatureImportance, Impact } from '../lib/types';

const IMPACT_VARIANT: Record<Impact, 'critical' | 'medium' | 'normal'> = {
  high: 'critical',
  medium: 'medium',
  low: 'normal',
};

export function CorrelationsPage() {
  const { data, isPending, isError, error, refetch } = useCorrelations();

  if (isError) {
    return (
      <>
        <Header events={119} />
        <ErrorState
          error={error}
          context="correlation analysis"
          onRetry={() => void refetch()}
        />
      </>
    );
  }

  if (isPending || !data) {
    return (
      <>
        <Header events={119} />
        <div className="grid gap-4 sm:grid-cols-3">
          <SkeletonPanel lines={1} label="Count" />
          <SkeletonPanel lines={1} label="Count" />
          <SkeletonPanel lines={1} label="Count" />
        </div>
        <SkeletonPanel lines={4} label="Finding" />
        <SkeletonPanel lines={4} label="Finding" />
      </>
    );
  }

  return (
    <>
      <Header events={data.n_events_analyzed} />

      <div className="grid items-stretch gap-4 sm:grid-cols-3">
        <Faceplate
          label="Total findings"
          tag="COR.N"
          value={data.total_findings}
          detail="MINED FROM HISTORY"
        />
        <Faceplate
          label="High impact"
          tag="COR.HI"
          value={data.high_impact}
          tone="bad"
          detail="ACT ON THESE FIRST"
        />
        <Faceplate
          label="Medium impact"
          tag="COR.MED"
          value={data.medium_impact}
          tone="warn"
          detail="TUNE WHERE PRACTICAL"
        />
      </div>

      <Section
        title="Discovered Correlations"
        tag="COR.REGISTER"
        description="Each finding names the variables involved, the strength of the relationship, and the recommended response."
      >
        <div className="space-y-2">
          {data.findings.map((finding, index) => (
            <FindingPanel key={finding.id} finding={finding} index={index + 1} />
          ))}
        </div>
      </Section>

      <Section
        title="Parameters With Highest Impact on Stabilization"
        tag="MDL.IMPORTANCE"
        description="Process variables and derived signals that most strongly determine whether a grade change stabilizes quickly or goes off-spec. Ranked by importance in the trained Random Forest classifier."
      >
        <Panel label="Feature importance" tag="MDL.GINI" padding="none">
          <ul className="divide-y divide-hmi-line">
            {data.feature_importances.map((feature, index) => (
              <FeatureRow key={feature.feature} feature={feature} rank={index + 1} />
            ))}
          </ul>
        </Panel>
        <p className="font-mono text-micro text-hmi-dim">
          SRC: {data.feature_importance_source}
        </p>
      </Section>
    </>
  );
}

function Header({ events }: { events: number }) {
  return (
    <ScreenHeader
      title="Correlation Analysis"
      tag="DISP-02 · QCS.COR"
      caption={`Patterns mined from ${events} historical grade-change events — relationships that impact transition quality.`}
    />
  );
}

function FindingPanel({ finding, index }: { finding: CorrelationFinding; index: number }) {
  const alarm = impactStyle(finding.impact);

  return (
    <Collapsible
      title={
        <span className="flex items-baseline gap-2">
          <span className="font-mono text-micro text-hmi-dim">
            FND-{String(index).padStart(2, '0')}
          </span>
          <span>{finding.title}</span>
        </span>
      }
      aside={
        <Badge variant={IMPACT_VARIANT[finding.impact]} solid>
          {finding.impact} impact
        </Badge>
      }
    >
      <p className="text-body text-hmi-text">{finding.description}</p>

      {finding.correlation_strength !== null && (
        <div className="mt-4 grid items-stretch gap-4 sm:grid-cols-3">
          <Faceplate
            label="Correlation r"
            tag="COR.R"
            value={fixed(finding.correlation_strength, 3)}
            detail={
              Math.abs(finding.correlation_strength) > 0.5
                ? 'STRONG'
                : Math.abs(finding.correlation_strength) > 0.2
                  ? 'MODERATE'
                  : 'WEAK'
            }
          />
          <Faceplate
            label="p-value"
            tag="COR.P"
            value={fixed(finding.p_value, 4)}
            tone={finding.p_value !== null && finding.p_value < 0.05 ? 'good' : 'warn'}
            detail={
              finding.p_value !== null && finding.p_value < 0.05
                ? 'SIGNIFICANT p<0.05'
                : 'NOT SIGNIFICANT'
            }
          />
          <Faceplate
            label="Impact"
            tag="COR.IMP"
            value={finding.impact.toUpperCase()}
            tone={finding.impact === 'high' ? 'bad' : finding.impact === 'medium' ? 'warn' : 'good'}
            detail="OPERATIONAL WEIGHT"
          />
        </div>
      )}

      <div className="mt-4 rounded-panel border border-alarm-normal/40 bg-hmi-panel">
        <header className="border-b border-alarm-normal/30 bg-alarm-normal-fill px-4 py-2">
          <span className="text-tag uppercase text-alarm-normal">Recommended response</span>
        </header>
        <p className="p-5 text-body text-hmi-text">{finding.recommendation}</p>
      </div>

      {finding.detail_data && finding.detail_data.length > 0 && (
        <div className="mt-4">
          <GradePairTrend rows={finding.detail_data} />
        </div>
      )}

      <div className="mt-4 space-y-1.5 border-t border-hmi-line pt-3">
        <p className="font-mono text-micro text-hmi-dim">SRC: {finding.source}</p>
        <p className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-micro uppercase text-hmi-dim">Tags:</span>
          {finding.variables_involved.map((variable) => (
            <span
              key={variable}
              className="rounded-control border border-hmi-bezel bg-hmi-header px-1.5 py-0.5 font-mono text-micro text-hmi-label"
              title={variable}
            >
              {tagFor(variable)}
            </span>
          ))}
        </p>
      </div>
      <p className={`mt-2 font-mono text-micro ${alarm.text}`}>
        IMPACT CLASS: {alarm.label}
      </p>
    </Collapsible>
  );
}

function FeatureRow({ feature, rank }: { feature: FeatureImportance; rank: number }) {
  // Bar fill steps with magnitude: the top drivers read as signal, the tail as
  // console chrome, so the ranking is legible before any number is read.
  const fill =
    feature.importance_pct > 8
      ? 'bg-signal'
      : feature.importance_pct > 4
        ? 'bg-signal/60'
        : 'bg-hmi-bezel';

  return (
    <li className="px-5 py-3">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-micro text-hmi-dim">
          {String(rank).padStart(2, '0')}
        </span>
        <span className="font-mono text-micro text-hmi-label">{tagFor(feature.feature)}</span>
        <span className="min-w-0 flex-1 truncate text-caption uppercase tracking-wide text-hmi-text">
          {feature.label}
        </span>
        <span className="font-mono text-caption font-semibold text-signal">
          {fixed(feature.importance_pct, 1)}%
        </span>
      </div>
      <div
        className="mt-1.5 h-1.5 w-full border border-hmi-line bg-hmi-inset"
        role="meter"
        aria-valuenow={feature.importance_pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${feature.label} importance`}
      >
        <div className={`h-full ${fill}`} style={{ width: `${feature.relative_pct}%` }} />
      </div>
      <p className="mt-1.5 text-caption text-hmi-label">{feature.explanation}</p>
    </li>
  );
}
