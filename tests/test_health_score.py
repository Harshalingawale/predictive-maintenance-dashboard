"""
tests/test_health_score.py
──────────────────────────
Run with: pytest tests/ -v
Or: F5 → "Run All Tests" in VS Code
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.health_score import (
    health_score_cnc, health_score_rep,
    compute_health_score, health_label, predict_rul
)


class TestCNCHealthScore:
    def test_perfect_machine_scores_high(self):
        row = pd.Series({
            "TOOL_WEAR_PCT": 5, "X_VIBRATION_MMS": 1.0,
            "Y_VIBRATION_MMS": 0.8, "SPINDLE_LOAD_PCT": 40,
            "COOLANT_TEMP_C": 22, "POWER_CONSUMPTION_KW": 12,
        })
        score = health_score_cnc(row)
        assert score >= 85, f"Expected >= 85 for healthy CNC, got {score:.1f}"

    def test_worn_tool_scores_low(self):
        row = pd.Series({
            "TOOL_WEAR_PCT": 95, "X_VIBRATION_MMS": 1.0,
            "Y_VIBRATION_MMS": 0.8, "SPINDLE_LOAD_PCT": 40,
            "COOLANT_TEMP_C": 22, "POWER_CONSUMPTION_KW": 12,
        })
        score = health_score_cnc(row)
        assert score < 60, f"Expected < 60 for worn tool, got {score:.1f}"

    def test_score_bounded_0_100(self):
        row = pd.Series({
            "TOOL_WEAR_PCT": 200, "X_VIBRATION_MMS": 50,
            "SPINDLE_LOAD_PCT": 200,
        })
        score = health_score_cnc(row)
        assert 0 <= score <= 100

    def test_missing_data_returns_neutral(self):
        row = pd.Series({})
        score = health_score_cnc(row)
        assert score == 50.0


class TestREPHealthScore:
    def test_healthy_robot_scores_high(self):
        row = pd.Series({
            "J1_VIBRATION_MMS": 0.5, "J2_BACKLASH_DEG": 0.01,
            "WELD_QUALITY_PCT": 97,  "GRIPPER_FORCE_N": 460,
            "J3_TEMPERATURE_C": 42,  "CONTROLLER_TEMP_C": 35,
        })
        score = health_score_rep(row)
        assert score >= 80, f"Expected >= 80 for healthy robot, got {score:.1f}"

    def test_poor_weld_quality_scores_low(self):
        row = pd.Series({
            "J1_VIBRATION_MMS": 0.5, "J2_BACKLASH_DEG": 0.01,
            "WELD_QUALITY_PCT": 65,   # Critical
            "GRIPPER_FORCE_N": 460,
        })
        score = health_score_rep(row)
        assert score < 70, f"Expected < 70 for poor weld quality, got {score:.1f}"


class TestHealthLabel:
    def test_labels(self):
        assert health_label(90)[0] == "Good"
        assert health_label(70)[0] == "Warning"
        assert health_label(50)[0] == "Poor"
        assert health_label(30)[0] == "Critical"


class TestComputeHealthScore:
    def test_routes_cnc_correctly(self):
        row = pd.Series({
            "MACHINE_TYPE": "CNC",
            "TOOL_WEAR_PCT": 5, "X_VIBRATION_MMS": 1.0,
            "SPINDLE_LOAD_PCT": 40, "COOLANT_TEMP_C": 22,
        })
        score = compute_health_score(row)
        assert isinstance(score, float)
        assert 0 <= score <= 100

    def test_routes_rep_correctly(self):
        row = pd.Series({
            "MACHINE_TYPE": "REP",
            "J1_VIBRATION_MMS": 0.5, "J2_BACKLASH_DEG": 0.01,
            "WELD_QUALITY_PCT": 97,
        })
        score = compute_health_score(row)
        assert isinstance(score, float)
        assert 0 <= score <= 100


class TestPredictRUL:
    def _make_meas_df(self, equnr, signal, values):
        from datetime import datetime, timedelta
        rows = []
        for i, v in enumerate(values):
            rows.append({
                "EQUNR": equnr,
                "CHAR_NAME": signal,
                "TIMESTAMP": datetime(2024,1,1) + timedelta(hours=i*3),
                "VALUE": v,
            })
        return pd.DataFrame(rows)

    def test_rising_signal_predicts_rul(self):
        # Tool wear rising from 30 to 70 over 40 readings → should have RUL
        values = np.linspace(30, 70, 40)
        df = self._make_meas_df("EQ-001", "TOOL_WEAR_PCT", values)
        rul = predict_rul(df, "EQ-001", "TOOL_WEAR_PCT", threshold=90, direction="up")
        assert rul is not None
        assert rul > 0

    def test_stable_signal_returns_high_rul(self):
        values = [30.0] * 20  # No change — not degrading
        df = self._make_meas_df("EQ-001", "TOOL_WEAR_PCT", values)
        rul = predict_rul(df, "EQ-001", "TOOL_WEAR_PCT", threshold=90, direction="up")
        assert rul == 9999.0

    def test_insufficient_data_returns_none(self):
        values = [30.0, 31.0]  # Only 2 readings
        df = self._make_meas_df("EQ-001", "TOOL_WEAR_PCT", values)
        rul = predict_rul(df, "EQ-001", "TOOL_WEAR_PCT", threshold=90, direction="up")
        assert rul is None
