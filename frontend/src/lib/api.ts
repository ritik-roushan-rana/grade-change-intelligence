/**
 * Typed fetch layer for the Python API.
 *
 * Every network failure is converted into an ApiError carrying operator-facing
 * copy, so no raw fetch/JSON exception ever reaches the screen.
 */

import type {
  CorrelationsResponse,
  EventsResponse,
  FeedbackRequest,
  FeedbackResponse,
  ModelInfoResponse,
  OptimalSetpointsResponse,
  PredictionResponse,
  ProjectionResponse,
  RecipeLimitsResponse,
  RecommendationsResponse,
  TimelineResponse,
} from './types';

// In dev, Vite proxies /api to the backend, so a relative base is the default.
// Set VITE_API_BASE_URL to point a built bundle at a different host.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  readonly status: number;
  readonly unreachable: boolean;

  constructor(message: string, status: number, unreachable = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.unreachable = unreachable;
  }
}

const UNREACHABLE_MESSAGE =
  'Cannot reach the prediction service. Start the API with: cd backend && uvicorn main:app --port 8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { Accept: 'application/json', ...(init?.headers ?? {}) },
      ...init,
    });
  } catch {
    // Network-level failure: server down, wrong port, DNS. Never surface the
    // browser's own wording ("Failed to fetch") to an operator.
    throw new ApiError(UNREACHABLE_MESSAGE, 0, true);
  }

  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }

  return (await response.json()) as T;
}

async function describeFailure(response: Response): Promise<string> {
  // FastAPI puts a human-readable string in `detail`; validation errors put an
  // array there instead.
  let detail: string | null = null;
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') detail = body.detail;
    else if (Array.isArray(body?.detail) && body.detail[0]?.msg) detail = body.detail[0].msg;
  } catch {
    detail = null;
  }

  if (detail) return detail;
  if (response.status === 503) return 'The prediction service is still loading its models.';
  return `The prediction service returned an error (HTTP ${response.status}).`;
}

export const api = {
  health: () => request<{ status: string; events: number }>('/api/health'),
  modelInfo: () => request<ModelInfoResponse>('/api/model-info'),
  events: () => request<EventsResponse>('/api/events'),
  timeline: (eventId: number) => request<TimelineResponse>(`/api/events/${eventId}/timeline`),
  predict: (eventId: number, t: number) =>
    request<PredictionResponse>(`/api/events/${eventId}/predict?t=${t}`),
  projection: (eventId: number, t: number) =>
    request<ProjectionResponse>(`/api/events/${eventId}/projection?t=${t}`),
  recommendations: (eventId: number, t: number) =>
    request<RecommendationsResponse>(`/api/events/${eventId}/recommendations?t=${t}`),
  correlations: () => request<CorrelationsResponse>('/api/correlations'),
  recipeLimits: (grade: string, eventId?: number, t?: number) => {
    const query =
      eventId !== undefined && t !== undefined ? `?event_id=${eventId}&t=${t}` : '';
    return request<RecipeLimitsResponse>(
      `/api/recipe-limits/${encodeURIComponent(grade)}${query}`,
    );
  },
  optimalSetpoints: (grade: string) =>
    request<OptimalSetpointsResponse>(`/api/optimal-setpoints/${encodeURIComponent(grade)}`),
  feedback: () => request<FeedbackResponse>('/api/feedback'),
  postFeedback: (payload: FeedbackRequest) =>
    request<{ logged: boolean; recommendation_id: string }>('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
};
