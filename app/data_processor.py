
# Data loading & feature engineering

import numpy as np
import pandas as pd
from datetime import datetime


class DataProcessor:
    """
    Loads the AI4I 2020 dataset, renames columns to internal names,
    and engineers derived features (vibration, power, timestamps, etc.).
    """

    COLUMN_MAP = {
        'Product ID':                  'machine_id',
        'Type':                        'machine_type',
        'Air temperature [K]':         'air_temp',
        'Process temperature [K]':     'process_temp',
        'Rotational speed [rpm]':      'rot_speed',
        'Torque [Nm]':                 'torque',
        'Tool wear [min]':             'tool_wear',
        'Machine failure':             'failure',
        'TWF':                         'tool_wear_failure',
        'HDF':                         'heat_dissipation_failure',
        'PWF':                         'power_failure',
        'OSF':                         'overstrain_failure',
        'RNF':                         'random_failure',
    }

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.df: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    def load_and_preprocess(self) -> pd.DataFrame:
        """Full pipeline: load → rename → engineer features."""
        self.df = pd.read_csv(self.filepath)
        self._rename_columns()
        self._add_timestamps()
        self._engineer_vibration()
        self._engineer_power_and_temp()
        self._add_time_features()
        return self.df


    # Private helpers

    def _rename_columns(self):
        existing = {k: v for k, v in self.COLUMN_MAP.items() if k in self.df.columns}
        self.df = self.df.rename(columns=existing)

    def _add_timestamps(self):
        start = datetime(2024, 1, 1)
        self.df['timestamp'] = pd.date_range(
            start=start, periods=len(self.df), freq='10min'
        )

    def _engineer_vibration(self):
        np.random.seed(42)
        n = len(self.df)
        self.df['vibration_x'] = (
            0.010 * self.df['rot_speed']
            + 0.050 * self.df['torque']
            + np.random.normal(0, 1.5, n)
        )
        self.df['vibration_y'] = (
            0.008 * self.df['rot_speed']
            + 0.040 * self.df['torque']
            + np.random.normal(0, 1.2, n)
        )
        self.df['vibration_z'] = (
            0.012 * self.df['rot_speed']
            + 0.060 * self.df['torque']
            + np.random.normal(0, 1.8, n)
        )
        self.df['vibration_magnitude'] = np.sqrt(
            self.df['vibration_x'] ** 2
            + self.df['vibration_y'] ** 2
            + self.df['vibration_z'] ** 2
        )

    def _engineer_power_and_temp(self):
        self.df['power_consumption'] = (
            self.df['torque'] * self.df['rot_speed'] * 2 * np.pi / 60_000
        )
        self.df['temp_differential'] = (
            self.df['process_temp'] - self.df['air_temp']
        )

    def _add_time_features(self):
        self.df['hour']             = self.df['timestamp'].dt.hour
        self.df['day_of_week']      = self.df['timestamp'].dt.dayofweek
        self.df['is_working_hours'] = self.df['hour'].between(8, 18).astype(int)
