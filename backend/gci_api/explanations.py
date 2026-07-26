"""Plain-language copy for model features.

Lifted verbatim from the Streamlit dashboard's Correlation Analysis page so the
React UI shows the same wording. This is presentation copy only -- it does not
influence training, features, or scoring.
"""

from __future__ import annotations

FEATURE_EXPLANATIONS: dict[str, str] = {
    "current_deviation_pct": (
        "The single strongest driver. If deviation is already elevated, "
        "the system is more likely to remain off-spec in the near future."
    ),
    "bw_distance_from_target": (
        "How far the actual basis weight is from its target in absolute terms. "
        "Larger gaps take longer to close and signal active instability."
    ),
    "bw_volatility": (
        "Variability (std dev) of deviation over the last ~2 minutes. "
        "High volatility means the control system is oscillating rather than settling."
    ),
    "moisture_volatility": (
        "Unstable moisture indicates steam pressure hasn't settled, "
        "which will continue to perturb basis weight via the ~60s steam-moisture lag."
    ),
    "bw_deviation_rate": (
        "Rate of change in deviation: is the situation getting better or worse? "
        "A positive rate means the breach is deepening."
    ),
    "deviation_trend": (
        "Linear trend slope over recent samples. Captures whether "
        "the system is converging toward target or diverging away."
    ),
    "time_since_start_sec": (
        "How far into the transition we are. Early instability often self-corrects; "
        "late instability suggests the control system is struggling."
    ),
    "basis_weight_gsm": (
        "The raw sheet weight. Heavier grades have more thermal inertia "
        "and tend to take longer to respond to control adjustments."
    ),
    "moisture_pct": (
        "Current moisture level. Elevated moisture directly increases basis weight "
        "deviation since moisture is a major component of sheet weight."
    ),
    "steam_pressure": (
        "Steam drives the drying process. If steam hasn't settled to its target, "
        "moisture will remain unstable and BW deviation persists."
    ),
    "steam_rate": (
        "Rate of change in steam pressure. Rapid changes propagate through "
        "to moisture (with ~60s lag) and then to basis weight."
    ),
    "steam_volatility": (
        "Fluctuating steam pressure means the dryer section isn't in steady state, "
        "which guarantees continued moisture -- and thus BW -- instability."
    ),
}

DEFAULT_FEATURE_EXPLANATION = "Contributes to predicting transition outcome."

FEATURE_IMPORTANCE_SOURCE = (
    "Feature importance scores from the Random Forest classifier, trained on "
    "15,664 transition-window samples with event-based holdout validation. "
    "Importance reflects how much each variable reduces prediction uncertainty "
    "(Gini impurity)."
)

PROJECTION_CAVEAT = (
    "Projection assumes current 60-second rate of change continues unchanged. "
    "Does not account for recommended corrective actions, operator interventions, "
    "or non-linear process dynamics. Correlated parameters (moisture, steam) are "
    "shown because steam pressure affects moisture with a ~60s lag, which in turn "
    "drives basis weight deviation."
)

RECIPE_LIMITS_SOURCE = (
    "Limits derived from steady-state operating ranges (mean +/- 2.5\u03c3). "
    "Source: Recipe limits"
)


def explain_feature(feature: str) -> str:
    return FEATURE_EXPLANATIONS.get(feature, DEFAULT_FEATURE_EXPLANATION)
