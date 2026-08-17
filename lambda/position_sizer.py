"""
Position Sizer
--------------
Calculates how many shares to buy based on probability confidence.

Formula:
  confidence = (probability - threshold) / (100 - threshold)
  sized_qty  = min_qty + (max_qty - min_qty) * confidence
"""


def calculate_position_size(
    probability: float,
    threshold: float,
    min_qty: float,
    max_qty: float,
) -> float:
    if probability <= threshold:
        return 0.0

    if max_qty <= min_qty:
        return min_qty

    confidence = (probability - threshold) / (100.0 - threshold)
    confidence = max(0.0, min(1.0, confidence))

    raw = min_qty + (max_qty - min_qty) * confidence

    return round(raw, 2)


def confidence_label(probability: float, threshold: float) -> str:
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
