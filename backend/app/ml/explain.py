"""
Explainability: computes SHAP feature-importance contributions for a single
prediction so every signal can show "why" it was generated, in plain terms.
"""
from typing import Dict

import numpy as np
import pandas as pd
import shap


_explainer_cache: dict = {}


def _get_explainer(model, model_version: str, background: pd.DataFrame):
    """
    Builds (and caches) a SHAP TreeExplainer for the calibrated model.
    CalibratedClassifierCV wraps multiple base estimators (one per CV fold);
    we explain using the first underlying calibrated classifier's base
    estimator as a representative approximation, which is standard practice
    for tree ensembles wrapped in calibration.
    """
    if model_version in _explainer_cache:
        return _explainer_cache[model_version]

    try:
        base_estimator = model.calibrated_classifiers_[0].estimator
        explainer = shap.TreeExplainer(base_estimator)
    except Exception:
        # Fallback: model-agnostic KernelExplainer on a small background sample
        explainer = shap.KernelExplainer(
            lambda x: model.predict_proba(pd.DataFrame(x, columns=background.columns))[:, 1],
            background.sample(min(50, len(background)), random_state=42),
        )
    _explainer_cache[model_version] = explainer
    return explainer


def explain_prediction(model, model_version: str, feature_row: pd.DataFrame,
                        background: pd.DataFrame, top_n: int = 5) -> Dict[str, float]:
    """
    Returns the top_n most influential features for this specific prediction,
    as {feature_name: shap_contribution}, sorted by absolute impact.
    Positive contribution = pushed probability toward "up".
    """
    explainer = _get_explainer(model, model_version, background)
    shap_values = explainer.shap_values(feature_row)

    # TreeExplainer on a binary classifier returns either a list [class0, class1]
    # or a single array depending on sklearn/shap version; normalize to class-1 array.
    if isinstance(shap_values, list):
        values = np.array(shap_values[1])[0]
    else:
        values = np.array(shap_values)[0]

    contributions = dict(zip(feature_row.columns, values.tolist()))
    ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:top_n]
    return {k: round(float(v), 5) for k, v in ranked}


def human_readable_reasons(explanation: Dict[str, float]) -> list:
    """
    Converts raw SHAP contributions into short human-readable phrases,
    e.g. "RSI(14) pushed probability toward UP".
    """
    labels = {
        "ret_1": "1-minute return", "ret_5": "5-minute return", "ret_15": "15-minute return",
        "ret_60": "60-minute return", "sma_9": "SMA(9) deviation", "sma_21": "SMA(21) deviation",
        "sma_50": "SMA(50) deviation", "ema_9": "EMA(9) deviation", "ema_21": "EMA(21) deviation",
        "rsi_14": "RSI(14)", "macd": "MACD line", "macd_signal": "MACD signal line",
        "macd_hist": "MACD histogram", "bb_width": "Bollinger Band width",
        "bb_pct_b": "Bollinger %B", "atr_14": "Average True Range(14)",
        "volume_zscore_20": "Volume z-score(20)", "momentum_10": "10-period momentum",
        "volatility_20": "20-period volatility", "high_low_range_pct": "High-low range %",
    }
    reasons = []
    for feature, value in explanation.items():
        direction = "UP" if value > 0 else "DOWN"
        reasons.append(f"{labels.get(feature, feature)} pushed the estimate toward {direction} "
                        f"(impact {value:+.4f})")
    return reasons
