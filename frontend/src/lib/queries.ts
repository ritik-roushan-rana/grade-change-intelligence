/**
 * React Query wiring.
 *
 * Slider interactions replay across a small set of discrete times (15s steps),
 * so responses are cached indefinitely: dragging back to a time already visited
 * paints instantly with no request. The underlying data is a fixed historical
 * dataset, so nothing goes stale.
 */

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { api } from './api';
import type { FeedbackRequest } from './types';

const STATIC = {
  staleTime: Infinity,
  gcTime: Infinity,
} as const;

export const queryKeys = {
  health: ['health'] as const,
  modelInfo: ['model-info'] as const,
  events: ['events'] as const,
  timeline: (eventId: number) => ['timeline', eventId] as const,
  predict: (eventId: number, t: number) => ['predict', eventId, t] as const,
  projection: (eventId: number, t: number) => ['projection', eventId, t] as const,
  recommendations: (eventId: number, t: number) => ['recommendations', eventId, t] as const,
  correlations: ['correlations'] as const,
  recipeLimits: (grade: string, eventId: number, t: number) =>
    ['recipe-limits', grade, eventId, t] as const,
  optimalSetpoints: (grade: string) => ['optimal-setpoints', grade] as const,
  feedback: ['feedback'] as const,
};

export const useEvents = () =>
  useQuery({ queryKey: queryKeys.events, queryFn: api.events, ...STATIC });

export const useModelInfo = () =>
  useQuery({ queryKey: queryKeys.modelInfo, queryFn: api.modelInfo, ...STATIC });

export const useTimeline = (eventId: number) =>
  useQuery({
    queryKey: queryKeys.timeline(eventId),
    queryFn: () => api.timeline(eventId),
    ...STATIC,
  });

export const usePrediction = (eventId: number, t: number) =>
  useQuery({
    queryKey: queryKeys.predict(eventId, t),
    queryFn: () => api.predict(eventId, t),
    // Hold the previous reading on screen while the next one loads, so dragging
    // the slider never blanks the risk card.
    placeholderData: keepPreviousData,
    ...STATIC,
  });

export const useProjection = (eventId: number, t: number) =>
  useQuery({
    queryKey: queryKeys.projection(eventId, t),
    queryFn: () => api.projection(eventId, t),
    placeholderData: keepPreviousData,
    ...STATIC,
  });

export const useRecommendations = (eventId: number, t: number) =>
  useQuery({
    queryKey: queryKeys.recommendations(eventId, t),
    queryFn: () => api.recommendations(eventId, t),
    placeholderData: keepPreviousData,
    ...STATIC,
  });

export const useCorrelations = () =>
  useQuery({ queryKey: queryKeys.correlations, queryFn: api.correlations, ...STATIC });

export const useRecipeLimits = (grade: string | undefined, eventId: number, t: number) =>
  useQuery({
    queryKey: queryKeys.recipeLimits(grade ?? '', eventId, t),
    queryFn: () => api.recipeLimits(grade as string, eventId, t),
    enabled: Boolean(grade),
    placeholderData: keepPreviousData,
    ...STATIC,
  });

export const useOptimalSetpoints = (grade: string | undefined) =>
  useQuery({
    queryKey: queryKeys.optimalSetpoints(grade ?? ''),
    queryFn: () => api.optimalSetpoints(grade as string),
    enabled: Boolean(grade),
    ...STATIC,
  });

export const useFeedback = () =>
  useQuery({
    queryKey: queryKeys.feedback,
    queryFn: api.feedback,
    // This app appends to the log at runtime, so it is the one resource that is
    // allowed to go stale and be refetched.
    staleTime: 0,
  });

export const useSubmitFeedback = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FeedbackRequest) => api.postFeedback(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.feedback });
    },
  });
};
