import clsx from 'clsx';
import type { ReactNode } from 'react';

type Variant = 'critical' | 'high' | 'medium' | 'normal' | 'neutral';

/** Tinted wash + hairline, like a small annunciator tile. */
const OUTLINE: Record<Variant, string> = {
  critical: 'border-alarm-critical/60 bg-alarm-critical-fill text-alarm-critical',
  high: 'border-alarm-high/60 bg-alarm-high-fill text-alarm-high',
  medium: 'border-alarm-medium/60 bg-alarm-medium-fill text-alarm-medium',
  normal: 'border-alarm-normal/60 bg-alarm-normal-fill text-alarm-normal',
  neutral: 'border-hmi-bezel bg-hmi-header text-hmi-label',
};

/** Solid fill with reverse contrast, for states that must not be missed. */
const SOLID: Record<Variant, string> = {
  critical: 'border-alarm-critical bg-alarm-critical hmi-reverse',
  high: 'border-alarm-high bg-alarm-high hmi-reverse',
  medium: 'border-alarm-medium bg-alarm-medium hmi-reverse',
  normal: 'border-alarm-normal bg-alarm-normal hmi-reverse',
  neutral: 'border-hmi-bezel bg-hmi-bezel text-hmi-text',
};

interface BadgeProps {
  children: ReactNode;
  variant?: Variant;
  /** Reverse-contrast solid tile instead of a tinted outline. */
  solid?: boolean;
  className?: string;
}

/**
 * Status tile. Always uppercase and monospaced: these read as instrument
 * annotations, not content chips.
 */
export function Badge({ children, variant = 'neutral', solid = false, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-control border px-1.5 py-0.5 font-mono text-micro font-medium uppercase',
        solid ? SOLID[variant] : OUTLINE[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
