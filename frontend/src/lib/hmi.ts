/**
 * Console semantics: alarm styling, recorder-pen assignments and instrument tag
 * codes.
 *
 * Single source of truth. Anywhere an alarm state appears — banner, badge,
 * table cell, chart stroke — it resolves through `alarmStyle`, so the colour
 * cannot drift between views.
 */

import type { Impact, RiskLevel } from './types';

export interface AlarmStyle {
  /** Annunciator wording, as printed on a DCS tile. */
  label: string;
  /** Raw hex, for chart strokes and inline SVG. */
  hex: string;
  /** Solid fill (banner, annunciator tile). Pair with `.hmi-reverse` text. */
  fill: string;
  /** Tinted wash for badges and callouts. */
  wash: string;
  /** Foreground colour utility. */
  text: string;
  /** Border colour utility. */
  border: string;
}

/** ISA-18.2 alarm scale: red / orange / yellow / teal. */
export const ALARM: Record<RiskLevel, AlarmStyle> = {
  critical: {
    label: 'CRITICAL',
    hex: '#E5484D',
    fill: 'bg-alarm-critical',
    wash: 'bg-alarm-critical-fill',
    text: 'text-alarm-critical',
    border: 'border-alarm-critical',
  },
  high: {
    label: 'HIGH',
    hex: '#F5A524',
    fill: 'bg-alarm-high',
    wash: 'bg-alarm-high-fill',
    text: 'text-alarm-high',
    border: 'border-alarm-high',
  },
  medium: {
    label: 'MEDIUM',
    hex: '#F5D90A',
    fill: 'bg-alarm-medium',
    wash: 'bg-alarm-medium-fill',
    text: 'text-alarm-medium',
    border: 'border-alarm-medium',
  },
  low: {
    label: 'NORMAL',
    hex: '#2DD4BF',
    fill: 'bg-alarm-normal',
    wash: 'bg-alarm-normal-fill',
    text: 'text-alarm-normal',
    border: 'border-alarm-normal',
  },
};

export const alarmStyle = (level: RiskLevel | string | undefined): AlarmStyle =>
  ALARM[(level ?? 'low') as RiskLevel] ?? ALARM.low;

/** Correlation-finding impact maps onto the same alarm scale. */
const IMPACT_TO_ALARM: Record<Impact, RiskLevel> = {
  high: 'critical',
  medium: 'medium',
  low: 'low',
};

export const impactStyle = (impact: Impact | string): AlarmStyle =>
  alarmStyle(IMPACT_TO_ALARM[impact as Impact] ?? 'low');

export type Tone = 'good' | 'warn' | 'bad' | 'neutral';

/** Readout tone. Only ever an alarm colour or neutral console grey. */
export const TONE_TEXT: Record<Tone, string> = {
  good: 'text-alarm-normal',
  warn: 'text-alarm-high',
  bad: 'text-alarm-critical',
  neutral: 'text-hmi-text',
};

/** Matching fill for bars and range indicators. */
export const TONE_FILL: Record<Tone, string> = {
  good: 'bg-alarm-normal',
  warn: 'bg-alarm-high',
  bad: 'bg-alarm-critical',
  neutral: 'bg-hmi-text',
};

/** Border colour, for needles and outline marks that must read on dark. */
export const TONE_BORDER: Record<Tone, string> = {
  good: 'border-alarm-normal',
  warn: 'border-alarm-high',
  bad: 'border-alarm-critical',
  neutral: 'border-hmi-text',
};

/** Field names match the API's recipe-limit payload so no mapping is needed. */
export interface LimitReading {
  min: number;
  max: number;
  current_value: number | null;
  within_limits: boolean | null;
  violation: number | null;
}

export interface LimitStatus {
  tone: Tone;
  /** Scannable status text, e.g. `OUT OF RANGE +2.26`. */
  text: string;
  /** Glyph matched to severity: dot for normal, triangle for a deviation. */
  icon: string;
}

/**
 * Grade a reading against its recipe range.
 *
 * Severity is measured in units of the range's own width, not absolute value,
 * because the ranges differ by orders of magnitude — caliper spans 1.76 µm while
 * steam pressure spans 24 kPa, so a raw violation of 2.0 means very different
 * things. A reading outside its range by more than the full width of that range
 * is treated as critical; anything less is a caution. That keeps red rare enough
 * to still mean something: on a bad transition it fires for the two genuinely
 * broken variables rather than for all five that are merely out.
 */
export function limitStatus(reading: LimitReading): LimitStatus {
  const { min, max, current_value: current, within_limits: within, violation } = reading;

  if (current === null || within === null) {
    return { tone: 'neutral', text: 'NO DATA', icon: '·' };
  }

  const span = Math.abs(max - min) || 1;

  if (within) {
    // Inside the range, but close enough to an edge to be worth flagging.
    const margin = Math.min(current - min, max - current);
    if (margin / span < 0.05) {
      return { tone: 'warn', text: 'NEAR LIMIT', icon: '▲' };
    }
    return { tone: 'good', text: 'IN RANGE', icon: '●' };
  }

  const excess = Math.abs(violation ?? 0);
  const signedExcess = `${(violation ?? 0) > 0 ? '+' : '−'}${excess.toFixed(2)}`;
  const tone: Tone = excess > span ? 'bad' : 'warn';
  return { tone, text: `OUT OF RANGE ${signedExcess}`, icon: '▲' };
}

/**
 * Where a reading sits inside its range, as a percentage of track width, and
 * whether it fell off either end.
 *
 * The marker is clamped to the track edge when the value is outside, with the
 * overflow reported separately so the caller can print an indicator instead of
 * letting the needle silently disappear.
 */
export function rangePosition(min: number, max: number, current: number) {
  const span = max - min || 1;
  const ratio = (current - min) / span;
  return {
    percent: Math.max(0, Math.min(1, ratio)) * 100,
    overflow: ratio < 0 ? ('low' as const) : ratio > 1 ? ('high' as const) : null,
  };
}

/**
 * Recorder pens. One fixed colour per instrument, so a given tag is the same
 * pen on every trend in the app — the way a strip-chart recorder is wired.
 */
export const PEN = {
  bw: '#38BDF8', // BW.PV
  target: '#34D399', // BW.SP
  deviation: '#A78BFA', // BW.DEV
  moisture: '#22D3EE', // MOI.PV
  steam: '#F5A524', // ST.PV
  stock: '#F472B6', // SF.PV
  filler: '#2DD4BF', // FF.PV
  speed: '#94A3B8', // MS.PV
  limit: '#E5484D', // spec limits
  projection: '#F5A524', // forward extrapolation
  // Console chrome used inside SVG, where utility classes do not reach.
  grid: '#1F2937',
  axis: '#5B6672',
  scan: '#8A97A6',
  panel: '#12181F',
  inset: '#0D1218',
  bezel: '#2B3644',
  text: '#E8EDF2',
} as const;

/**
 * Instrument tag codes. Real consoles label everything with a tag alongside the
 * human name; `.PV` is a measured value, `.SP` a setpoint, `.DEV` a deviation,
 * `.ROC` a rate of change, `.STD` a variability statistic.
 */
const TAGS: Record<string, string> = {
  basis_weight_gsm: 'BW.PV',
  basis_weight_target_gsm: 'BW.SP',
  basis_weight_deviation_pct: 'BW.DEV',
  stock_flow: 'SF.PV',
  filler_flow: 'FF.PV',
  steam_pressure: 'ST.PV',
  machine_speed: 'MS.PV',
  moisture_pct: 'MOI.PV',
  ash_pct: 'ASH.PV',
  caliper_um: 'CAL.PV',
  // Derived model features.
  current_deviation_pct: 'BW.DEV',
  bw_distance_from_target: 'BW.ERR',
  bw_volatility: 'BW.STD',
  bw_deviation_rate: 'BW.ROC',
  deviation_trend: 'BW.TRND',
  moisture_volatility: 'MOI.STD',
  moisture_rate: 'MOI.ROC',
  steam_volatility: 'ST.STD',
  steam_rate: 'ST.ROC',
  stock_flow_rate: 'SF.ROC',
  time_since_start_sec: 'GC.ELAP',
  target_grade_encoded: 'GRD.TGT',
  source_grade_encoded: 'GRD.SRC',
};

/** Tag code for a variable; falls back to initials of each word. */
export const tagFor = (variable: string): string => {
  const known = TAGS[variable];
  if (known) return known;
  const parts = variable.split('_').filter(Boolean);
  return `${parts.map((part) => part.slice(0, 3).toUpperCase()).join('.')}`;
};

/** Pen colour for a variable, for charts and legend swatches. */
export const penFor = (variable: string): string => {
  const map: Record<string, string> = {
    basis_weight_gsm: PEN.bw,
    basis_weight_target_gsm: PEN.target,
    basis_weight_deviation_pct: PEN.deviation,
    stock_flow: PEN.stock,
    filler_flow: PEN.filler,
    steam_pressure: PEN.steam,
    machine_speed: PEN.speed,
    moisture_pct: PEN.moisture,
    ash_pct: PEN.filler,
    caliper_um: PEN.speed,
  };
  return map[variable] ?? PEN.speed;
};

/** Grade identity colour, reused by the scatter and the event register. */
const GRADE_PENS: Record<string, string> = {
  'Grade-A-Light': '#38BDF8',
  'Grade-B-Std': '#34D399',
  'Grade-C-Heavy': '#F5A524',
  'Grade-D-Premium': '#A78BFA',
};

export const gradeColor = (grade: string): string => GRADE_PENS[grade] ?? PEN.speed;

/** Event tag, e.g. event 46 -> `GC-0046`. */
export const eventTag = (eventId: number): string => `GC-${String(eventId).padStart(4, '0')}`;
