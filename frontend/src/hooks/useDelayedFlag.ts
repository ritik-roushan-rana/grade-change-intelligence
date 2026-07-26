import { useEffect, useState } from 'react';

/**
 * True only once `active` has held for `delayMs`.
 *
 * Used to gate loading indicators: a request that resolves in 80ms should not
 * flash a spinner, but one that takes 400ms must show something.
 */
export function useDelayedFlag(active: boolean, delayMs = 300): boolean {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!active) {
      setVisible(false);
      return;
    }
    const timer = window.setTimeout(() => setVisible(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [active, delayMs]);

  return visible;
}
