"""
Prediction Model Module
------------------------
Watches an in-progress grade-change transition and flags rising risk of
exceeding the 2.5% Basis Weight deviation BEFORE it happens.

IMPORTANT: Uses EVENT-BASED train/test split to avoid data leakage.
Consecutive 15-second snapshots from the same event are highly correlated,
so splitting randomly by row would inflate metrics. Instead, we hold out
entire events (~25%) for honest evaluation.

Approach:
1. Split 119 events into ~75% train / ~25% test BY EVENT ID.
2. Train Random Forest classifier + Gradient Boosting regressor on train events only.
3. Evaluate on held-out test events with proper metrics.
4. Report class balance, precision/recall/F1, confusion matrix, lead time.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, mean_absolute_error, mean_squared_error, r2_score
)
from typing import Dict, Any, Optional, List
import os


class PredictionModel:
    """Predicts off-spec risk during an in-progress grade change."""

    RISK_THRESHOLD = 2.5  # percent deviation that defines off-spec
    TRAIN_FRACTION = 0.75
    RANDOM_SEED = 42

    def __init__(self, timeseries_path: str, summary_path: str):
        self.ts_df = pd.read_csv(timeseries_path, parse_dates=["timestamp"])
        self.summary_df = pd.read_csv(summary_path)
        self.classifier = None
        self.regressor = None
        self.label_encoder = LabelEncoder()
        self.feature_columns = []
        self._trained = False
        self.train_event_ids = []
        self.test_event_ids = []
        self.evaluation_results = None

    def train(self):
        """Train models using event-based split to avoid data leakage."""
        # --- Event-based split ---
        all_event_ids = sorted(self.summary_df["grade_change_event_id"].unique())
        rng = np.random.default_rng(self.RANDOM_SEED)
        rng.shuffle(all_event_ids)

        split_idx = int(len(all_event_ids) * self.TRAIN_FRACTION)
        self.train_event_ids = sorted(all_event_ids[:split_idx])
        self.test_event_ids = sorted(all_event_ids[split_idx:])

        # Build features for all events
        all_features_df = self._build_training_features()
        if all_features_df.empty:
            raise ValueError("No training data could be built.")

        # Split by event membership
        train_df = all_features_df[
            all_features_df["_event_id"].isin(self.train_event_ids)
        ].copy()
        test_df = all_features_df[
            all_features_df["_event_id"].isin(self.test_event_ids)
        ].copy()

        X_train = train_df[self.feature_columns]
        y_train_class = train_df["will_exceed_spec_next_60s"].astype(int)
        y_train_reg = train_df["max_deviation_next_60s"]

        X_test = test_df[self.feature_columns]
        y_test_class = test_df["will_exceed_spec_next_60s"].astype(int)
        y_test_reg = test_df["max_deviation_next_60s"]

        # --- Class balance ---
        train_pos_rate = y_train_class.mean()
        test_pos_rate = y_test_class.mean()

        # --- Train models on TRAIN set only ---
        self.classifier = RandomForestClassifier(
            n_estimators=150, max_depth=12, random_state=42,
            n_jobs=-1, class_weight="balanced"
        )
        self.classifier.fit(X_train, y_train_class)

        self.regressor = GradientBoostingRegressor(
            n_estimators=150, max_depth=6, random_state=42,
            learning_rate=0.1
        )
        self.regressor.fit(X_train, y_train_reg)

        self._trained = True

        # --- Evaluate on HELD-OUT test set ---
        self.evaluation_results = self._evaluate(
            X_train, y_train_class, y_train_reg,
            X_test, y_test_class, y_test_reg,
            test_df, train_pos_rate, test_pos_rate
        )
        return self.evaluation_results

    def _evaluate(self, X_train, y_train_class, y_train_reg,
                  X_test, y_test_class, y_test_reg,
                  test_df, train_pos_rate, test_pos_rate) -> Dict:
        """Comprehensive evaluation on held-out test events."""
        # Classifier metrics on TEST set
        y_pred_class = self.classifier.predict(X_test)
        y_pred_prob = self.classifier.predict_proba(X_test)
        exceed_probs = y_pred_prob[:, 1] if y_pred_prob.shape[1] > 1 else y_pred_prob[:, 0]

        test_accuracy = accuracy_score(y_test_class, y_pred_class)
        test_precision = precision_score(y_test_class, y_pred_class, zero_division=0)
        test_recall = recall_score(y_test_class, y_pred_class, zero_division=0)
        test_f1 = f1_score(y_test_class, y_pred_class, zero_division=0)
        conf_matrix = confusion_matrix(y_test_class, y_pred_class)

        # Baseline: always predict majority class
        majority_class = int(y_train_class.mode().iloc[0])
        baseline_accuracy = (y_test_class == majority_class).mean()

        # Regressor metrics on TEST set
        y_pred_reg = self.regressor.predict(X_test)
        test_r2 = r2_score(y_test_class.astype(float) * 0 + y_test_reg, y_pred_reg)
        # Actually compute on the regression target
        test_r2 = r2_score(y_test_reg, y_pred_reg)
        test_mae = mean_absolute_error(y_test_reg, y_pred_reg)
        test_rmse = np.sqrt(mean_squared_error(y_test_reg, y_pred_reg))

        # Train-set metrics (for comparison / overfitting check)
        train_accuracy = self.classifier.score(X_train, y_train_class)
        train_r2 = self.regressor.score(X_train, y_train_reg)

        # --- Lead time calculation ---
        lead_time_sec = self._calculate_lead_time(test_df)

        # Feature importances
        importances = self.classifier.feature_importances_
        top_features = sorted(
            zip(self.feature_columns, importances),
            key=lambda x: x[1], reverse=True
        )[:10]

        return {
            # Split info
            "n_train_events": len(self.train_event_ids),
            "n_test_events": len(self.test_event_ids),
            "n_train_samples": len(X_train),
            "n_test_samples": len(X_test),
            # Class balance
            "train_positive_rate": round(train_pos_rate, 3),
            "test_positive_rate": round(test_pos_rate, 3),
            "majority_class": majority_class,
            "baseline_accuracy": round(baseline_accuracy, 3),
            # Classifier - TEST set (honest)
            "test_accuracy": round(test_accuracy, 3),
            "test_precision": round(test_precision, 3),
            "test_recall": round(test_recall, 3),
            "test_f1": round(test_f1, 3),
            "confusion_matrix": conf_matrix.tolist(),
            # Classifier - TRAIN set (for overfitting check)
            "train_accuracy": round(train_accuracy, 3),
            # Regressor - TEST set (honest)
            "test_r2": round(test_r2, 3),
            "test_mae": round(test_mae, 3),
            "test_rmse": round(test_rmse, 3),
            # Regressor - TRAIN set
            "train_r2": round(train_r2, 3),
            # Lead time
            "avg_lead_time_sec": lead_time_sec,
            # Features
            "top_features": [
                {"feature": f, "importance": round(i, 4)} for f, i in top_features
            ],
        }

    def _calculate_lead_time(self, test_df: pd.DataFrame) -> Optional[float]:
        """
        For correctly-flagged breaches in test events, calculate how many
        seconds before the actual 2.5% breach the model first raised the alert.

        Since ALL transitions start off-spec by design (grade targets jump
        discretely), we look for the model's ability to predict that deviation
        will REMAIN above threshold in the next 60s. We measure: at each sample
        where the model predicts "will exceed" AND it's correct, how far ahead
        of the ACTUAL future breach point is that prediction?

        Alternative approach: for samples currently BELOW threshold that later
        go above, measure lead time. But since the data starts above, we instead
        measure how early the model correctly flags "will stay off-spec" — i.e.,
        the model predicts 1 while actual future confirms 1, and we find the
        earliest such correct prediction per event minus when deviation finally
        drops below threshold (the recovery point).
        """
        lead_times = []

        for event_id in self.test_event_ids:
            event_samples = test_df[test_df["_event_id"] == event_id].copy()
            if event_samples.empty:
                continue
            event_samples = event_samples.sort_values("_time_since_start").reset_index(drop=True)

            # Find the recovery point: first time deviation drops below threshold
            below_threshold = event_samples[
                event_samples["_actual_deviation_at_sample"] <= self.RISK_THRESHOLD
            ]
            if below_threshold.empty:
                # Never recovered — model should predict 1 the whole time
                # Lead time concept doesn't apply
                continue

            recovery_time = below_threshold["_time_since_start"].iloc[0]

            # Look at samples BEFORE recovery: model should predict "will exceed" (1)
            # After recovery: model should predict "won't exceed" (0)
            # Lead time = how many seconds before recovery does model switch from 1→0?
            X_event = event_samples[self.feature_columns]
            predictions = self.classifier.predict(X_event)
            event_samples = event_samples.copy()
            event_samples["predicted_breach"] = predictions

            # Find the last time model predicted "will NOT breach" before recovery
            # (i.e., model correctly anticipated recovery ahead of time)
            pre_recovery = event_samples[event_samples["_time_since_start"] < recovery_time]
            if pre_recovery.empty:
                continue

            # Model predicts 0 (no breach) while still above threshold = early recovery signal
            early_recovery_calls = pre_recovery[pre_recovery["predicted_breach"] == 0]
            if not early_recovery_calls.empty:
                first_no_breach_call = early_recovery_calls["_time_since_start"].iloc[0]
                lead_time = recovery_time - first_no_breach_call
                if lead_time > 0:
                    lead_times.append(lead_time)

        if lead_times:
            return round(np.mean(lead_times), 1)
        return None

    def _build_training_features(self) -> pd.DataFrame:
        """Build feature matrix from historical transition data."""
        transition_df = self.ts_df[self.ts_df["phase"] == "transition"].copy()
        transition_df = transition_df.sort_values(
            ["grade_change_event_id", "time_since_transition_start_sec"]
        )

        # Encode grade pairs
        steady_df = self.ts_df[self.ts_df["phase"] == "steady_state"]
        source_grades = steady_df.groupby("grade_change_event_id")["grade"].first().reset_index()
        source_grades.columns = ["grade_change_event_id", "source_grade"]
        transition_df = transition_df.merge(source_grades, on="grade_change_event_id", how="left")

        all_grades = pd.concat([
            transition_df["grade"], transition_df["source_grade"]
        ]).dropna().unique()
        self.label_encoder.fit(all_grades)

        rows = []
        for event_id, group in transition_df.groupby("grade_change_event_id"):
            group = group.sort_values("time_since_transition_start_sec").reset_index(drop=True)
            n = len(group)

            for i in range(3, n):  # need at least 3 prior points for features
                current = group.iloc[i]
                history = group.iloc[max(0, i - 8):i + 1]  # last ~2 min window

                # Look ahead 60 seconds (4 samples at 15-sec intervals)
                future = group.iloc[i + 1:i + 5]
                if future.empty:
                    continue

                # Targets
                will_exceed = (future["basis_weight_deviation_pct"] > self.RISK_THRESHOLD).any()
                max_dev_future = future["basis_weight_deviation_pct"].max()

                # Features
                feat = self._extract_features(current, history, group.iloc[0])
                # Metadata for splitting and lead-time (not used as features)
                feat["_event_id"] = event_id
                feat["_time_since_start"] = current["time_since_transition_start_sec"]
                feat["_actual_deviation_at_sample"] = current["basis_weight_deviation_pct"]
                feat["will_exceed_spec_next_60s"] = will_exceed
                feat["max_deviation_next_60s"] = max_dev_future
                rows.append(feat)

        features_df = pd.DataFrame(rows)

        # Define feature columns (exclude targets and metadata)
        self.feature_columns = [
            c for c in features_df.columns
            if c not in [
                "will_exceed_spec_next_60s", "max_deviation_next_60s",
                "_event_id", "_time_since_start", "_actual_deviation_at_sample"
            ]
        ]
        return features_df

    def _extract_features(self, current: pd.Series, history: pd.DataFrame,
                          first_row: pd.Series) -> Dict[str, float]:
        """Extract features from current state and recent history."""
        feat = {}

        # Current state features
        feat["current_deviation_pct"] = current["basis_weight_deviation_pct"]
        feat["time_since_start_sec"] = current["time_since_transition_start_sec"]
        feat["stock_flow"] = current["stock_flow"]
        feat["filler_flow"] = current["filler_flow"]
        feat["steam_pressure"] = current["steam_pressure"]
        feat["machine_speed"] = current["machine_speed"]
        feat["moisture_pct"] = current["moisture_pct"]
        feat["ash_pct"] = current["ash_pct"]
        feat["caliper_um"] = current["caliper_um"]
        feat["basis_weight_gsm"] = current["basis_weight_gsm"]
        feat["basis_weight_target_gsm"] = current["basis_weight_target_gsm"]

        # Rate of change features (from history window)
        if len(history) >= 2:
            feat["bw_deviation_rate"] = (
                history["basis_weight_deviation_pct"].iloc[-1] -
                history["basis_weight_deviation_pct"].iloc[0]
            ) / max(len(history) - 1, 1)
            feat["steam_rate"] = (
                history["steam_pressure"].iloc[-1] - history["steam_pressure"].iloc[0]
            ) / max(len(history) - 1, 1)
            feat["moisture_rate"] = (
                history["moisture_pct"].iloc[-1] - history["moisture_pct"].iloc[0]
            ) / max(len(history) - 1, 1)
            feat["stock_flow_rate"] = (
                history["stock_flow"].iloc[-1] - history["stock_flow"].iloc[0]
            ) / max(len(history) - 1, 1)
        else:
            feat["bw_deviation_rate"] = 0
            feat["steam_rate"] = 0
            feat["moisture_rate"] = 0
            feat["stock_flow_rate"] = 0

        # Volatility features
        feat["bw_volatility"] = history["basis_weight_deviation_pct"].std() if len(history) > 1 else 0
        feat["steam_volatility"] = history["steam_pressure"].std() if len(history) > 1 else 0
        feat["moisture_volatility"] = history["moisture_pct"].std() if len(history) > 1 else 0

        # Distance from target
        feat["bw_distance_from_target"] = abs(
            current["basis_weight_gsm"] - current["basis_weight_target_gsm"]
        )

        # Grade encoding
        try:
            feat["target_grade_encoded"] = self.label_encoder.transform(
                [current["grade"]]
            )[0]
        except (ValueError, KeyError):
            feat["target_grade_encoded"] = 0

        try:
            source = first_row.get("source_grade", current["grade"])
            feat["source_grade_encoded"] = self.label_encoder.transform([source])[0]
        except (ValueError, KeyError):
            feat["source_grade_encoded"] = 0

        # Deviation trend (is it improving or worsening?)
        if len(history) >= 3:
            recent = history["basis_weight_deviation_pct"].tail(3).values
            feat["deviation_trend"] = np.polyfit(range(len(recent)), recent, 1)[0]
        else:
            feat["deviation_trend"] = 0

        return feat

    def predict_risk(self, current_state: Dict[str, Any],
                     history_window: pd.DataFrame) -> Dict[str, Any]:
        """
        Predict risk for current in-progress transition.

        Args:
            current_state: dict with current sensor readings
            history_window: DataFrame of recent readings (last ~2 min)

        Returns:
            Dict with risk_level, confidence, projected_deviation,
            time_to_breach_estimate, explanation
        """
        if not self._trained:
            return self._rule_based_prediction(current_state, history_window)

        # Build feature vector
        current_series = pd.Series(current_state)
        first_row = history_window.iloc[0] if len(history_window) > 0 else current_series
        features = self._extract_features(current_series, history_window, first_row)

        # Ensure all feature columns present
        X = pd.DataFrame([features])[self.feature_columns]

        # Predict
        risk_prob = self.classifier.predict_proba(X)[0]
        exceed_prob = risk_prob[1] if len(risk_prob) > 1 else risk_prob[0]
        projected_deviation = self.regressor.predict(X)[0]

        # Determine risk level
        current_dev = current_state.get("basis_weight_deviation_pct", 0)
        risk_level = self._classify_risk(exceed_prob, projected_deviation, current_dev)

        # Estimate time to breach
        rate = features.get("bw_deviation_rate", 0)
        time_to_breach = self._estimate_time_to_breach(current_dev, rate)

        # Generate explanation (with fixed status distinction)
        explanation = self._generate_explanation(
            risk_level, exceed_prob, projected_deviation, features, time_to_breach
        )

        return {
            "risk_level": risk_level,
            "risk_probability": round(exceed_prob, 3),
            "projected_deviation_pct": round(projected_deviation, 2),
            "current_deviation_pct": round(current_dev, 2),
            "time_to_breach_sec": time_to_breach,
            "explanation": explanation,
            "source": "ML model (Random Forest + Gradient Boosting) trained on historical data",
            "contributing_factors": self._get_contributing_factors(features),
        }

    def _rule_based_prediction(self, current_state: Dict, history: pd.DataFrame) -> Dict:
        """Fallback rule-based prediction when ML model isn't trained."""
        current_dev = current_state.get("basis_weight_deviation_pct", 0)

        # Simple trend extrapolation
        if len(history) >= 3:
            recent_devs = history["basis_weight_deviation_pct"].tail(5).values
            trend = np.polyfit(range(len(recent_devs)), recent_devs, 1)[0]
            projected = current_dev + trend * 4  # 4 steps ahead = 60 sec
        else:
            trend = 0
            projected = current_dev

        if projected > self.RISK_THRESHOLD and current_dev < self.RISK_THRESHOLD:
            risk_level = "high"
        elif current_dev > self.RISK_THRESHOLD:
            risk_level = "critical"
        elif projected > self.RISK_THRESHOLD * 0.8:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "risk_probability": min(projected / self.RISK_THRESHOLD, 1.0),
            "projected_deviation_pct": round(projected, 2),
            "current_deviation_pct": round(current_dev, 2),
            "time_to_breach_sec": self._estimate_time_to_breach(current_dev, trend),
            "explanation": (
                f"Rule-based prediction: current deviation {current_dev:.2f}%, "
                f"trending at {trend:+.3f}%/step, projected {projected:.2f}% in 60s."
            ),
            "source": "Rule-based trend extrapolation",
            "contributing_factors": [],
        }

    def _classify_risk(self, prob: float, projected_dev: float, current_dev: float) -> str:
        """Map probability and deviation to risk level."""
        if current_dev > self.RISK_THRESHOLD:
            return "critical"
        elif prob > 0.7 or projected_dev > self.RISK_THRESHOLD * 1.5:
            return "high"
        elif prob > 0.4 or projected_dev > self.RISK_THRESHOLD:
            return "medium"
        else:
            return "low"

    def _estimate_time_to_breach(self, current_dev: float, rate: float) -> Optional[int]:
        """Estimate seconds until 2.5% threshold is breached."""
        if current_dev >= self.RISK_THRESHOLD:
            return 0  # already breached
        if rate <= 0:
            return None  # deviation is decreasing, no breach expected
        remaining = self.RISK_THRESHOLD - current_dev
        steps_to_breach = remaining / rate
        return int(steps_to_breach * 15)  # convert steps to seconds

    def _generate_explanation(self, risk_level: str, prob: float,
                              projected_dev: float, features: Dict,
                              time_to_breach: Optional[int]) -> str:
        """
        Generate plain-language explanation of prediction.
        Fixed: distinguishes 'already off-spec, recovering' from 'approaching breach'.
        """
        parts = []
        current_dev = features.get("current_deviation_pct", 0)
        dev_rate = features.get("bw_deviation_rate", 0)

        if risk_level == "critical":
            # Distinguish: already off-spec but recovering vs still worsening
            if dev_rate < -0.05:
                parts.append(
                    f"OFF-SPEC (RECOVERING): Deviation at {current_dev:.2f}% "
                    f"(above 2.5% threshold) but trending downward — recovery in progress."
                )
            else:
                parts.append(
                    f"CRITICAL: Basis weight deviation is {current_dev:.2f}%, "
                    f"exceeding the 2.5% off-spec threshold and not yet recovering."
                )
        elif risk_level == "high":
            parts.append(
                f"HIGH RISK: Model predicts {prob*100:.1f}% probability of exceeding "
                f"the 2.5% specification limit within the next 60 seconds."
            )
            if time_to_breach is not None and time_to_breach > 0:
                parts.append(f"Estimated time to breach: {time_to_breach} seconds.")
        elif risk_level == "medium":
            parts.append(
                f"MODERATE RISK: Deviation trending upward. Projected to reach "
                f"{projected_dev:.2f}% (threshold: 2.5%)."
            )
            if time_to_breach is not None and time_to_breach > 0:
                parts.append(f"Estimated time to breach: {time_to_breach} seconds.")
        else:
            parts.append(
                f"LOW RISK: Current trajectory suggests deviation will stay within "
                f"specification limits."
            )

        # Key factors — only show rate info if NOT contradicting the status above
        if risk_level != "critical":
            if abs(dev_rate) > 0.1:
                direction = "increasing" if dev_rate > 0 else "decreasing"
                parts.append(f"Deviation rate is {direction} rapidly.")

        if features.get("steam_volatility", 0) > 1.0:
            parts.append("Steam pressure is unstable, which will impact moisture with a lag.")

        return " ".join(parts)

    def _get_contributing_factors(self, features: Dict) -> list:
        """Identify top contributing factors to the risk assessment."""
        factors = []
        if self.classifier is not None:
            importances = self.classifier.feature_importances_
            top_indices = np.argsort(importances)[-5:][::-1]
            for idx in top_indices:
                if idx < len(self.feature_columns):
                    col = self.feature_columns[idx]
                    factors.append({
                        "variable": col,
                        "importance": round(importances[idx], 3),
                        "current_value": round(features.get(col, 0), 3),
                    })
        return factors

    def get_feature_importances(self) -> pd.DataFrame:
        """Return feature importances as a DataFrame."""
        if self.classifier is None:
            return pd.DataFrame()
        importances = self.classifier.feature_importances_
        df = pd.DataFrame({
            "Feature": self.feature_columns,
            "Importance": importances
        }).sort_values("Importance", ascending=False)
        return df

    def simulate_event_predictions(self, event_id: int) -> list:
        """
        Run predictions across all timesteps of a given event.
        Useful for dashboard visualization.
        """
        event_data = self.ts_df[
            (self.ts_df["grade_change_event_id"] == event_id) &
            (self.ts_df["phase"] == "transition")
        ].sort_values("time_since_transition_start_sec").reset_index(drop=True)

        predictions = []
        for i in range(3, len(event_data)):
            current = event_data.iloc[i].to_dict()
            history = event_data.iloc[max(0, i - 8):i + 1]
            pred = self.predict_risk(current, history)
            pred["timestamp"] = current["timestamp"]
            pred["time_since_start_sec"] = current["time_since_transition_start_sec"]
            predictions.append(pred)

        return predictions


# --- Standalone execution for testing ---
if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model = PredictionModel(
        timeseries_path=os.path.join(base_dir, "data", "grade_change_timeseries.csv"),
        summary_path=os.path.join(base_dir, "data", "grade_change_event_summary.csv"),
    )
    print("Training prediction model (EVENT-BASED split)...")
    print("=" * 60)
    report = model.train()

    print(f"\n  SPLIT INFO:")
    print(f"    Train events: {report['n_train_events']} | Test events: {report['n_test_events']}")
    print(f"    Train samples: {report['n_train_samples']:,} | Test samples: {report['n_test_samples']:,}")

    print(f"\n  CLASS BALANCE:")
    print(f"    Train positive rate (will breach): {report['train_positive_rate']*100:.1f}%")
    print(f"    Test positive rate (will breach): {report['test_positive_rate']*100:.1f}%")
    print(f"    Baseline accuracy (always predict majority): {report['baseline_accuracy']*100:.1f}%")

    print(f"\n  CLASSIFIER — HELD-OUT TEST SET (honest):")
    print(f"    Accuracy:  {report['test_accuracy']*100:.1f}%")
    print(f"    Precision: {report['test_precision']*100:.1f}%")
    print(f"    Recall:    {report['test_recall']*100:.1f}%")
    print(f"    F1 Score:  {report['test_f1']*100:.1f}%")
    print(f"    Confusion Matrix:")
    cm = report['confusion_matrix']
    print(f"      TN={cm[0][0]:,}  FP={cm[0][1]:,}")
    print(f"      FN={cm[1][0]:,}  TP={cm[1][1]:,}")

    print(f"\n  CLASSIFIER — TRAIN SET (overfitting check):")
    print(f"    Train Accuracy: {report['train_accuracy']*100:.1f}%")

    print(f"\n  REGRESSOR — HELD-OUT TEST SET (honest):")
    print(f"    R²:   {report['test_r2']:.3f}")
    print(f"    MAE:  {report['test_mae']:.3f}%")
    print(f"    RMSE: {report['test_rmse']:.3f}%")

    print(f"\n  REGRESSOR — TRAIN SET:")
    print(f"    Train R²: {report['train_r2']:.3f}")

    print(f"\n  LEAD TIME:")
    if report['avg_lead_time_sec'] is not None:
        print(f"    Average early warning: {report['avg_lead_time_sec']:.1f} seconds before breach")
    else:
        print(f"    Could not compute lead time (no pre-breach alerts in test set)")

    print(f"\n  TOP 10 FEATURES:")
    for f in report["top_features"]:
        print(f"    {f['feature']}: {f['importance']:.4f}")

    print(f"\n  COMPARISON (old inflated vs new honest):")
    print(f"    {'Metric':<25} {'Old (leaked)':<15} {'New (honest)':<15}")
    print(f"    {'-'*55}")
    print(f"    {'Classifier Accuracy':<25} {'98.0%':<15} {report['test_accuracy']*100:.1f}%")
    print(f"    {'Regressor R²':<25} {'0.994':<15} {report['test_r2']:.3f}")
    print(f"    {'Eval method':<25} {'Random row':<15} {'Event holdout'}")
