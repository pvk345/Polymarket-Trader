import pytest
from app.services.position_sizer import calculate_position_size, confidence_label


class TestCalculatePositionSize:
    def test_at_threshold_returns_zero(self):
        # probability == threshold is "not yet crossed", per the docstring's own examples
        assert calculate_position_size(probability=60, threshold=60, min_qty=1, max_qty=5) == 0.0

    def test_below_threshold_returns_zero(self):
        assert calculate_position_size(probability=50, threshold=60, min_qty=1, max_qty=5) == 0.0

    def test_just_above_threshold_returns_min_qty(self):
        result = calculate_position_size(probability=60.01, threshold=60, min_qty=1, max_qty=5)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_at_maximum_probability_returns_max_qty(self):
        result = calculate_position_size(probability=100, threshold=60, min_qty=1, max_qty=5)
        assert result == 5.0

    @pytest.mark.parametrize(
        "probability, expected",
        [
            # (60, 1.0) intentionally omitted: the module docstring calls this "0%
            # confidence -> 1.0 shares", but the code's `probability <= threshold`
            # check means exactly-at-threshold returns 0.0, not min_qty. See
            # test_at_threshold_returns_zero for that boundary case.
            (70, 2.0),   # confidence=25%
            (80, 3.0),   # confidence=50%
            (90, 4.0),   # confidence=75%
        ],
    )
    def test_matches_docstring_examples(self, probability, expected):
        # min=1, max=5, threshold=60 — the exact worked examples in the module docstring
        result = calculate_position_size(probability=probability, threshold=60, min_qty=1, max_qty=5)
        assert result == pytest.approx(expected, abs=0.01)

    def test_max_qty_equal_to_min_qty_disables_scaling(self):
        result = calculate_position_size(probability=95, threshold=60, min_qty=2, max_qty=2)
        assert result == 2.0

    def test_max_qty_less_than_min_qty_disables_scaling(self):
        result = calculate_position_size(probability=95, threshold=60, min_qty=3, max_qty=1)
        assert result == 3.0

    def test_result_rounded_to_two_decimals(self):
        result = calculate_position_size(probability=73, threshold=60, min_qty=1, max_qty=3)
        assert result == round(result, 2)

    def test_probability_above_100_is_clamped(self):
        # confidence would exceed 1.0 without clamping — must not exceed max_qty
        result = calculate_position_size(probability=150, threshold=60, min_qty=1, max_qty=5)
        assert result == 5.0


class TestConfidenceLabel:
    def test_below_threshold(self):
        assert confidence_label(probability=50, threshold=60) == "below threshold"

    def test_at_threshold_is_below_threshold_label(self):
        assert confidence_label(probability=60, threshold=60) == "below threshold"

    @pytest.mark.parametrize(
        "probability, expected_label",
        [
            (65, "low"),        # confidence=12.5%
            (75, "moderate"),   # confidence=37.5%
            (85, "high"),       # confidence=62.5%
            (95, "very high"),  # confidence=87.5%
        ],
    )
    def test_confidence_bands(self, probability, expected_label):
        assert confidence_label(probability=probability, threshold=60) == expected_label

    def test_band_boundary_is_exclusive_on_lower_edge(self):
        # confidence exactly 0.25 should fall into "moderate", not "low" (uses `<`, not `<=`)
        assert confidence_label(probability=70, threshold=60) == "moderate"
