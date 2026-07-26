import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

/**
 * Operator station layout: a persistent header strip across the top, a fixed
 * navigation rail, and a scrolling display area on a faint schematic grid.
 *
 * Below `lg` the rail stacks above the display so the app stays usable at
 * smaller widths without a separate mobile design.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full min-h-full flex-col">
      <TopBar />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <Sidebar />
        <main className="hmi-grid min-w-0 flex-1 overflow-y-auto px-4 py-5 sm:px-5 lg:px-6">
          <div className="mx-auto max-w-shell space-y-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
