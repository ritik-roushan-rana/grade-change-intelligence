"""
Synthetic dataset generator: Grade Change Intelligence in Paper Making Process
-------------------------------------------------------------------------------
Simulates a paper machine (Honeywell QCS / MD Control style) going through
multiple grade-change events. Produces a time-series dataset with:
    - process variables (stock flow, filler flow, steam pressure, machine speed,
      moisture, ash, caliper, basis weight)
    - grade/recipe metadata
    - operator actions during instability
    - an off-spec flag (Basis Weight deviating >2.5% from setpoint)

Designed so that:
    1) Some grade changes stabilize quickly & cleanly.
    2) Some grade changes go off-spec / take long to settle.
    3) There are REAL, discoverable correlations built in on purpose
       (e.g., steam pressure lag -> moisture -> basis weight), so a
       "correlation discovery" module has something genuine to find.

Tweak the CONFIG section below to change size, noise, number of events, etc.
Re-run to regenerate a fresh dataset.
"""

import os

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ------------------------- CONFIG -------------------------
SEED = 42
N_GRADE_CHANGES = 119          # number of grade-change events to simulate (~50,000 rows)
STEADY_STATE_MINUTES = 60     # minutes of steady state before each change
TRANSITION_MINUTES = 45       # minutes of active transition/settling window
SAMPLE_INTERVAL_SEC = 15      # data resolution (seconds between samples)
OFF_SPEC_FRACTION = 0.35      # ~35% of grade changes will go off-spec
START_TIME = datetime(2026, 1, 1, 6, 0, 0)

BASIS_WEIGHT_SPEC_TOLERANCE = 0.025  # 2.5% deviation = off-spec

# Grade catalog: (grade_name, target_basis_weight_gsm, target_moisture_pct,
#                 target_ash_pct, target_caliper_um)
GRADES = [
    ("Grade-A-Light",   45.0, 6.0, 12.0, 60.0),
    ("Grade-B-Std",      60.0, 6.5, 14.0, 78.0),
    ("Grade-C-Heavy",    80.0, 7.0, 16.0, 100.0),
    ("Grade-D-Premium",  55.0, 5.5, 10.0, 70.0),
]

rng = np.random.default_rng(SEED)

# ------------------------- HELPERS -------------------------

def relax_to_target(current, target, rate, noise_scale, rng):
    """First-order lag toward target with noise. rate in (0,1]: higher = faster settle."""
    step = (target - current) * rate
    return current + step + rng.normal(0, noise_scale)


def simulate_grade_change(event_id, start_time, prev_grade, next_grade, off_spec, rng):
    """
    Simulate one full grade-change event: steady state on prev_grade,
    then transition to next_grade, ending in steady state on next_grade.
    Returns a list of row dicts.
    """
    rows = []
    steady_steps = int(STEADY_STATE_MINUTES * 60 / SAMPLE_INTERVAL_SEC)
    transition_steps = int(TRANSITION_MINUTES * 60 / SAMPLE_INTERVAL_SEC)
    total_steps = steady_steps + transition_steps

    prev_name, prev_bw, prev_moist, prev_ash, prev_cal = prev_grade
    next_name, next_bw, next_moist, next_ash, next_cal = next_grade

    # Base process variables at steady state (loosely tied to grade targets)
    stock_flow = 100.0 + (prev_bw - 60.0) * 0.8
    filler_flow = 20.0 + (prev_ash - 14.0) * 1.2
    steam_pressure = 300.0 + (prev_moist - 6.5) * -8.0
    machine_speed = 900.0 - (prev_bw - 60.0) * 3.0

    basis_weight = prev_bw
    moisture = prev_moist
    ash = prev_ash
    caliper = prev_cal

    # Settling speed differs for "good" vs "off-spec" transitions
    if off_spec:
        bw_rate = rng.uniform(0.03, 0.06)     # slow settle -> overshoot/oscillation
        noise_scale = rng.uniform(0.25, 0.4)
        steam_lag_steps = rng.integers(6, 12)  # bigger lag -> worse coupling
    else:
        bw_rate = rng.uniform(0.12, 0.20)     # fast settle
        noise_scale = rng.uniform(0.05, 0.12)
        steam_lag_steps = rng.integers(2, 5)

    steam_history = [steam_pressure] * (steam_lag_steps + 1)

    # Targets shift at the start of the transition window
    target_stock_flow = 100.0 + (next_bw - 60.0) * 0.8
    target_filler_flow = 20.0 + (next_ash - 14.0) * 1.2
    target_steam_pressure = 300.0 + (next_moist - 6.5) * -8.0
    target_machine_speed = 900.0 - (next_bw - 60.0) * 3.0

    t = start_time
    for i in range(total_steps):
        in_transition = i >= steady_steps
        grade_now = next_name if in_transition else prev_name
        bw_target = next_bw if in_transition else prev_bw
        moist_target = next_moist if in_transition else prev_moist
        ash_target = next_ash if in_transition else prev_ash
        cal_target = next_cal if in_transition else prev_cal

        # Manipulated variables move toward their new targets once transition starts
        rate_mv = 0.08 if in_transition else 0.02
        stock_flow = relax_to_target(stock_flow, target_stock_flow if in_transition else stock_flow, rate_mv, 0.3, rng)
        filler_flow = relax_to_target(filler_flow, target_filler_flow if in_transition else filler_flow, rate_mv, 0.2, rng)
        machine_speed = relax_to_target(machine_speed, target_machine_speed if in_transition else machine_speed, rate_mv, 0.5, rng)

        # Steam pressure moves toward target with its own dynamics
        steam_pressure = relax_to_target(steam_pressure, target_steam_pressure if in_transition else steam_pressure, rate_mv * 0.9, 0.4, rng)
        steam_history.append(steam_pressure)

        # Moisture responds to LAGGED steam pressure (built-in discoverable correlation)
        lagged_steam = steam_history[-1 - steam_lag_steps]
        steam_driven_moist_target = moist_target + (lagged_steam - target_steam_pressure) * -0.01
        moisture = relax_to_target(moisture, steam_driven_moist_target, bw_rate * 0.8, noise_scale * 0.15, rng)

        # Ash follows filler flow roughly
        ash = relax_to_target(ash, ash_target + (filler_flow - target_filler_flow) * 0.05, bw_rate, noise_scale * 0.1, rng)

        # Caliper follows basis weight roughly (thicker sheet -> more caliper)
        caliper = relax_to_target(caliper, cal_target, bw_rate, noise_scale * 0.5, rng)

        # Basis weight: the main target variable, driven by stock flow & moisture, with lag/noise
        bw_driver_target = bw_target + (moisture - moist_target) * 1.5 + (stock_flow - target_stock_flow) * 0.05
        basis_weight = relax_to_target(basis_weight, bw_driver_target, bw_rate, noise_scale, rng)

        deviation_pct = abs(basis_weight - bw_target) / bw_target
        is_off_spec = deviation_pct > BASIS_WEIGHT_SPEC_TOLERANCE

        # Operator action: logged occasionally during instability
        operator_action = ""
        if in_transition and is_off_spec and rng.random() < 0.08:
            action_choices = [
                "Trimmed stock flow setpoint",
                "Nudged steam pressure setpoint",
                "Adjusted filler flow manually",
                "Reduced machine speed ramp rate",
            ]
            operator_action = rng.choice(action_choices)

        rows.append({
            "timestamp": t,
            "grade_change_event_id": event_id,
            "grade": grade_now,
            "phase": "transition" if in_transition else "steady_state",
            "time_since_transition_start_sec": (i - steady_steps) * SAMPLE_INTERVAL_SEC if in_transition else -1,
            "stock_flow": round(stock_flow, 3),
            "filler_flow": round(filler_flow, 3),
            "steam_pressure": round(steam_pressure, 3),
            "machine_speed": round(machine_speed, 3),
            "moisture_pct": round(moisture, 3),
            "ash_pct": round(ash, 3),
            "caliper_um": round(caliper, 3),
            "basis_weight_gsm": round(basis_weight, 3),
            "basis_weight_target_gsm": bw_target,
            "basis_weight_deviation_pct": round(deviation_pct * 100, 3),
            "off_spec_flag": bool(is_off_spec),
            "operator_action": operator_action,
        })
        t += timedelta(seconds=SAMPLE_INTERVAL_SEC)

    return rows


# ------------------------- MAIN GENERATION LOOP -------------------------
all_rows = []
current_time = START_TIME
prev_grade = GRADES[0]

off_spec_flags = rng.random(N_GRADE_CHANGES) < OFF_SPEC_FRACTION

for event_id in range(1, N_GRADE_CHANGES + 1):
    next_grade = GRADES[rng.integers(0, len(GRADES))]
    while next_grade[0] == prev_grade[0]:
        next_grade = GRADES[rng.integers(0, len(GRADES))]

    off_spec = off_spec_flags[event_id - 1]
    rows = simulate_grade_change(event_id, current_time, prev_grade, next_grade, off_spec, rng)
    all_rows.extend(rows)

    # advance clock + small random gap between events
    current_time = rows[-1]["timestamp"] + timedelta(minutes=int(rng.integers(30, 180)))
    prev_grade = next_grade

df = pd.DataFrame(all_rows)

# Event-level summary (useful for the dashboard / correlation discovery)
# Restrict off-spec determination to the transition phase only (steady-state noise shouldn't count)
transition_df = df[df["phase"] == "transition"]
summary = (
    transition_df.groupby("grade_change_event_id")
    .agg(
        grade=("grade", "last"),
        max_deviation_pct=("basis_weight_deviation_pct", "max"),
        went_off_spec=("off_spec_flag", "any"),
        n_operator_actions=("operator_action", lambda s: (s != "").sum()),
    )
    .reset_index()
)
def time_to_stabilize(group):
    off = group[group["off_spec_flag"]]
    if off.empty:
        return 0
    return off["time_since_transition_start_sec"].max()

stabilize_times = transition_df.groupby("grade_change_event_id").apply(time_to_stabilize, include_groups=False)
summary["time_to_stabilize_sec"] = summary["grade_change_event_id"].map(stabilize_times)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

df.to_csv(os.path.join(OUTPUT_DIR, "grade_change_timeseries.csv"), index=False)
summary.to_csv(os.path.join(OUTPUT_DIR, "grade_change_event_summary.csv"), index=False)

print(f"Output written to: {OUTPUT_DIR}")
print(f"Rows generated: {len(df)}")
print(f"Grade change events: {N_GRADE_CHANGES}")
print(f"Events that went off-spec: {int(summary['went_off_spec'].sum())} / {N_GRADE_CHANGES}")
print(df.head(10).to_string())
