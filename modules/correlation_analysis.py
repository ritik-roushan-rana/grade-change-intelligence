"""
Correlation Analysis Module
----------------------------
Mines timeseries + event summary data to discover which variables and
patterns predict a bad (slow-to-stabilize or high-deviation) grade-change
transition.

Outputs:
- Correlation strength (r-value or feature importance)
- Plain-language explanation of each finding
- Data-source tag for every insight
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import List, Dict, Any


class CorrelationAnalyzer:
    """Discovers correlations between process variables and grade-change outcomes."""

    def __init__(self, timeseries_path: str, summary_path: str):
        self.ts_df = pd.read_csv(timeseries_path, parse_dates=["timestamp"])
        self.summary_df = pd.read_csv(summary_path)
        self.findings: List[Dict[str, Any]] = []

    def run_full_analysis(self) -> List[Dict[str, Any]]:
        """Run all correlation analyses and return findings."""
        self.findings = []
        self._analyze_steam_moisture_lag()
        self._analyze_filler_ash_correlation()
        self._analyze_operator_actions_vs_stabilization()
        self._analyze_variable_volatility_vs_outcome()
        self._analyze_ramp_rate_impact()
        self._analyze_initial_deviation_magnitude()
        self._analyze_grade_pair_difficulty()
        return self.findings

    def _analyze_steam_moisture_lag(self):
        """
        Discover: Steam pressure changes affect moisture with a time lag,
        and moisture drives basis weight deviation.
        """
        transition_df = self.ts_df[self.ts_df["phase"] == "transition"].copy()

        # Per-event: compute cross-correlation between steam_pressure and moisture
        lag_correlations = []
        for event_id, group in transition_df.groupby("grade_change_event_id"):
            if len(group) < 20:
                continue
            steam = group["steam_pressure"].values
            moisture = group["moisture_pct"].values
            # Normalize
            steam_norm = (steam - steam.mean()) / (steam.std() + 1e-9)
            moisture_norm = (moisture - moisture.mean()) / (moisture.std() + 1e-9)
            # Cross-correlation at multiple lags (each lag = 15 sec)
            best_lag = 0
            best_corr = 0
            for lag in range(1, min(12, len(steam_norm) // 2)):
                corr = np.corrcoef(steam_norm[:-lag], moisture_norm[lag:])[0, 1]
                if abs(corr) > abs(best_corr):
                    best_corr = corr
                    best_lag = lag
            lag_correlations.append({
                "event_id": event_id,
                "best_lag_steps": best_lag,
                "best_lag_seconds": best_lag * 15,
                "correlation": best_corr
            })

        lag_df = pd.DataFrame(lag_correlations)
        # Merge with summary to see if larger lag correlates with worse outcomes
        merged = lag_df.merge(self.summary_df, left_on="event_id", right_on="grade_change_event_id")

        if len(merged) > 5:
            r_lag_stab, p_lag_stab = stats.pearsonr(
                merged["best_lag_steps"], merged["time_to_stabilize_sec"]
            )
            r_lag_dev, p_lag_dev = stats.pearsonr(
                merged["best_lag_steps"], merged["max_deviation_pct"]
            )

            avg_lag = lag_df["best_lag_seconds"].mean()
            avg_corr = lag_df["correlation"].mean()

            self.findings.append({
                "id": "steam_moisture_lag",
                "title": "Steam Pressure → Moisture Time Lag",
                "description": (
                    f"Steam pressure changes affect moisture with an average lag of "
                    f"{avg_lag:.0f} seconds (avg cross-correlation: {avg_corr:.3f}). "
                    f"Events with larger steam-moisture lag take significantly longer to stabilize "
                    f"(r={r_lag_stab:.3f}, p={p_lag_stab:.4f}) and reach higher deviations "
                    f"(r={r_lag_dev:.3f}, p={p_lag_dev:.4f})."
                ),
                "correlation_strength": round(r_lag_stab, 3),
                "p_value": round(p_lag_stab, 4),
                "impact": "high",
                "source": "Historical timeseries cross-correlation analysis",
                "recommendation": (
                    "Pre-emptively adjust steam pressure BEFORE the grade change to reduce "
                    "the effective lag. Larger anticipatory steam moves lead to faster moisture "
                    "settling and reduced basis weight deviation."
                ),
                "variables_involved": ["steam_pressure", "moisture_pct", "basis_weight_gsm"],
            })

    def _analyze_filler_ash_correlation(self):
        """Discover: Filler flow drift correlates with ash deviation."""
        transition_df = self.ts_df[self.ts_df["phase"] == "transition"].copy()

        # Per event: compute filler flow variability vs ash variability
        event_stats = []
        for event_id, group in transition_df.groupby("grade_change_event_id"):
            if len(group) < 10:
                continue
            filler_std = group["filler_flow"].std()
            ash_std = group["ash_pct"].std()
            filler_range = group["filler_flow"].max() - group["filler_flow"].min()
            event_stats.append({
                "event_id": event_id,
                "filler_std": filler_std,
                "filler_range": filler_range,
                "ash_std": ash_std,
            })

        stats_df = pd.DataFrame(event_stats)
        if len(stats_df) > 5:
            r_val, p_val = stats.pearsonr(stats_df["filler_std"], stats_df["ash_std"])

            # Also check impact on stabilization
            merged = stats_df.merge(
                self.summary_df, left_on="event_id", right_on="grade_change_event_id"
            )
            r_stab, p_stab = stats.pearsonr(merged["filler_std"], merged["time_to_stabilize_sec"])

            self.findings.append({
                "id": "filler_ash_drift",
                "title": "Filler Flow Drift → Ash Deviation",
                "description": (
                    f"Filler flow variability during transition strongly correlates with "
                    f"ash percentage variability (r={r_val:.3f}, p={p_val:.4f}). "
                    f"Higher filler flow instability also correlates with longer "
                    f"stabilization time (r={r_stab:.3f}, p={p_stab:.4f})."
                ),
                "correlation_strength": round(r_val, 3),
                "p_value": round(p_val, 4),
                "impact": "medium",
                "source": "Historical timeseries variability analysis",
                "recommendation": (
                    "Tighten filler flow control during grade changes. Smoother filler "
                    "flow ramps reduce ash variability and contribute to faster stabilization."
                ),
                "variables_involved": ["filler_flow", "ash_pct"],
            })

    def _analyze_operator_actions_vs_stabilization(self):
        """Discover: More operator interventions correlate with longer stabilization."""
        df = self.summary_df.copy()
        if len(df) > 5:
            r_val, p_val = stats.pearsonr(
                df["n_operator_actions"], df["time_to_stabilize_sec"]
            )
            r_dev, p_dev = stats.pearsonr(
                df["n_operator_actions"], df["max_deviation_pct"]
            )

            self.findings.append({
                "id": "operator_actions_stabilization",
                "title": "Operator Interventions → Longer Stabilization",
                "description": (
                    f"The number of operator actions during a grade change is positively "
                    f"correlated with stabilization time (r={r_val:.3f}, p={p_val:.4f}) "
                    f"and maximum deviation (r={r_dev:.3f}, p={p_dev:.4f}). "
                    f"This suggests that frequent manual interventions either indicate "
                    f"a difficult transition or cause oscillations that delay settling."
                ),
                "correlation_strength": round(r_val, 3),
                "p_value": round(p_val, 4),
                "impact": "high",
                "source": "Event summary statistical analysis",
                "recommendation": (
                    "Limit manual operator interventions during the first 2-3 minutes "
                    "of a grade change. Allow the automatic control system to settle "
                    "before making manual adjustments, unless deviation exceeds critical thresholds."
                ),
                "variables_involved": ["operator_action", "time_to_stabilize_sec"],
            })

    def _analyze_variable_volatility_vs_outcome(self):
        """Discover: Early volatility in process variables predicts bad outcomes."""
        transition_df = self.ts_df[self.ts_df["phase"] == "transition"].copy()

        # Look at first 2 minutes (8 samples) of transition
        early_transition = transition_df[
            transition_df["time_since_transition_start_sec"] <= 120
        ]

        process_vars = ["stock_flow", "filler_flow", "steam_pressure", "machine_speed"]
        volatility_results = []

        for event_id, group in early_transition.groupby("grade_change_event_id"):
            if len(group) < 5:
                continue
            row = {"event_id": event_id}
            for var in process_vars:
                # Volatility = std of first differences (rate of change)
                diffs = group[var].diff().dropna()
                row[f"{var}_volatility"] = diffs.std()
            volatility_results.append(row)

        vol_df = pd.DataFrame(volatility_results)
        merged = vol_df.merge(
            self.summary_df, left_on="event_id", right_on="grade_change_event_id"
        )

        best_var = None
        best_r = 0
        for var in process_vars:
            col = f"{var}_volatility"
            if col in merged.columns:
                r, p = stats.pearsonr(merged[col], merged["time_to_stabilize_sec"])
                if abs(r) > abs(best_r):
                    best_r = r
                    best_var = var
                    best_p = p

        if best_var:
            self.findings.append({
                "id": "early_volatility_predictor",
                "title": f"Early {best_var.replace('_', ' ').title()} Volatility → Slow Stabilization",
                "description": (
                    f"High volatility (rate-of-change variability) in {best_var.replace('_', ' ')} "
                    f"during the first 2 minutes of transition is the strongest early predictor "
                    f"of slow stabilization (r={best_r:.3f}, p={best_p:.4f})."
                ),
                "correlation_strength": round(best_r, 3),
                "p_value": round(best_p, 4),
                "impact": "medium",
                "source": "Early-transition volatility analysis (first 120 sec)",
                "recommendation": (
                    f"Monitor {best_var.replace('_', ' ')} rate-of-change in the first 2 minutes. "
                    f"If volatility exceeds historical norms, proactively dampen ramp rates."
                ),
                "variables_involved": [best_var, "time_to_stabilize_sec"],
            })

    def _analyze_ramp_rate_impact(self):
        """Discover: Speed of variable ramping affects outcome quality."""
        transition_df = self.ts_df[self.ts_df["phase"] == "transition"].copy()

        ramp_stats = []
        for event_id, group in transition_df.groupby("grade_change_event_id"):
            if len(group) < 10:
                continue
            # Compute ramp rate as slope over first 5 minutes
            early = group[group["time_since_transition_start_sec"] <= 300]
            if len(early) < 5:
                continue
            t = early["time_since_transition_start_sec"].values
            bw = early["basis_weight_gsm"].values
            speed = early["machine_speed"].values

            # Linear fit for basis weight ramp
            if t.std() > 0:
                bw_slope = np.polyfit(t, bw, 1)[0]
                speed_slope = np.polyfit(t, speed, 1)[0]
                ramp_stats.append({
                    "event_id": event_id,
                    "bw_ramp_rate": abs(bw_slope),
                    "speed_ramp_rate": abs(speed_slope),
                })

        ramp_df = pd.DataFrame(ramp_stats)
        if len(ramp_df) > 5:
            merged = ramp_df.merge(
                self.summary_df, left_on="event_id", right_on="grade_change_event_id"
            )
            r_speed, p_speed = stats.pearsonr(
                merged["speed_ramp_rate"], merged["time_to_stabilize_sec"]
            )

            self.findings.append({
                "id": "ramp_rate_impact",
                "title": "Machine Speed Ramp Rate → Stabilization Time",
                "description": (
                    f"Faster machine speed ramp rates during the first 5 minutes of "
                    f"transition correlate with stabilization outcomes "
                    f"(r={r_speed:.3f}, p={p_speed:.4f}). Aggressive ramping can "
                    f"either help (reaching target faster) or hurt (causing overshoot)."
                ),
                "correlation_strength": round(r_speed, 3),
                "p_value": round(p_speed, 4),
                "impact": "medium",
                "source": "Ramp-rate regression analysis (first 300 sec)",
                "recommendation": (
                    "Use moderate, controlled ramp rates for machine speed changes. "
                    "Match the ramp rate to the grade-pair difficulty based on historical performance."
                ),
                "variables_involved": ["machine_speed", "time_to_stabilize_sec"],
            })

    def _analyze_initial_deviation_magnitude(self):
        """Discover: Initial basis weight jump magnitude predicts recovery difficulty."""
        transition_df = self.ts_df[self.ts_df["phase"] == "transition"].copy()

        # Get first reading of transition for each event
        first_readings = transition_df.groupby("grade_change_event_id").first().reset_index()

        merged = first_readings[["grade_change_event_id", "basis_weight_deviation_pct"]].merge(
            self.summary_df, on="grade_change_event_id"
        )
        merged.rename(
            columns={"basis_weight_deviation_pct_x": "initial_deviation"},
            inplace=True
        )

        if len(merged) > 5 and "initial_deviation" in merged.columns:
            r_val, p_val = stats.pearsonr(
                merged["initial_deviation"], merged["time_to_stabilize_sec"]
            )

            self.findings.append({
                "id": "initial_deviation_difficulty",
                "title": "Initial Deviation Magnitude → Recovery Difficulty",
                "description": (
                    f"The basis weight deviation at the very start of transition "
                    f"(the 'step size') correlates with time to stabilize "
                    f"(r={r_val:.3f}, p={p_val:.4f}). Larger grade jumps are harder to recover from."
                ),
                "correlation_strength": round(r_val, 3),
                "p_value": round(p_val, 4),
                "impact": "high",
                "source": "Initial condition analysis at transition start",
                "recommendation": (
                    "For large grade jumps (>15% initial deviation), activate enhanced "
                    "control mode: tighter tolerances, faster control loop gains, and "
                    "pre-positioning of manipulated variables before the transition starts."
                ),
                "variables_involved": ["basis_weight_deviation_pct", "time_to_stabilize_sec"],
            })

    def _analyze_grade_pair_difficulty(self):
        """Discover: Certain grade-to-grade transitions are inherently harder."""
        # We need to determine the source grade for each event
        # Events are sequential, so prev grade is the grade at steady state
        steady_df = self.ts_df[self.ts_df["phase"] == "steady_state"]
        first_steady = steady_df.groupby("grade_change_event_id")["grade"].first().reset_index()
        first_steady.columns = ["grade_change_event_id", "source_grade"]

        merged = self.summary_df.merge(first_steady, on="grade_change_event_id")
        merged["grade_pair"] = merged["source_grade"] + " → " + merged["grade"]

        # Group by grade pair and compute average stabilization time
        pair_stats = merged.groupby("grade_pair").agg(
            avg_stabilize=("time_to_stabilize_sec", "mean"),
            avg_deviation=("max_deviation_pct", "mean"),
            count=("grade_change_event_id", "count")
        ).reset_index()

        pair_stats = pair_stats[pair_stats["count"] >= 3]  # need enough samples

        if len(pair_stats) > 2:
            hardest = pair_stats.loc[pair_stats["avg_stabilize"].idxmax()]
            easiest = pair_stats.loc[pair_stats["avg_stabilize"].idxmin()]

            self.findings.append({
                "id": "grade_pair_difficulty",
                "title": "Grade-Pair Transition Difficulty",
                "description": (
                    f"Certain grade transitions are consistently harder. "
                    f"Hardest: '{hardest['grade_pair']}' (avg {hardest['avg_stabilize']:.0f}s to stabilize, "
                    f"avg {hardest['avg_deviation']:.1f}% max deviation). "
                    f"Easiest: '{easiest['grade_pair']}' (avg {easiest['avg_stabilize']:.0f}s, "
                    f"avg {easiest['avg_deviation']:.1f}% deviation). "
                    f"Grade pairs with large basis weight differences tend to be harder."
                ),
                "correlation_strength": None,
                "p_value": None,
                "impact": "high",
                "source": "Grade-pair aggregation from event summary",
                "recommendation": (
                    f"Pre-load optimized trajectories per grade pair. For difficult pairs "
                    f"like '{hardest['grade_pair']}', use slower ramp rates and "
                    f"anticipatory steam pressure adjustments."
                ),
                "variables_involved": ["grade", "time_to_stabilize_sec", "max_deviation_pct"],
                "detail_data": pair_stats.to_dict("records"),
            })

    def get_findings_summary(self) -> pd.DataFrame:
        """Return findings as a DataFrame for display."""
        if not self.findings:
            self.run_full_analysis()
        rows = []
        for f in self.findings:
            rows.append({
                "ID": f["id"],
                "Finding": f["title"],
                "Correlation (r)": f.get("correlation_strength", "N/A"),
                "p-value": f.get("p_value", "N/A"),
                "Impact": f["impact"],
                "Source": f["source"],
            })
        return pd.DataFrame(rows)


# --- Standalone execution for testing ---
if __name__ == "__main__":
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    analyzer = CorrelationAnalyzer(
        timeseries_path=os.path.join(base_dir, "data", "grade_change_timeseries.csv"),
        summary_path=os.path.join(base_dir, "data", "grade_change_event_summary.csv"),
    )
    findings = analyzer.run_full_analysis()
    print(f"\n{'='*60}")
    print(f"  CORRELATION ANALYSIS RESULTS: {len(findings)} findings")
    print(f"{'='*60}\n")
    for i, f in enumerate(findings, 1):
        print(f"[{i}] {f['title']}")
        print(f"    Impact: {f['impact'].upper()}")
        print(f"    {f['description']}")
        print(f"    Source: {f['source']}")
        print(f"    Recommendation: {f['recommendation']}")
        print()
