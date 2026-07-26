/** Number and label formatting. Presentation only. */

export const fixed = (value: number | null | undefined, digits = 2): string =>
  value === null || value === undefined || Number.isNaN(value) ? '—' : value.toFixed(digits);

export const signed = (value: number | null | undefined, digits = 2): string =>
  value === null || value === undefined || Number.isNaN(value)
    ? '—'
    : `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toFixed(digits)}`;

export const percent = (fraction: number | null | undefined, digits = 0): string =>
  fraction === null || fraction === undefined || Number.isNaN(fraction)
    ? '—'
    : `${(fraction * 100).toFixed(digits)}%`;

export const seconds = (value: number | null | undefined): string =>
  value === null || value === undefined || Number.isNaN(value) ? '—' : `${Math.round(value)}s`;

/** 2685 -> "44:45" for the slider readout. */
export const clock = (totalSeconds: number): string => {
  const safe = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  return `${minutes}:${String(rest).padStart(2, '0')}`;
};

/** ISO timestamp -> "2026-07-26 04:31:18" (mono column in the feedback table). */
export const timestamp = (iso: string): string => {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} ` +
    `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`
  );
};

/** `steam_pressure` -> `Steam Pressure` (fallback when the API sends no label). */
export const titleize = (value: string): string =>
  value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
