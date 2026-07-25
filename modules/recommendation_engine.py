"""
Recommendation Engine Module
------------------------------
When a risk is flagged, suggests specific setpoint adjustments matched from
similar historical transitions that recovered fastest.

Approach:
1. Build a library of "recovery patterns" — historical moments where deviation
   was high but the system successfully recovered quickly.
2. When risk is flagged, find the most similar historical situation by matching
   on: grade pair, deviation magnitude, process variable states.
3. Recommend the setpoint adjustments that worked in those similar recoveries.
4. Validate recommendations against per-grade recipe limits.
5. Tag every recommendation with its source of inference.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import os
import json
from datetime import datetime
from .recipe_limits import validate_recommendation, get_limits_for_grade


class RecommendationEngine:
    """Generates actionable recommendations based on historical recovery patterns."""

    def __init__(self, timeseries_path: str, summary_path: str):
        self.ts_df = pd.read_csv(timeseries_path, parse_dates=["timestamp"])
        self.summary_df = pd.read_csv(summary_path)
        self.recovery_library = None
        self.knn_model = None
        self.scaler = StandardScaler()
        self.feature_cols = [
            "basis_weight_deviation_pct", "stock_flow", "filler_flow",
            "steam_pressure", "machine_speed", "moisture_pct"
        ]
        self._built = False

    def build_recovery_library(self):
        """
        Build a library of recovery patterns from historical data.
        A 'recovery' is defined as a window where deviation went from high (>2.5%)
        back to low (<2.5%) — we capture the setpoint adjustments that happened.
        """
        transition_df = self.ts_df[self.ts_df["phase"] == "transition"].copy()
        transition_df = transition_df.sort_values(
            ["grade_change_event_id", "time_since_transition_start_sec"]
        )

        # Get source grades
        steady_df = self.ts_df[self.ts_df["phase"] == "steady_state"]
        source_grades = steady_df.groupby("grade_change_event_id")["grade"].first().reset_index()
        source_grades.columns = ["grade_change_event_id", "source_grade"]
        transition_df = transition_df.merge(source_grades, on="grade_change_event_id", how="left")

        recovery_patterns = []

        for event_id, group in transition_df.groupby("grade_change_event_id"):
            group = group.sort_values("time_since_transition_start_sec").reset_index(drop=True)

            # Find recovery moments (transition from off-spec to on-spec)
            for i in range(1, len(group)):
                prev_off = group.iloc[i - 1]["basis_weight_deviation_pct"] > 2.5
                curr_on = group.iloc[i]["basis_weight_deviation_pct"] <= 2.5

                if prev_off and curr_on:
                    # This is a recovery point — capture context
                    # Look at what happened 30-120 seconds before recovery
                    recovery_time = group.iloc[i]["time_since_transition_start_sec"]
                    pre_recovery = group[
                        (group["time_since_transition_start_sec"] >= recovery_time - 120) &
                        (group["time_since_transition_start_sec"] < recovery_time)
                    ]

                    if len(pre_recovery) < 2:
                        continue

                    # The state at peak deviation (before recovery started)
                    peak_idx = pre_recovery["basis_weight_deviation_pct"].idxmax()
                    peak_state = pre_recovery.loc[peak_idx]

                    # The state at recovery completion
                    recovered_state = group.iloc[i]

                    # Calculate the setpoint changes that led to recovery
                    setpoint_changes = {
                        "stock_flow_change": recovered_state["stock_flow"] - peak_state["stock_flow"],
                        "filler_flow_change": recovered_state["filler_flow"] - peak_state["filler_flow"],
                        "steam_pressure_change": recovered_state["steam_pressure"] - peak_state["steam_pressure"],
                        "machine_speed_change": recovered_state["machine_speed"] - peak_state["machine_speed"],
                    }

                    # Time it took to recover
                    recovery_duration = (
                        recovered_state["time_since_transition_start_sec"] -
                        peak_state["time_since_transition_start_sec"]
                    )

                    # Get stabilization time for this event
                    event_summary = self.summary_df[
                        self.summary_df["grade_change_event_id"] == event_id
                    ]
                    stabilize_time = (
                        event_summary["time_to_stabilize_sec"].values[0]
                        if len(event_summary) > 0 else 9999
                    )

                    recovery_patterns.append({
                        "event_id": event_id,
                        "grade": peak_state["grade"],
                        "source_grade": peak_state.get("source_grade", "Unknown"),
                        "peak_deviation_pct": peak_state["basis_weight_deviation_pct"],
                        "peak_stock_flow": peak_state["stock_flow"],
                        "peak_filler_flow": peak_state["filler_flow"],
                        "peak_steam_pressure": peak_state["steam_pressure"],
                        "peak_machine_speed": peak_state["machine_speed"],
                        "peak_moisture_pct": peak_state["moisture_pct"],
                        "recovery_duration_sec": recovery_duration,
                        "event_stabilize_time_sec": stabilize_time,
                        **setpoint_changes,
                        "basis_weight_target_gsm": peak_state["basis_weight_target_gsm"],
                    })

        self.recovery_library = pd.DataFrame(recovery_patterns)

        # Fit KNN on recovery patterns for similarity search
        if len(self.recovery_library) > 5:
            knn_features = self.recovery_library[[
                "peak_deviation_pct", "peak_stock_flow", "peak_filler_flow",
                "peak_steam_pressure", "peak_machine_speed", "peak_moisture_pct"
            ]].values
            self.scaler.fit(knn_features)
            scaled = self.scaler.transform(knn_features)
            self.knn_model = NearestNeighbors(n_neighbors=min(5, len(scaled)), metric="euclidean")
            self.knn_model.fit(scaled)
            self._built = True

        return len(self.recovery_library)

    def recommend(self, current_state: Dict[str, Any],
                  risk_prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate recommendation based on current state and risk prediction.

        Args:
            current_state: dict with current process variable readings
            risk_prediction: output from PredictionModel.predict_risk()

        Returns:
            Dict with recommended setpoints, rationale, and source tags
        """
        if not self._built or self.recovery_library is None or self.recovery_library.empty:
            return self._rule_based_recommendation(current_state, risk_prediction)

        risk_level = risk_prediction.get("risk_level", "low")

        if risk_level == "low":
            return {
                "action": "maintain",
                "message": "System within specification. No action required.",
                "risk_level": risk_level,
                "recommendations": [],
                "source": "No recommendation needed - system stable",
            }

        # Find similar historical situations
        similar_recoveries = self._find_similar_recoveries(current_state)

        if similar_recoveries.empty:
            return self._rule_based_recommendation(current_state, risk_prediction)

        # Compute recommended setpoints from the best recoveries
        # Weight by inverse of recovery duration (faster recoveries get more weight)
        weights = 1.0 / (similar_recoveries["recovery_duration_sec"] + 1)
        weights = weights / weights.sum()

        recommendations = []

        # Helper: compute consistency-based confidence (renamed "Similarity Match")
        # High confidence = neighbors agree on direction AND have low variance in outcome
        def _compute_confidence(changes: pd.Series, distances: pd.Series) -> float:
            """
            Confidence based on:
            1. Direction agreement: what fraction of neighbors agree on +/- direction?
            2. Magnitude consistency: low CoV in the change values = more confidence
            3. Proximity: closer neighbors (lower distance) = more confidence
            Returns a score in [0.50, 0.98] range.
            """
            if len(changes) < 2:
                return 0.60

            # Direction agreement (0 to 1): fraction with same sign as weighted mean
            mean_change = (changes * weights[:len(changes)]).sum()
            if abs(mean_change) < 1e-9:
                direction_score = 0.5
            else:
                same_sign = (np.sign(changes) == np.sign(mean_change)).mean()
                direction_score = same_sign  # 0.4 to 1.0 typically

            # Magnitude consistency: 1 - normalized CoV (capped)
            std_change = changes.std()
            mean_abs = abs(changes).mean()
            if mean_abs > 1e-9:
                cov = min(std_change / mean_abs, 2.0)  # cap at 2
                consistency_score = 1.0 - (cov / 2.0)  # maps [0,2] -> [1.0, 0.0]
            else:
                consistency_score = 0.5

            # Proximity score: inverse of mean distance, normalized
            mean_dist = distances.mean()
            # Empirically, distances range 0-5 in scaled space
            proximity_score = max(0, 1.0 - mean_dist / 5.0)

            # Weighted combination
            raw = (direction_score * 0.45 +
                   consistency_score * 0.35 +
                   proximity_score * 0.20)

            # Scale to [0.50, 0.98] for display (avoid showing <50% which reads as bad)
            return round(0.50 + raw * 0.48, 2)

        neighbor_distances = similar_recoveries.get("similarity_distance", pd.Series([1.0]))

        # Stock flow recommendation
        avg_stock_change = (similar_recoveries["stock_flow_change"] * weights).sum()
        if abs(avg_stock_change) > 0.5:
            target_stock = current_state.get("stock_flow", 100) + avg_stock_change
            conf = _compute_confidence(
                similar_recoveries["stock_flow_change"], neighbor_distances
            )
            recommendations.append({
                "variable": "stock_flow",
                "current_value": round(current_state.get("stock_flow", 100), 2),
                "recommended_value": round(target_stock, 2),
                "change": round(avg_stock_change, 2),
                "unit": "units",
                "rationale": (
                    f"Based on {len(similar_recoveries)} similar historical recoveries, "
                    f"adjusting stock flow by {avg_stock_change:+.2f} helped reduce deviation. "
                    f"Average recovery time in similar cases: "
                    f"{similar_recoveries['recovery_duration_sec'].mean():.0f}s."
                ),
                "confidence": conf,
                "source": "Historical recovery pattern matching (KNN similarity search)",
            })

        # Steam pressure recommendation
        avg_steam_change = (similar_recoveries["steam_pressure_change"] * weights).sum()
        if abs(avg_steam_change) > 0.3:
            target_steam = current_state.get("steam_pressure", 300) + avg_steam_change
            conf = _compute_confidence(
                similar_recoveries["steam_pressure_change"], neighbor_distances
            )
            recommendations.append({
                "variable": "steam_pressure",
                "current_value": round(current_state.get("steam_pressure", 300), 2),
                "recommended_value": round(target_steam, 2),
                "change": round(avg_steam_change, 2),
                "unit": "kPa",
                "rationale": (
                    f"Steam pressure adjustment of {avg_steam_change:+.2f} kPa was effective "
                    f"in similar scenarios. Note: steam affects moisture with a ~60s lag, "
                    f"so act early."
                ),
                "confidence": conf,
                "source": "Historical recovery pattern matching + steam-moisture lag correlation",
            })

        # Filler flow recommendation
        avg_filler_change = (similar_recoveries["filler_flow_change"] * weights).sum()
        if abs(avg_filler_change) > 0.2:
            target_filler = current_state.get("filler_flow", 20) + avg_filler_change
            conf = _compute_confidence(
                similar_recoveries["filler_flow_change"], neighbor_distances
            )
            recommendations.append({
                "variable": "filler_flow",
                "current_value": round(current_state.get("filler_flow", 20), 2),
                "recommended_value": round(target_filler, 2),
                "change": round(avg_filler_change, 2),
                "unit": "units",
                "rationale": (
                    f"Filler flow change of {avg_filler_change:+.2f} observed in "
                    f"successful recoveries with similar ash deviation patterns."
                ),
                "confidence": conf,
                "source": "Historical recovery pattern matching + filler-ash correlation",
            })

        # Machine speed recommendation
        avg_speed_change = (similar_recoveries["machine_speed_change"] * weights).sum()
        if abs(avg_speed_change) > 0.5:
            target_speed = current_state.get("machine_speed", 900) + avg_speed_change
            conf = _compute_confidence(
                similar_recoveries["machine_speed_change"], neighbor_distances
            )
            recommendations.append({
                "variable": "machine_speed",
                "current_value": round(current_state.get("machine_speed", 900), 2),
                "recommended_value": round(target_speed, 2),
                "change": round(avg_speed_change, 2),
                "unit": "m/min",
                "rationale": (
                    f"Machine speed adjustment of {avg_speed_change:+.2f} m/min helped "
                    f"in historically similar transitions."
                ),
                "confidence": conf,
                "source": "Historical recovery pattern matching",
            })

        # If no specific recommendations found
        if not recommendations:
            return self._rule_based_recommendation(current_state, risk_prediction)

        # Validate recommendations against recipe limits
        grade = current_state.get("grade", "")
        for rec in recommendations:
            check = validate_recommendation(grade, rec["variable"], rec["recommended_value"])
            rec["recipe_limit_check"] = check
            if check["flagged"]:
                # Clamp recommendation to recipe limit
                limits = get_limits_for_grade(grade).get(rec["variable"])
                if limits:
                    lo, hi = limits
                    clamped = max(lo, min(hi, rec["recommended_value"]))
                    rec["recommended_value_original"] = rec["recommended_value"]
                    rec["recommended_value"] = round(clamped, 2)
                    rec["change"] = round(clamped - rec["current_value"], 2)
                    rec["source"] += " | Clamped to recipe limits"
                    rec["rationale"] += (
                        f" (Note: original suggestion clamped from "
                        f"{rec['recommended_value_original']:.2f} to {clamped:.2f} "
                        f"to stay within recipe limits [{lo}, {hi}].)"
                    )

        # Estimated improvement
        avg_recovery_time = similar_recoveries["recovery_duration_sec"].mean()

        return {
            "action": "adjust_setpoints",
            "message": (
                f"Risk level: {risk_level.upper()}. Recommending setpoint adjustments "
                f"based on {len(similar_recoveries)} similar historical recoveries "
                f"(avg recovery time: {avg_recovery_time:.0f}s)."
            ),
            "risk_level": risk_level,
            "recommendations": recommendations,
            "estimated_recovery_time_sec": round(avg_recovery_time),
            "similar_events_used": similar_recoveries["event_id"].tolist(),
            "source": "Historical KNN-based recovery pattern matching + Recipe limits",
        }

    def _find_similar_recoveries(self, current_state: Dict) -> pd.DataFrame:
        """Find the most similar historical recovery patterns to current state."""
        query = np.array([[
            current_state.get("basis_weight_deviation_pct", 0),
            current_state.get("stock_flow", 100),
            current_state.get("filler_flow", 20),
            current_state.get("steam_pressure", 300),
            current_state.get("machine_speed", 900),
            current_state.get("moisture_pct", 6.5),
        ]])
        scaled_query = self.scaler.transform(query)
        distances, indices = self.knn_model.kneighbors(scaled_query)

        similar = self.recovery_library.iloc[indices[0]].copy()
        similar["similarity_distance"] = distances[0]

        # Filter to only reasonably similar ones (distance < 3 std deviations)
        threshold = distances[0].mean() + 2 * distances[0].std() if len(distances[0]) > 1 else 10
        similar = similar[similar["similarity_distance"] <= threshold]

        # Prefer faster recoveries
        similar = similar.sort_values("recovery_duration_sec")
        return similar

    def _rule_based_recommendation(self, current_state: Dict,
                                   risk_prediction: Dict) -> Dict:
        """Fallback rule-based recommendations when no similar patterns found."""
        recommendations = []
        risk_level = risk_prediction.get("risk_level", "medium")
        current_dev = current_state.get("basis_weight_deviation_pct", 0)
        bw = current_state.get("basis_weight_gsm", 60)
        target = current_state.get("basis_weight_target_gsm", 60)

        # If basis weight is below target, increase stock flow
        if bw < target:
            change = min((target - bw) * 0.3, 5.0)
            recommendations.append({
                "variable": "stock_flow",
                "current_value": round(current_state.get("stock_flow", 100), 2),
                "recommended_value": round(current_state.get("stock_flow", 100) + change, 2),
                "change": round(change, 2),
                "unit": "units",
                "rationale": (
                    f"Basis weight ({bw:.1f} gsm) is below target ({target:.1f} gsm). "
                    f"Increasing stock flow should increase sheet weight."
                ),
                "confidence": 0.6,
                "source": "Rule-based: BW below target → increase stock flow (process knowledge)",
            })
        elif bw > target:
            change = max((target - bw) * 0.3, -5.0)
            recommendations.append({
                "variable": "stock_flow",
                "current_value": round(current_state.get("stock_flow", 100), 2),
                "recommended_value": round(current_state.get("stock_flow", 100) + change, 2),
                "change": round(change, 2),
                "unit": "units",
                "rationale": (
                    f"Basis weight ({bw:.1f} gsm) is above target ({target:.1f} gsm). "
                    f"Reducing stock flow should decrease sheet weight."
                ),
                "confidence": 0.6,
                "source": "Rule-based: BW above target → decrease stock flow (process knowledge)",
            })

        # Steam pressure adjustment for moisture control
        moisture = current_state.get("moisture_pct", 6.5)
        if moisture > 7.0:
            recommendations.append({
                "variable": "steam_pressure",
                "current_value": round(current_state.get("steam_pressure", 300), 2),
                "recommended_value": round(current_state.get("steam_pressure", 300) + 3.0, 2),
                "change": 3.0,
                "unit": "kPa",
                "rationale": (
                    f"Moisture ({moisture:.2f}%) is elevated. Increasing steam pressure "
                    f"will help reduce moisture content (effect delayed ~60s)."
                ),
                "confidence": 0.5,
                "source": "Rule-based: high moisture → increase steam (process knowledge + lag correlation)",
            })

        return {
            "action": "adjust_setpoints",
            "message": (
                f"Risk level: {risk_level.upper()}. Using rule-based recommendations "
                f"(insufficient similar historical patterns found)."
            ),
            "risk_level": risk_level,
            "recommendations": recommendations,
            "estimated_recovery_time_sec": None,
            "similar_events_used": [],
            "source": "Rule-based process knowledge (fallback)",
        }

    def get_optimal_setpoints_for_grade(self, target_grade: str,
                                        source_grade: str = None) -> Dict:
        """
        Get optimal setpoints for a specific grade transition based on
        the fastest historical stabilizations.
        """
        # Filter to events targeting this grade
        grade_events = self.summary_df[self.summary_df["grade"] == target_grade]

        # Get the fastest 25% of transitions
        fast_events = grade_events.nsmallest(
            max(1, len(grade_events) // 4), "time_to_stabilize_sec"
        )

        transition_df = self.ts_df[
            (self.ts_df["grade_change_event_id"].isin(fast_events["grade_change_event_id"])) &
            (self.ts_df["phase"] == "transition")
        ]

        # Get the steady-state values these events settled to
        late_transition = transition_df[
            transition_df["time_since_transition_start_sec"] > 600  # last portion
        ]

        if late_transition.empty:
            late_transition = transition_df.tail(100)

        optimal = {
            "target_grade": target_grade,
            "source_grade": source_grade,
            "optimal_setpoints": {
                "stock_flow": round(late_transition["stock_flow"].median(), 2),
                "filler_flow": round(late_transition["filler_flow"].median(), 2),
                "steam_pressure": round(late_transition["steam_pressure"].median(), 2),
                "machine_speed": round(late_transition["machine_speed"].median(), 2),
            },
            "basis_weight_target_gsm": late_transition["basis_weight_target_gsm"].mode().iloc[0]
            if len(late_transition) > 0 else None,
            "source": (
                f"Optimal setpoints derived from the fastest {len(fast_events)} "
                f"historical transitions to {target_grade}"
            ),
            "avg_stabilize_time_sec": round(fast_events["time_to_stabilize_sec"].mean()),
        }
        return optimal


class FeedbackLogger:
    """Logs user accept/reject decisions on recommendations for later evaluation."""

    COLUMNS = [
        "timestamp", "event_id", "risk_level", "variable",
        "recommended_value", "current_value", "change",
        "source", "decision", "user_notes",
    ]

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._ensure_log_exists()

    def _needs_header(self) -> bool:
        """
        True if the log is missing, empty, or has lost its header row.
        Guards against a headerless file being produced by an append when the
        log was deleted or truncated mid-session -- which would otherwise make
        pandas read the first decision as column names.
        """
        if not os.path.exists(self.log_path):
            return True
        try:
            if os.path.getsize(self.log_path) == 0:
                return True
            with open(self.log_path, "r") as fh:
                first_line = fh.readline().strip()
            return not first_line.startswith("timestamp")
        except OSError:
            return True

    def _ensure_log_exists(self):
        """Create (or repair) the feedback log so it always has a valid header."""
        if not self._needs_header():
            return

        salvaged = None
        # If the file exists but lost its header, preserve the orphaned rows.
        if os.path.exists(self.log_path) and os.path.getsize(self.log_path) > 0:
            try:
                orphaned = pd.read_csv(self.log_path, header=None,
                                       names=self.COLUMNS)
                if not orphaned.empty:
                    salvaged = orphaned
            except Exception:
                salvaged = None

        frame = salvaged if salvaged is not None else pd.DataFrame(columns=self.COLUMNS)
        frame.to_csv(self.log_path, index=False)

    def log_decision(self, event_id: int, recommendation: Dict,
                     decision: str, user_notes: str = ""):
        """
        Log a user's accept/reject decision.

        Args:
            event_id: The grade change event ID
            recommendation: The recommendation dict that was shown
            decision: 'accept' or 'reject'
            user_notes: Optional notes from the user
        """
        row = {
            "timestamp": datetime.now().isoformat(),
            "event_id": event_id,
            "risk_level": recommendation.get("risk_level", "unknown"),
            "variable": recommendation.get("variable", ""),
            "recommended_value": recommendation.get("recommended_value", ""),
            "current_value": recommendation.get("current_value", ""),
            "change": recommendation.get("change", ""),
            "source": recommendation.get("source", ""),
            "decision": decision,
            "user_notes": user_notes,
        }
        # Re-check on every write: the file may have been removed or truncated
        # since this logger was constructed.
        write_header = self._needs_header()
        if write_header and os.path.exists(self.log_path):
            self._ensure_log_exists()
            write_header = False

        df = pd.DataFrame([row], columns=self.COLUMNS)
        df.to_csv(self.log_path, mode="a", header=write_header, index=False)

    def get_log(self) -> pd.DataFrame:
        """Read the full feedback log."""
        if os.path.exists(self.log_path):
            return pd.read_csv(self.log_path)
        return pd.DataFrame()

    def get_accuracy_stats(self) -> Dict:
        """Compute acceptance rate and other stats from the feedback log."""
        log = self.get_log()
        if log.empty:
            return {"total_decisions": 0, "accept_rate": 0, "reject_rate": 0}

        total = len(log)
        accepted = (log["decision"] == "accept").sum()
        rejected = (log["decision"] == "reject").sum()

        return {
            "total_decisions": total,
            "accepted": int(accepted),
            "rejected": int(rejected),
            "accept_rate": round(accepted / total, 3) if total > 0 else 0,
            "reject_rate": round(rejected / total, 3) if total > 0 else 0,
            "by_variable": log.groupby("variable")["decision"].value_counts().to_dict()
            if not log.empty else {},
        }


# --- Standalone execution for testing ---
if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    engine = RecommendationEngine(
        timeseries_path=os.path.join(base_dir, "data", "grade_change_timeseries.csv"),
        summary_path=os.path.join(base_dir, "data", "grade_change_event_summary.csv"),
    )
    print("Building recovery library...")
    n_patterns = engine.build_recovery_library()
    print(f"  Recovery patterns found: {n_patterns}")

    # Test recommendation for a simulated bad state
    test_state = {
        "basis_weight_deviation_pct": 4.5,
        "stock_flow": 92.0,
        "filler_flow": 18.5,
        "steam_pressure": 295.0,
        "machine_speed": 920.0,
        "moisture_pct": 6.8,
        "basis_weight_gsm": 47.0,
        "basis_weight_target_gsm": 45.0,
    }
    test_risk = {"risk_level": "high", "projected_deviation_pct": 5.2}

    print("\n\nTest Recommendation (high-risk scenario):")
    result = engine.recommend(test_state, test_risk)
    print(f"  Action: {result['action']}")
    print(f"  Message: {result['message']}")
    for rec in result.get("recommendations", []):
        print(f"\n  → {rec['variable']}:")
        print(f"    Current: {rec['current_value']} | Recommended: {rec['recommended_value']} ({rec['change']:+.2f})")
        print(f"    Rationale: {rec['rationale']}")
        print(f"    Source: {rec['source']}")

    # Test optimal setpoints
    print("\n\nOptimal setpoints for Grade-A-Light:")
    optimal = engine.get_optimal_setpoints_for_grade("Grade-A-Light")
    for k, v in optimal.items():
        print(f"  {k}: {v}")
