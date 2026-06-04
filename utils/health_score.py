"""
utils/health_score.py
─────────────────────
Calculates a health score (0–100) per machine.
Separate logic for CNC machines and REP robots since
their failure modes and sensor signals are completely different.
"""

import numpy as np
import pandas as pd


# ─── CNC Health Score ─────────────────────────────────────────────────────────

CNC_WEIGHTS = {
    "TOOL_WEAR_PCT":        0.30,   # Most important for CNC
    "X_VIBRATION_MMS":      0.20,
    "Y_VIBRATION_MMS":      0.15,
    "SPINDLE_LOAD_PCT":     0.15,
    "COOLANT_TEMP_C":       0.10,
    "POWER_CONSUMPTION_KW": 0.10,
}

CNC_THRESHOLDS = {
    # signal: (warning_threshold, critical_threshold)
    "TOOL_WEAR_PCT":        (70,   90),
    "X_VIBRATION_MMS":      (3.5,  6.0),
    "Y_VIBRATION_MMS":      (3.0,  5.5),
    "SPINDLE_LOAD_PCT":     (80,   95),
    "COOLANT_TEMP_C":       (35,   45),
    "POWER_CONSUMPTION_KW": (22,   28),
}


def health_score_cnc(row: pd.Series) -> float:
    """
    Health score for a CNC machine (0 = failed, 100 = perfect).
    Uses exponential degradation — a reading at 90% of the critical
    threshold causes much more penalty than at 50%.
    """
    penalty = 0.0
    total_weight = 0.0

    for signal, weight in CNC_WEIGHTS.items():
        value = row.get(signal, np.nan)
        if pd.isna(value):
            continue

        warn, crit = CNC_THRESHOLDS[signal]
        total_weight += weight

        if value <= warn:
            # Good zone — small penalty
            penalty += weight * 0.05
        elif value <= crit:
            # Warning zone — exponential penalty
            ratio = (value - warn) / (crit - warn)
            penalty += weight * (ratio ** 1.5) * 0.6
        else:
            # Critical zone — heavy penalty
            ratio = min((value - crit) / crit, 1.0)
            penalty += weight * (0.6 + ratio * 0.4)

    if total_weight == 0:
        return 50.0   # No data — return neutral score

    raw_score = 100 * (1 - penalty / total_weight)
    return float(np.clip(raw_score, 0, 100))


# ─── REP Health Score ─────────────────────────────────────────────────────────

REP_WEIGHTS = {
    "J1_VIBRATION_MMS":   0.25,   # Most important for robots
    "J2_BACKLASH_DEG":    0.25,
    "WELD_QUALITY_PCT":   0.20,
    "GRIPPER_FORCE_N":    0.15,
    "J3_TEMPERATURE_C":   0.10,
    "CONTROLLER_TEMP_C":  0.05,
}

REP_THRESHOLDS = {
    # For REP, some signals degrade DOWNWARD (quality, force)
    # Format: (warn, crit, direction)  direction: "up" or "down"
    "J1_VIBRATION_MMS":   (1.5,   3.0,   "up"),
    "J2_BACKLASH_DEG":    (0.08,  0.15,  "up"),
    "WELD_QUALITY_PCT":   (90,    80,    "down"),   # Lower = worse
    "GRIPPER_FORCE_N":    (380,   300,   "down"),   # Lower = worse
    "J3_TEMPERATURE_C":   (55,    70,    "up"),
    "CONTROLLER_TEMP_C":  (50,    65,    "up"),
}


def health_score_rep(row: pd.Series) -> float:
    """
    Health score for a REP robot (0 = failed, 100 = perfect).
    Handles bidirectional degradation:
    - Vibration/backlash/temperature: higher = worse
    - Weld quality/gripper force:     lower = worse
    """
    penalty = 0.0
    total_weight = 0.0

    for signal, weight in REP_WEIGHTS.items():
        value = row.get(signal, np.nan)
        if pd.isna(value):
            continue

        warn, crit, direction = REP_THRESHOLDS[signal]
        total_weight += weight

        if direction == "up":
            if value <= warn:
                penalty += weight * 0.05
            elif value <= crit:
                ratio = (value - warn) / (crit - warn)
                penalty += weight * (ratio ** 1.5) * 0.6
            else:
                ratio = min((value - crit) / crit, 1.0)
                penalty += weight * (0.6 + ratio * 0.4)
        else:   # direction == "down"
            if value >= warn:
                penalty += weight * 0.05
            elif value >= crit:
                ratio = (warn - value) / (warn - crit)
                penalty += weight * (ratio ** 1.5) * 0.6
            else:
                ratio = min((crit - value) / crit, 1.0)
                penalty += weight * (0.6 + ratio * 0.4)

    if total_weight == 0:
        return 50.0

    raw_score = 100 * (1 - penalty / total_weight)
    return float(np.clip(raw_score, 0, 100))


# ─── Unified Entry Point ──────────────────────────────────────────────────────

def compute_health_score(row: pd.Series) -> float:
    """
    Automatically selects CNC or REP formula based on MACHINE_TYPE.
    Use this on the master_df directly:
        master_df["HEALTH_SCORE"] = master_df.apply(compute_health_score, axis=1)
    """
    mtype = row.get("MACHINE_TYPE", "CNC")
    if mtype == "REP":
        return health_score_rep(row)
    return health_score_cnc(row)


def health_label(score: float) -> tuple:
    """Returns (label, color) for a health score."""
    if score >= 80:
        return "Good",     "#107E3E"
    elif score >= 60:
        return "Warning",  "#E9730C"
    elif score >= 40:
        return "Poor",     "#CC4400"
    else:
        return "Critical", "#BB0000"


def predict_rul(measurements_df: pd.DataFrame,
                equnr: str,
                signal: str,
                threshold: float,
                direction: str = "up",
                hours_per_reading: int = 3) -> float | None:
    """
    Predict Remaining Useful Life (RUL) in hours using linear trend.

    Args:
        measurements_df: Full measurement documents DataFrame
        equnr:           Equipment number e.g. 'EQ-10005'
        signal:          Characteristic name e.g. 'TOOL_WEAR_PCT'
        threshold:       Value at which failure occurs
        direction:       'up'   = value rises toward threshold (tool wear)
                         'down' = value falls toward threshold (weld quality)
        hours_per_reading: How often measurements are taken (default 3h)

    Returns:
        RUL in hours, or None if insufficient data
    """
    data = (
        measurements_df[
            (measurements_df["EQUNR"] == equnr) &
            (measurements_df["CHAR_NAME"] == signal)
        ]
        .sort_values("TIMESTAMP")
        .tail(30)
    )

    if len(data) < 5:
        return None

    values = data["VALUE"].values
    x = np.arange(len(values)).reshape(-1, 1)

    # Simple linear regression for trend
    slope = np.polyfit(range(len(values)), values, 1)[0]
    current = values[-1]

    if direction == "up":
        if slope <= 0:
            return 9999.0   # Not degrading
        readings_to_fail = (threshold - current) / slope
    else:   # down
        if slope >= 0:
            return 9999.0
        readings_to_fail = (current - threshold) / abs(slope)

    rul_hours = max(0.0, readings_to_fail * hours_per_reading)
    return round(rul_hours, 1)


# Recommended RUL signals per machine type
RUL_CONFIG = {
    "CNC": [
        ("TOOL_WEAR_PCT",    90,   "up"),
        ("X_VIBRATION_MMS",  6.0,  "up"),
        ("SPINDLE_LOAD_PCT", 95,   "up"),
    ],
    "REP": [
        ("J2_BACKLASH_DEG",  0.15, "up"),
        ("J1_VIBRATION_MMS", 3.0,  "up"),
        ("WELD_QUALITY_PCT", 80,   "down"),
        ("GRIPPER_FORCE_N",  300,  "down"),
    ],
}
