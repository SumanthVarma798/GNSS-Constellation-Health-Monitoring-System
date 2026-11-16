"""The score rules in one place, checked at the edges that matter."""

import pytest

from analysis import score_rules
from ui import surfaces


@pytest.mark.parametrize("score, word", [
    (80, "Healthy"), (79.9, "Fair"), (60, "Fair"),
    (59.9, "Degraded"), (40, "Degraded"), (39.9, "Critical"),
])
def test_status_word_at_the_band_edges(score, word):
    assert score_rules.status_word(score) == word


@pytest.mark.parametrize("inclination, constellation, orbit", [
    (9.99, "NavIC", "GEO"),
    (10.0, "NavIC", "IGSO"),
    (10.0, "QZSS", "QZO"),
    (None, "QZSS", "Unclassified"),
])
def test_orbit_type_at_the_tilt_edges(inclination, constellation, orbit):
    assert score_rules.orbit_type(inclination, constellation) == orbit


@pytest.mark.parametrize("deviation, orbit, score", [
    (0.5, "GEO", 100),
    (1.0, "GEO", 70),
    (2.0, "GEO", 40),
    (5.0, "IGSO", 100),
    (10.0, "IGSO", 60),
])
def test_longitude_score_at_its_edges(deviation, orbit, score):
    assert score_rules.longitude_score(deviation, orbit) == score


def test_surfaces_band_and_score_rules_agree_on_the_same_score():
    tone = {"Healthy": "ok", "Fair": "warn", "Degraded": "bad", "Critical": "bad"}
    for score in (80, 79.9, 60, 59.9, 40, 39.9):
        assert surfaces.band(score) == tone[score_rules.status_word(score)]


def test_qzss_default_inclination_tolerance_is_four_degrees():
    assert score_rules.default_inclination_tolerance("QZSS") == 4.0
    assert score_rules.default_inclination_tolerance("NavIC") == 1.0
