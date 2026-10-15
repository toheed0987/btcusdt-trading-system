"""
Unit tests for the core probabilistic guarantees of the signal engine:
probabilities must never collapse to exact certainty (0 or 1).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ml.signal_engine import clamp_probability, generate_signal, compute_confidence


def test_clamp_probability_never_reaches_extremes():
    assert clamp_probability(0.0) > 0
    assert clamp_probability(1.0) < 1
    assert clamp_probability(0.5) == 0.5


def test_generate_signal_never_claims_certainty():
    sig = generate_signal(raw_prob_up=0.999999, buy_threshold=0.6, sell_threshold=0.6, min_confidence=0.1)
    assert 0 < sig.prob_up < 1
    assert 0 < sig.prob_down < 1
    assert sig.confidence < 1
    assert "not a guarantee" in sig.disclaimer.lower() or "probabilistic" in sig.disclaimer.lower()


def test_generate_signal_hold_below_confidence():
    sig = generate_signal(raw_prob_up=0.61, buy_threshold=0.6, sell_threshold=0.6, min_confidence=0.9)
    assert sig.action == "HOLD"


def test_generate_signal_buy_above_threshold():
    sig = generate_signal(raw_prob_up=0.85, buy_threshold=0.6, sell_threshold=0.6, min_confidence=0.1)
    assert sig.action == "BUY"


def test_generate_signal_sell_above_threshold():
    sig = generate_signal(raw_prob_up=0.10, buy_threshold=0.6, sell_threshold=0.6, min_confidence=0.1)
    assert sig.action == "SELL"


if __name__ == "__main__":
    test_clamp_probability_never_reaches_extremes()
    test_generate_signal_never_claims_certainty()
    test_generate_signal_hold_below_confidence()
    test_generate_signal_buy_above_threshold()
    test_generate_signal_sell_above_threshold()
    print("All signal engine tests passed.")
