"""The medians either side of a candidate burn (analysis/maneuver_detection.py) give exactly what the per-row
np.median version gave, edges and gaps included; that version is kept here as the reference."""
import numpy as np
import pandas as pd
import pytest

from analysis.maneuver_detection import post_median, pre_median


def _pre_reference(s, half):
    return s.rolling(window=2 * half + 1, min_periods=1).apply(
        lambda arr: np.median(arr[:-half]) if len(arr) > half else np.nan, raw=True)


def _post_reference(s, half):
    return s.shift(-half).rolling(window=2 * half + 1, min_periods=1).apply(
        lambda arr: np.median(arr[half:]) if len(arr) > half else np.nan, raw=True)


@pytest.mark.parametrize("half", [1, 2, 3, 5, 10])
@pytest.mark.parametrize("length", [0, 1, 2, 3, 7, 25, 200])
def test_same_as_the_per_row_median_with_gaps(half, length):
    rng = np.random.default_rng(half * 1000 + length)
    s = pd.Series(42164 + rng.normal(0, 0.3, length).round(2))   # rounded, so even windows hit ties
    s[rng.random(length) < 0.1] = np.nan
    for got, want in ((pre_median(s, half), _pre_reference(s, half)), (post_median(s, half), _post_reference(s, half))):
        assert np.array_equal(got.to_numpy(), want.to_numpy(), equal_nan=True)
