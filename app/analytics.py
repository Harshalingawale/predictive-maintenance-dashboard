
# ML models: health score, failure prediction, anomaly detection

import numpy as np
import pandas as pd
import warnings
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split, cross_val_score

warnings.filterwarnings('ignore')


class AnalyticsEngine:
    """
    Encapsulates all ML analytics:
      - Health score calculation (weighted degradation index)
      - Random Forest failure probability model
      - Isolation Forest anomaly detection
    """

    HEALTH_FEATURES = [
        'tool_wear', 'vibration_magnitude', 'temp_differential',
        'power_consumption', 'air_temp', 'process_temp',
    ]
    HEALTH_WEIGHTS = {
        'tool_wear': 0.25, 'vibration_magnitude': 0.20,
        'temp_differential': 0.15, 'power_consumption': 0.15,
        'air_temp': 0.15, 'process_temp': 0.10,
    }

    FAILURE_FEATURES = [
        'air_temp', 'process_temp', 'rot_speed', 'torque', 'tool_wear',
        'vibration_magnitude', 'temp_differential', 'power_consumption',
        'hour', 'is_working_hours',
    ]

    ANOMALY_FEATURES = [
        'vibration_magnitude', 'temp_differential', 'power_consumption', 'rot_speed',
    ]

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.scaler = StandardScaler()
        self.models: dict = {}

    # Public API

    def calculate_health_score(self) -> pd.DataFrame:
        """Add 'health_score' column (0–100, higher = healthier)."""
        features = [f for f in self.HEALTH_FEATURES if f in self.df.columns]
        normalized = pd.DataFrame(
            self.scaler.fit_transform(self.df[features]),
            columns=features,
        )
        degradation = sum(
            normalized[f].abs() * self.HEALTH_WEIGHTS.get(f, 0)
            for f in features
        )
        max_deg = degradation.max()
        self.df['health_score'] = (
            (100 - degradation * 100 / max_deg).clip(0, 100)
            if max_deg > 0
            else 100.0
        )

        bins   = [0, 40, 60, 80, 100]
        labels_en = ['Poor', 'Fair', 'Good', 'Excellent']
        labels_de = ['Schlecht', 'Akzeptabel', 'Gut', 'Ausgezeichnet']
        self.df['health_status_en'] = pd.cut(self.df['health_score'], bins=bins, labels=labels_en)
        self.df['health_status_de'] = pd.cut(self.df['health_score'], bins=bins, labels=labels_de)
        return self.df

    def train_failure_model(self) -> tuple:
        """
        Train a Random Forest classifier to predict 'failure'.
        Adds 'failure_prob', 'risk_level_*', 'estimated_rul_hours',
        and 'maintenance_urgency_*' columns.

        Returns (model, cv_scores) or (None, None) if 'failure' column missing.
        """
        if 'failure' not in self.df.columns:
            print("Warning: 'failure' column not found. Skipping model training.")
            return None, None

        features = [f for f in self.FAILURE_FEATURES if f in self.df.columns]
        X, y = self.df[features], self.df['failure']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        model = RandomForestClassifier(
            n_estimators=100, max_depth=10,
            min_samples_split=5, min_samples_leaf=2,
            class_weight='balanced', random_state=42, n_jobs=-1,
        )
        model.fit(X_train, y_train)
        cv_scores = cross_val_score(model, X, y, cv=3, scoring='roc_auc')

        self.models['failure_model'] = model
        self.models['cv_scores']     = cv_scores
        self.models['features']      = features

        self.df['failure_prob'] = model.predict_proba(X)[:, 1]

        prob_bins  = [0, .1, .3, .6, .8, 1.0]
        self.df['risk_level_en'] = pd.cut(
            self.df['failure_prob'], bins=prob_bins,
            labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'],
        )
        self.df['risk_level_de'] = pd.cut(
            self.df['failure_prob'], bins=prob_bins,
            labels=['Sehr Niedrig', 'Niedrig', 'Mittel', 'Hoch', 'Sehr Hoch'],
        )
        self.df['estimated_rul_hours'] = (
            (100 - self.df['health_score']) / 100 * 1000
        ).clip(10, 1000)

        conditions = [
            (self.df['failure_prob'] > 0.7) | (self.df['health_score'] < 30),
            (self.df['failure_prob'] > 0.4) | (self.df['health_score'] < 50),
            self.df['health_score'] >= 50,
        ]
        self.df['maintenance_urgency_en'] = np.select(
            conditions, ['Immediate', 'Scheduled', 'Monitor'], default='Monitor'
        )
        self.df['maintenance_urgency_de'] = np.select(
            conditions, ['Sofort', 'Geplant', 'Überwachen'], default='Überwachen'
        )
        return model, cv_scores

    def detect_anomalies(self) -> pd.DataFrame:
        """Add boolean 'is_anomaly' column via Isolation Forest."""
        features = [f for f in self.ANOMALY_FEATURES if f in self.df.columns]
        iso = IsolationForest(contamination=0.05, random_state=42)
        self.df['is_anomaly'] = iso.fit_predict(self.df[features]) == -1
        return self.df