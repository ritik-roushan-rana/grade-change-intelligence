/**
 * Response shapes from the Grade Change Intelligence API.
 *
 * These mirror what backend/gci_api/services.py returns. No scoring or
 * derivation happens on this side -- the UI only formats and draws what the
 * Python models produced.
 */

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type Impact = 'high' | 'medium' | 'low';
export type Decision = 'accept' | 'reject';

export interface EventSummary {
  event_id: number;
  grade: string;
  max_deviation_pct: number;
  went_off_spec: boolean;
  n_operator_actions: number;
  time_to_stabilize_sec: number;
}

export interface EventsResponse {
  events: EventSummary[];
  grades: string[];
  off_spec_threshold_pct: number;
}

export interface TimelineSample {
  timestamp: string;
  grade_change_event_id: number;
  grade: string;
  phase: 'steady_state' | 'transition';
  time_since_transition_start_sec: number;
  stock_flow: number;
  filler_flow: number;
  steam_pressure: number;
  machine_speed: number;
  moisture_pct: number;
  ash_pct: number;
  caliper_um: number;
  basis_weight_gsm: number;
  basis_weight_target_gsm: number;
  basis_weight_deviation_pct: number;
  off_spec_flag: boolean;
  operator_action: string | null;
}

export interface OperatorAction {
  time_since_transition_start_sec: number;
  operator_action: string;
  basis_weight_deviation_pct: number;
}

export interface TimelineResponse {
  event: EventSummary;
  max_time_sec: number;
  sample_interval_sec: number;
  off_spec_threshold_pct: number;
  samples: TimelineSample[];
  operator_actions: OperatorAction[];
}

export interface ContributingFactor {
  variable: string;
  label: string;
  importance: number;
  current_value: number;
}

export type StatusKind = 'recovering' | 'off_spec' | 'time_to_breach' | 'within_spec';

export interface PredictionStatus {
  kind: StatusKind;
  label: string;
  value: string;
  detail: string | null;
  tone: 'good' | 'warn' | 'bad';
}

export interface PredictionResponse {
  available: boolean;
  message?: string;
  event_id: number;
  t_sec: number;
  max_time_sec: number;
  samples_elapsed: number;
  grade: string;
  off_spec_threshold_pct: number;
  risk_level: RiskLevel;
  risk_probability: number;
  current_deviation_pct: number;
  deviation_vs_spec_pct: number;
  projected_deviation_pct: number;
  time_to_breach_sec: number | null;
  window_deviation_change_pct: number;
  status: PredictionStatus;
  explanation: string;
  source: string;
  contributing_factors: ContributingFactor[];
}

export interface ProjectionPoint {
  t: number;
  deviation_pct: number;
  moisture_pct: number;
  steam_pressure: number;
}

export interface ProjectionRates {
  deviation_pct_per_60s: number;
  moisture_pct_per_60s: number;
  steam_kpa_per_60s: number;
}

export interface ProjectionResponse {
  event_id: number;
  t_sec: number;
  off_spec_threshold_pct: number;
  horizon_sec: number;
  caveat: string;
  available: boolean;
  message: string | null;
  now?: ProjectionPoint;
  actual: ProjectionPoint[];
  projected: ProjectionPoint[];
  rates: ProjectionRates | null;
}

export interface RecipeLimitCheck {
  clamped: boolean;
  within_limits: boolean | null;
  min: number | null;
  max: number | null;
  violation: number | null;
  flag_message: string | null;
}

export interface Recommendation {
  id: string;
  variable: string;
  label: string;
  current_value: number;
  recommended_value: number;
  recommended_value_original: number | null;
  change: number;
  direction: 'up' | 'down';
  unit: string;
  rationale: string;
  source: string;
  /** Engine "confidence": neighbour agreement, shown as Similarity Match. */
  similarity_match: number;
  recipe_limit: RecipeLimitCheck;
  risk_level: RiskLevel;
}

export interface RecommendationsResponse {
  available: boolean;
  event_id: number;
  t_sec: number;
  action: 'maintain' | 'adjust_setpoints' | null;
  message?: string;
  risk_level?: RiskLevel;
  estimated_recovery_time_sec?: number | null;
  similar_events_used?: number[];
  source?: string;
  recommendations: Recommendation[];
}

export interface GradePairDetail {
  grade_pair: string;
  avg_stabilize: number;
  avg_deviation: number;
  count: number;
}

export interface CorrelationFinding {
  id: string;
  title: string;
  description: string;
  correlation_strength: number | null;
  p_value: number | null;
  impact: Impact;
  source: string;
  recommendation: string;
  variables_involved: string[];
  detail_data: GradePairDetail[] | null;
}

export interface FeatureImportance {
  feature: string;
  label: string;
  importance: number;
  importance_pct: number;
  relative_pct: number;
  explanation: string;
}

export interface CorrelationsResponse {
  findings: CorrelationFinding[];
  total_findings: number;
  high_impact: number;
  medium_impact: number;
  low_impact: number;
  n_events_analyzed: number;
  feature_importances: FeatureImportance[];
  feature_importance_source: string;
}

export interface RecipeLimitVariable {
  variable: string;
  label: string;
  unit: string;
  min: number;
  max: number;
  range_label: string;
  current_value: number | null;
  within_limits: boolean | null;
  violation: number | null;
}

export interface RecipeLimitsResponse {
  grade: string;
  variables: RecipeLimitVariable[];
  source: string;
  annotated: boolean;
}

export interface OptimalSetpoint {
  variable: string;
  label: string;
  value: number;
  unit: string;
}

export interface OptimalSetpointsResponse {
  target_grade: string;
  source_grade: string | null;
  setpoints: OptimalSetpoint[];
  basis_weight_target_gsm: number | null;
  avg_stabilize_time_sec: number;
  source: string;
}

export interface FeedbackEntry {
  timestamp: string;
  event_id: number;
  risk_level: string;
  variable: string;
  recommended_value: number | string;
  current_value: number | string;
  change: number | string;
  source: string;
  decision: string;
  user_notes: string | null;
}

export interface FeedbackStats {
  total_decisions: number;
  accepted: number;
  rejected: number;
  accept_rate: number;
  reject_rate: number;
  by_variable: Record<string, number>;
}

export interface FeedbackResponse {
  entries: FeedbackEntry[];
  columns: string[];
  stats: FeedbackStats;
}

export interface FeedbackRequest {
  event_id: number;
  timestamp: number;
  recommendation_id: string;
  decision: Decision;
  user_notes?: string;
}

export interface ModelEvaluation {
  n_train_events: number;
  n_test_events: number;
  n_train_samples: number;
  n_test_samples: number;
  baseline_accuracy: number;
  test_accuracy: number;
  test_precision: number;
  test_recall: number;
  test_f1: number;
  train_accuracy: number;
  test_r2: number;
  test_mae: number;
  test_rmse: number;
  train_r2: number;
  avg_lead_time_sec: number | null;
  confusion_matrix: number[][];
}

export interface ModelInfoResponse {
  classifier: string;
  regressor: string;
  recommender: string;
  recovery_patterns: number;
  validation: string;
  evaluation: ModelEvaluation;
  startup_seconds: number | null;
}
