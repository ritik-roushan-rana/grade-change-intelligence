import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import clsx from 'clsx';

interface CollapsibleProps {
  title: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  /** Instrument tag code for the sub-display. */
  tag?: string;
  /** Right-aligned header content, e.g. an alarm tile. */
  aside?: ReactNode;
  className?: string;
}

/**
 * Collapsed sub-display. Styled as a panel header that opens: same bezel and
 * header strip as `Panel`, with a hard-edged +/− control instead of a chevron.
 */
export function Collapsible({
  title,
  children,
  defaultOpen = false,
  tag,
  aside,
  className,
}: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();

  return (
    <div
      className={clsx('rounded-panel border border-hmi-line bg-hmi-panel', className)}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className={clsx(
          'flex w-full items-center gap-3 bg-hmi-header px-3 py-2 text-left transition-colors hover:bg-hmi-bezel/40',
          open && 'border-b border-hmi-line',
        )}
      >
        <span
          className="flex h-4 w-4 shrink-0 items-center justify-center border border-hmi-bezel font-mono text-micro leading-none text-hmi-label"
          aria-hidden="true"
        >
          {open ? '−' : '+'}
        </span>
        <span className="min-w-0 flex-1 text-tag uppercase text-hmi-text">{title}</span>
        {aside ?? (tag && <span className="font-mono text-micro text-hmi-dim">{tag}</span>)}
      </button>
      {open && (
        <div id={panelId} className="animate-fade-in p-4">
          {children}
        </div>
      )}
    </div>
  );
}
