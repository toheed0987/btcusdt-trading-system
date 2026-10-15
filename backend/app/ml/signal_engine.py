"""
Signal engine: converts a model's probability output into a BUY/SELL/HOLD
action, always framed probabilistically.

Hard rule enforced here: the system NEVER claims certainty.
  - Probabilities are clamped into (epsilon, 1-epsilon) — never exactly 0 or 1.
  - "confidence" is a distance-from-uncertainty measure, not a guarantee.
  - Every signal carries a disclaimer and a SHAP-based explanation.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.config import settings


@dataclass
class SignalResult:
    action: str            # BUY | SELL | HOLD
    prob_up: float
    prob_down: float
    confidence: float
    explanation: Dict[str, float] = field(default_factory=dict)
    reasons: list = field(default_factory=list)
    disclaimer: str = ("This is a probabilistic estimate derived from historical patterns. "
                        "It is not a guarantee of future price movement and should not be "
                        "treated as certainty.")


def clamp_probability(p: float, epsilon: float = None) -> float:
    """Never let a probability collapse to exactly 0 or 1."""
    epsilon = epsilon if epsilon is not None else settings.PROB_CLAMP_EPSILON
    return max(epsilon, min(1 - epsilon, float(p)))


def compute_confidence(prob_up: float) -> float:
    """
    Confidence = how far the probability sits from maximum uncertainty (0.5),
    rescaled to [0, 1]. A prob_up of 0.5 => confidence 0 (pure uncertainty).
    A prob_up of 0.99 (clamped) => confidence close to 1, never exactly 1.
    This is NOT a statement of correctness — only of how decisive the
    model's estimate is.
    """
    return clamp_probability(abs(prob_up - 0.5) * 2, epsilon=0.0) * 0.99999999


def generate_signal(raw_prob_up: float, buy_threshold: float, sell_threshold: float,
                     min_confidence: float,
                     explanation: Optional[Dict[str, float]] = None) -> SignalResult:
    """
    raw_prob_up: model's raw predict_proba(class=1) output, already
                 isotonic-calibrated but not yet clamped.
    buy_threshold / sell_threshold: probability thresholds configured in Admin Panel.
    min_confidence: minimum confidence required to act (otherwise -> HOLD).
    """
    prob_up = clamp_probability(raw_prob_up)
    prob_down = clamp_probability(1 - raw_prob_up)
    confidence = compute_confidence(prob_up)

    if prob_up >= buy_threshold and confidence >= min_confidence:
        action = "BUY"
    elif prob_down >= sell_threshold and confidence >= min_confidence:
        action = "SELL"
    else:
        action = "HOLD"

    explanation = explanation or {}
    from app.ml.explain import human_readable_reasons
    reasons = human_readable_reasons(explanation) if explanation else []

    return SignalResult(
        action=action,
        prob_up=round(prob_up, 5),
        prob_down=round(prob_down, 5),
        confidence=round(confidence, 5),
        explanation=explanation,
        reasons=reasons,
    )
