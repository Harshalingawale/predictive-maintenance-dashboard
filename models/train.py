"""
models/train.py
───────────────
Trains a failure prediction model on the SAP dataset.
Run this from VS Code:  F5 → select "Train ML Model"
Or from terminal:       python models/train.py
"""

import sys
import os
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import Pipeline
from dotenv import load_dotenv

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from utils.data_loader import SAPDataLoader
from utils.health_score import compute_health_score


# ─── Feature Configuration ────────────────────────────────────────────────────

# CNC features for the model
CNC_FEATURES = [
    "SPINDLE_SPEED_RPM", "SPINDLE_LOAD_PCT", "COOLANT_TEMP_C",
    "X_VIBRATION_MMS", "Y_VIBRATION_MMS", "TOOL_WEAR_PCT",
    "POWER_CONSUMPTION_KW", "SERVO_CURRENT_A",
    "TOTAL_DOWNTIME_H", "CORRECTIVE_ORDERS", "CORRECTIVE_RATIO",
    "OEE", "AVAILABILITY", "PERFORMANCE",
    "MTBF_H", "MTTR_H",
]

# REP features for the model
REP_FEATURES = [
    "J1_VIBRATION_MMS", "J2_BACKLASH_DEG", "J3_TEMPERATURE_C",
    "J4_CURRENT_A", "WELD_QUALITY_PCT", "GRIPPER_FORCE_N",
    "CONTROLLER_TEMP_C", "POSITIONING_ACC_MM", "CYCLE_TIME_S",
    "POWER_CONSUMPTION_KW",
    "TOTAL_DOWNTIME_H", "CORRECTIVE_ORDERS", "CORRECTIVE_RATIO",
    "OEE", "AVAILABILITY", "PERFORMANCE",
    "MTBF_H", "MTTR_H",
]


def prepare_features(master_df: pd.DataFrame, machine_type: str) -> tuple:
    """
    Prepare feature matrix X and label vector y for training.
    Label: 1 = machine at risk (health score < 60), 0 = healthy
    """
    df = master_df[master_df["MACHINE_TYPE"] == machine_type].copy()

    # Add health score as a feature AND use it to generate labels
    df["HEALTH_SCORE"] = df.apply(compute_health_score, axis=1)
    df["FAILURE_RISK"] = (df["HEALTH_SCORE"] < 60).astype(int)

    features = CNC_FEATURES if machine_type == "CNC" else REP_FEATURES

    # Keep only columns that exist in the data
    available = [f for f in features if f in df.columns]
    missing   = [f for f in features if f not in df.columns]
    if missing:
        print(f"  [Warning] Missing features for {machine_type}: {missing}")

    X = df[available].fillna(0)
    y = df["FAILURE_RISK"]

    return X, y, available


def train_model(X: pd.DataFrame, y: pd.Series, model_name: str) -> dict:
    """Train and evaluate a model. Returns results dict."""
    if len(y.unique()) < 2:
        print(f"  [Skip] Not enough class variety for {model_name}")
        return None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    # Pipeline: scale + gradient boosted trees
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model",  GradientBoostingClassifier(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )),
    ])

    pipeline.fit(X_train, y_train)

    # Evaluate
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    auc    = roc_auc_score(y_test, y_prob)
    cv_scores = cross_val_score(pipeline, X, y, cv=5, scoring="roc_auc")

    print(f"\n  [{model_name}] Results:")
    print(f"  AUC (test)    : {auc:.3f}")
    print(f"  AUC (5-fold)  : {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
    print(classification_report(y_test, y_pred, target_names=["Healthy","At Risk"]))

    # Feature importance
    model    = pipeline.named_steps["model"]
    feat_imp = pd.Series(model.feature_importances_, index=X.columns)
    print(f"  Top 5 features:\n{feat_imp.nlargest(5).to_string()}\n")

    return {
        "pipeline":     pipeline,
        "features":     list(X.columns),
        "auc":          auc,
        "cv_auc_mean":  cv_scores.mean(),
        "feature_importance": feat_imp.to_dict(),
    }


def main():
    print("=" * 55)
    print("  BRUSS – ML Model Training")
    print("=" * 55)

    # Load data
    loader = SAPDataLoader()
    loader.load()
    master = loader.master_df

    results = {}
    model_path = Path(os.getenv("MODEL_PATH", "models/failure_model.pkl"))
    model_path.parent.mkdir(exist_ok=True)

    # Train CNC model
    print("\n[1/2] Training CNC failure prediction model...")
    X_cnc, y_cnc, feats_cnc = prepare_features(master, "CNC")
    if len(X_cnc) > 0:
        cnc_result = train_model(X_cnc, y_cnc, "CNC")
        if cnc_result:
            results["CNC"] = cnc_result

    # Train REP model
    print("\n[2/2] Training REP failure prediction model...")
    X_rep, y_rep, feats_rep = prepare_features(master, "REP")
    if len(X_rep) > 0:
        rep_result = train_model(X_rep, y_rep, "REP")
        if rep_result:
            results["REP"] = rep_result

    # Save both models together
    joblib.dump(results, model_path)
    print(f"\n✅ Models saved to: {model_path}")
    print(f"   CNC AUC: {results.get('CNC', {}).get('auc', 'N/A')}")
    print(f"   REP AUC: {results.get('REP', {}).get('auc', 'N/A')}")
    print("\nNext: Press F5 → 'Run Dashboard' to start the app.")


if __name__ == "__main__":
    main()
