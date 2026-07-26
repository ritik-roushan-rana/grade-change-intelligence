import { useEffect, useState } from 'react';

/**
 * Trailing-edge debounce.
 *
 * The time slider updates its own position on every input event so the handle
 * tracks the pointer, but the value that drives API calls is debounced: a drag
 * across the full transition fires one request at the end, not one per pixel.
 */
export function useDebouncedValue<T>(value: T, delayMs = 150): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    if (value === settled) return;
    const timer = window.setTimeout(() => setSettled(value), delayMs);
    return () => window.clearTimeout(timer);
    // `settled` is deliberately excluded: including it would restart the timer
    // on every settle and stall the final update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, delayMs]);

  return settled;
}
