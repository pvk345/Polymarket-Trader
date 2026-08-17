"""
Position Sizer
--------------
Calculates how many shares to buy based on probability confidence.

Formula:
  confidence = (probability - threshold) / (100 - threshold)
  sized_qty  = min_qty + (max_qty - min_qty) * confidence

Examples with min=1, max=5, threshold=60:
  prob=60% → confidence=0%  → 1.0 shares  (just crossed)
  prob=70% → confidence=25% → 2.0 shares
  prob=80% → confidence=50% → 3.0 shares
  prob=90% → confidence=75% → 4.0 shares
  prob=99% → confidence=97% → 4.9 shares
"""

import math


def calculate_position_size(
    probability: float,
    threshold: float,
    min_qty: float,
    max_qty: float,
) -> float:
    """
    Scale position size linearly from min_qty to max_qty
    based on how far probability is above the threshold.
    """
    if probability <= threshold:
        return 0.0  # condition not met

    if max_qty <= min_qty:
        return min_qty  # no scaling configured

    # How far above threshold as a fraction of remaining space
    confidence = (probability - threshold) / (100.0 - threshold)
    confidence = max(0.0, min(1.0, confidence))  # clamp 0-1

    raw = min_qty + (max_qty - min_qty) * confidence

    # Round to nearest 0.01 (fractional shares supported by Alpaca)
    return round(raw, 2)


def confidence_label(probability: float, threshold: float) -> str:
    """Human-readable confidence level."""
    if probability <= threshold:
        return "below threshold"
    confidence = (probability - threshold) / (100.0 - threshold)
    if confidence < 0.25:
        return "low"
    elif confidence < 0.50:
        return "moderate"
    elif confidence < 0.75:
        return "high"
    else:
        return "very high"