"""JSON-safety helpers.

pandas/numpy hand back values that ``json`` refuses or mangles: numpy scalars,
``Timestamp``, and NaN/inf (which are not valid JSON). Everything leaving the
API goes through :func:`jsonable` first.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def jsonable(value: Any) -> Any:
    """Recursively convert pandas/numpy values into JSON-safe primitives."""
    if value is None:
        return None
    if isinstance(value, (str, bool, int)) and not isinstance(value, np.generic):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        as_float = float(value)
        return as_float if math.isfinite(as_float) else None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).isoformat()
    if value is pd.NaT:
        return None
    if isinstance(value, np.ndarray):
        return [jsonable(v) for v in value.tolist()]
    if isinstance(value, pd.Series):
        return [jsonable(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    try:
        if pd.isna(value):  # pandas NA / NaT scalars
            return None
    except (TypeError, ValueError):
        pass
    return value
