/**
 * Shared UI state: which event is selected, where the simulation clock sits,
 * and which suggestions have already been decided this session.
 *
 * No process data or model output lives here -- that all comes from React Query
 * so it stays in one cache with one source of truth.
 */

import { create } from 'zustand';
import type { Decision } from '../lib/types';

/** Sidebar demo presets: a typical transition and the worst case in the dataset. */
export const DEMO_PRESETS = {
  moderate: { eventId: 46, label: 'Moderate', hint: 'Event 46 — typical transition' },
  extreme: { eventId: 5, label: 'Extreme', hint: 'Event 5 — worst-case' },
} as const;

export const DEFAULT_EVENT_ID = DEMO_PRESETS.moderate.eventId;

/** The dashboard opened at 180s (or the end of a shorter event). */
export const DEFAULT_SIM_TIME = 180;
export const SIM_TIME_STEP = 15;

interface AppState {
  selectedEventId: number;
  simTime: number;
  /** recommendation id -> decision, so a suggestion is only decided once. */
  decisions: Record<string, Decision>;
  /** Ids currently in flight, for immediate button feedback. */
  pending: Record<string, true>;

  selectEvent: (eventId: number) => void;
  setSimTime: (t: number) => void;
  markPending: (recommendationId: string) => void;
  recordDecision: (recommendationId: string, decision: Decision) => void;
  clearPending: (recommendationId: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedEventId: DEFAULT_EVENT_ID,
  simTime: DEFAULT_SIM_TIME,
  decisions: {},
  pending: {},

  selectEvent: (eventId) =>
    set((state) =>
      state.selectedEventId === eventId
        ? state
        : // Changing event rewinds the clock: the previous position has no
          // meaning against a different transition.
          { ...state, selectedEventId: eventId, simTime: DEFAULT_SIM_TIME },
    ),

  setSimTime: (t) => set({ simTime: Math.max(0, Math.round(t)) }),

  markPending: (recommendationId) =>
    set((state) => ({ pending: { ...state.pending, [recommendationId]: true } })),

  recordDecision: (recommendationId, decision) =>
    set((state) => {
      const pending = { ...state.pending };
      delete pending[recommendationId];
      return { decisions: { ...state.decisions, [recommendationId]: decision }, pending };
    }),

  clearPending: (recommendationId) =>
    set((state) => {
      const pending = { ...state.pending };
      delete pending[recommendationId];
      return { pending };
    }),
}));
