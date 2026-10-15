"""
Model training pipeline. Trains a probability-calibrated gradient boosting
classifier on engineered features and persists the artifact + metadata.

Design choices (kept intentionally simple/robust for a reference implementation):
  - GradientBoostingClassifier wrapped in CalibratedClassifierCV (isotonic)
    so predict_proba outputs are well-calibrated probabilities, not raw scores.
  - Time-ordered train/validation split (no shuffling) to avoid lookahead leakage.
  - Every trained model is versioned and stored in the `models` table/registry.
"""
import json
import os
import uuid
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, brier_score_loss

from app.config import settings
from app.ml.features import FEATURE_COLUMNS, build_features, make_label


def prepare_training_frame(raw_ohlcv: pd.DataFrame, horizon: int = None) -> pd.DataFrame:
    horizon = horizon or settings.PREDICTION_HORIZON_MINUTES
    feats = build_features(raw_ohlcv)
    feats["label_up"] = make_label(raw_ohlcv, horizon=horizon)
    feats = feats.dropna(subset=FEATURE_COLUMNS + ["label_up"])
    return feats


def train_model(raw_ohlcv: pd.DataFrame, artifact_dir: str = None) -> dict:
    """
    Trains a new model version from raw OHLCV history.
    Returns a metadata dict ready to insert into the `models` table.
    """
    artifact_dir = artifact_dir or settings.MODEL_ARTIFACT_DIR
    os.makedirs(artifact_dir, exist_ok=True)

    frame = prepare_training_frame(raw_ohlcv)
    if len(frame) < 200:
        raise ValueError("Not enough labeled rows to train a model (need >= 200).")

    split_idx = int(len(frame) * 0.85)
    train_df, val_df = frame.iloc[:split_idx], frame.iloc[split_idx:]

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df["label_up"].astype(int)
    X_val, y_val = val_df[FEATURE_COLUMNS], val_df["label_up"].astype(int)

    base_clf = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    # Isotonic calibration so predict_proba is a genuine probability estimate,
    # not an overconfident raw score.
    calibrated = CalibratedClassifierCV(base_clf, method="isotonic", cv=3)
    calibrated.fit(X_train, y_train)

    val_proba = calibrated.predict_proba(X_val)[:, 1]
    val_pred = (val_proba >= 0.5).astype(int)

    metrics = {
        "val_accuracy": float(accuracy_score(y_val, val_pred)),
        "val_brier_score": float(brier_score_loss(y_val, val_proba)),
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
    }

    version = f"gb_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    artifact_path = os.path.join(artifact_dir, f"{version}.joblib")
    joblib.dump({"model": calibrated, "feature_columns": FEATURE_COLUMNS}, artifact_path)

    meta = {
        "version": version,
        "algorithm": "gradient_boosting_calibrated_isotonic",
        "training_rows": int(len(frame)),
        "feature_list": FEATURE_COLUMNS,
        "hyperparameters": {
            "n_estimators": 200, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8,
            "calibration": "isotonic", "cv": 3,
        },
        "artifact_path": artifact_path,
        "metrics": metrics,
    }
    return meta


def load_model(artifact_path: str):
    bundle = joblib.load(artifact_path)
    return bundle["model"], bundle["feature_columns"]
