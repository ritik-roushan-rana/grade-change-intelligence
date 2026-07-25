"""
Recipe Limits Module
---------------------
Defines per-grade operating limits for all process variables.
Limits are derived from steady-state operating ranges in historical data
(mean ± 2.5 standard deviations during steady_state phase).

Used by:
- Recommendation engine: to validate suggested setpoints don't exceed safe range
- Dashboard: to display safe operating range alongside current values
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


# Per-grade recipe limits: {grade: {variable: (min, max)}}
# Derived from steady-state data: mean ± 2.5*std
RECIPE_LIMITS = {
    "Grade-A-Light": {
        "stock_flow": (81.3, 95.4),
        "filler_flow": (11.1, 23.0),
        "steam_pressure": (294.5, 314.5),
        "machine_speed": (930.8, 957.8),
        "moisture_pct": (5.71, 6.24),
        "ash_pct": (11.46, 12.37),
        "caliper_um": (59.27, 60.73),
    },
    "Grade-B-Std": {
        "stock_flow": (92.7, 106.9),
        "filler_flow": (15.3, 24.6),
        "steam_pressure": (287.7, 311.6),
        "machine_speed": (885.7, 912.1),
        "moisture_pct": (6.21, 6.86),
        "ash_pct": (13.60, 14.56),
        "caliper_um": (77.11, 78.87),
    },
    "Grade-C-Heavy": {
        "stock_flow": (107.6, 123.7),
        "filler_flow": (16.2, 28.9),
        "steam_pressure": (285.5, 305.1),
        "machine_speed": (825.9, 855.8),
        "moisture_pct": (6.81, 7.35),
        "ash_pct": (15.82, 16.62),
        "caliper_um": (99.26, 100.69),
    },
    "Grade-D-Premium": {
        "stock_flow": (88.1, 101.8),
        "filler_flow": (9.3, 20.5),
        "steam_pressure": (297.2, 318.2),
        "machine_speed": (899.8, 928.0),
        "moisture_pct": (5.13, 5.72),
        "ash_pct": (9.31, 10.20),
        "caliper_um": (69.21, 70.74),
    },
}


def get_limits_for_grade(grade: str) -> Dict[str, tuple]:
    """Get recipe limits for a given grade. Returns empty dict if grade not found."""
    return RECIPE_LIMITS.get(grade, {})


def check_within_limits(grade: str, variable: str, value: float) -> Dict:
    """
    Check if a value is within recipe limits for a grade/variable.
    Returns dict with: within_limits (bool), min, max, violation_amount.
    """
    limits = RECIPE_LIMITS.get(grade, {}).get(variable)
    if limits is None:
        return {"within_limits": True, "min": None, "max": None, "violation": 0}

    lo, hi = limits
    within = lo <= value <= hi
    violation = 0
    if value < lo:
        violation = value - lo  # negative = below min
    elif value > hi:
        violation = value - hi  # positive = above max

    return {
        "within_limits": within,
        "min": lo,
        "max": hi,
        "violation": round(violation, 2),
    }


def validate_recommendation(grade: str, variable: str,
                            recommended_value: float) -> Dict:
    """
    Validate a recommended setpoint against recipe limits.
    Returns check result + whether the recommendation should be flagged.
    """
    check = check_within_limits(grade, variable, recommended_value)
    if not check["within_limits"]:
        check["flagged"] = True
        check["flag_message"] = (
            f"Recommended {variable.replace('_',' ')} value "
            f"({recommended_value:.2f}) exceeds recipe limits "
            f"[{check['min']}, {check['max']}] for {grade}."
        )
    else:
        check["flagged"] = False
        check["flag_message"] = None
    return check


def get_limits_dataframe(grade: str) -> pd.DataFrame:
    """Get recipe limits as a formatted DataFrame for dashboard display."""
    limits = RECIPE_LIMITS.get(grade, {})
    if not limits:
        return pd.DataFrame()

    rows = []
    for var, (lo, hi) in limits.items():
        rows.append({
            "Variable": var.replace("_", " ").title(),
            "Min": lo,
            "Max": hi,
            "Range": f"{lo} – {hi}",
        })
    return pd.DataFrame(rows)
