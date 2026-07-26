import clsx from 'clsx';
import type { ReactNode } from 'react';

interface PanelProps {
  children: ReactNode;
  className?: string;
  /** Uppercase panel label, printed in the header strip. */
  label?: ReactNode;
  /** Instrument tag code, right-aligned in the header strip. */
  tag?: string;
  /** Right-aligned content in the header strip (overrides `tag`). */
  aside?: ReactNode;
  /** Fill the grid row so panels in a row share one height. */
  fill?: boolean;
  /** `none` for panels that supply their own inset (e.g. a flush table). */
  padding?: 'none' | 'md';
}

/**
 * The console's spacing rule, applied by every panel-like surface in the app:
 *
 *   PANEL_BODY   20px inset on all sides, regardless of how much content the
 *                panel happens to hold. A sparse panel gets a shorter height,
 *                never looser padding.
 *   PANEL_STRIP  16px horizontal / 8px vertical for header strips, pen bars and
 *                footers, so every strip in the app is the same height.
 */
export const PANEL_BODY = 'p-5';
export const PANEL_STRIP = 'px-4 py-2';

/**
 * The console's only surface: a hairline-bordered instrument bezel with a
 * labelled header strip. Near-square corners, no drop shadow — depth comes from
 * the 1px border and the darker header, the way a bezelled panel on a real
 * operator console does.
 */
export function Panel({
  children,
  className,
  label,
  tag,
  aside,
  fill = false,
  padding = 'md',
}: PanelProps) {
  const hasHeader = Boolean(label || tag || aside);

  return (
    <section
      className={clsx(
        'rounded-panel border border-hmi-line bg-hmi-panel',
        fill && 'flex h-full flex-col',
        className,
      )}
    >
      {hasHeader && (
        <header
          className={clsx(
            'flex items-center justify-between gap-3 border-b border-hmi-line bg-hmi-header',
            PANEL_STRIP,
          )}
        >
          {label && <h3 className="text-tag uppercase text-hmi-label">{label}</h3>}
          {aside ?? (tag && <span className="font-mono text-micro text-hmi-dim">{tag}</span>)}
        </header>
      )}
      <div
        className={clsx(
          padding === 'md' && PANEL_BODY,
          fill && 'flex flex-1 flex-col',
        )}
      >
        {children}
      </div>
    </section>
  );
}

interface SectionProps {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  aside?: ReactNode;
  /** Tag code shown beside the section rule. */
  tag?: string;
  id?: string;
}

/**
 * Screen subdivision. The title sits on a hairline rule with an optional tag,
 * mirroring how a console screen separates equipment groups.
 */
export function Section({ title, description, children, aside, tag, id }: SectionProps) {
  return (
    <section id={id} className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-hmi-line pb-1.5">
        <div className="flex items-baseline gap-3">
          <h2 className="text-panel uppercase text-hmi-text">{title}</h2>
          {tag && <span className="font-mono text-micro text-hmi-dim">{tag}</span>}
        </div>
        {aside}
      </div>
      {description && <p className="max-w-5xl text-caption text-hmi-label">{description}</p>}
      {children}
    </section>
  );
}

interface ScreenHeaderProps {
  /** Screen name, as it would appear in a console's display directory. */
  title: string;
  caption: string;
  /** Screen number/tag, e.g. `DISP-01 · QCS.GC`. */
  tag: string;
  aside?: ReactNode;
}

export function ScreenHeader({ title, caption, tag, aside }: ScreenHeaderProps) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 border-b border-hmi-bezel pb-3">
      <div>
        <div className="flex items-baseline gap-3">
          <h1 className="text-screen uppercase text-hmi-text">{title}</h1>
          <span className="font-mono text-micro text-hmi-dim">{tag}</span>
        </div>
        <p className="mt-1.5 max-w-5xl text-caption text-hmi-label">{caption}</p>
      </div>
      {aside}
    </header>
  );
}
