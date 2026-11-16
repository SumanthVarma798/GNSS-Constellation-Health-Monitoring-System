"""The score rules both the analysis and the pages read.

One source for the score bands, part weights, orbit classification, tolerances
and longitude scoring, so the pages stop keeping their own copies.
"""

from config.config import DEFAULT_PARAMS

# Status words by the lowest score that earns them.
STATUS_FROM = [("Healthy", 80), ("Fair", 60), ("Degraded", 40), ("Critical", 0)]
STATUS_WORDS = tuple(word for word, _ in STATUS_FROM)
STATUS_EMOJI = {"Healthy": "🟢", "Fair": "🟡", "Degraded": "🟠", "Critical": "🔴"}

# The overall score's parts and their weights in per cent, with the labels the tiles use.
SCORE_WEIGHTS = [("Inclination", 30), ("Upkeep", 25), ("Drift", 20), ("Longitude", 15), ("Regularity", 10)]
WEIGHTS = {"inc": 0.30, "maintenance": 0.25, "uniformity": 0.10, "drift": 0.20, "longitude": 0.15}
SCORE_PARTS = [("Inclination", "_inc_score"), ("Upkeep", "_maintenance_score"),
               ("Regularity", "_uniformity_score"), ("Drift", "_drift_score"),
               ("Longitude", "Lon Deviation Score")]

TILT_GEO_BELOW = 10.0
QZSS_INCLINATION_TOLERANCE = 4.0
OVERDUE_AFTER = 1.5
DRIFT_TOLERANCE_GEO = 0.05
DRIFT_TOLERANCE_TILTED = 2.0
SLOT_ALLOWED = {"GEO": 0.5}
SLOT_ALLOWED_TILTED = 5.0


def status_word(score):
    """The status word for one overall score."""
    return next(word for word, low in STATUS_FROM if score >= low)


def status_emoji(score):
    """The colour marker that goes with status_word."""
    return STATUS_EMOJI[status_word(score)]


def orbit_type(inclination, constellation):
    """GEO under 10 degrees of tilt, else QZO for QZSS and IGSO otherwise."""
    if inclination is None:
        return "Unclassified"
    if 0.0 <= inclination < TILT_GEO_BELOW:
        return "GEO"
    if inclination >= TILT_GEO_BELOW:
        return "QZO" if constellation == "QZSS" else "IGSO"
    return "Unclassified"


def default_inclination_tolerance(constellation):
    """The inclination tolerance a constellation starts with, before the gear moves it."""
    return QZSS_INCLINATION_TOLERANCE if constellation == "QZSS" else DEFAULT_PARAMS["inclination_tolerance"]


def longitude_score(abs_dev, sat_type):
    """The longitude part score, moved from analysis/bundled_run.py."""
    if sat_type == 'GEO':
        if abs_dev <= 0.5:
            return 100
        if abs_dev <= 1.0:
            return 90 - ((abs_dev - 0.5) / 0.5) * 20
        if abs_dev <= 2.0:
            return 70 - ((abs_dev - 1.0) / 1.0) * 30
        return max(0, 40 - ((abs_dev - 2.0) / 2.0) * 40)
    # IGSO and QZO
    if abs_dev <= 5.0:
        return 100
    if abs_dev <= 10.0:
        return 90 - ((abs_dev - 5.0) / 5.0) * 30
    return max(0, 60 - ((abs_dev - 10.0) / 10.0) * 60)


def longitude_remark(abs_dev, deviation, sat_type, designated_lon):
    """The longitude remark, moved from analysis/bundled_run.py."""
    where = f"({deviation:+.2f}° from {designated_lon}°)"
    if sat_type == 'GEO':
        if abs_dev <= 0.5:
            return f"✅ Excellent longitude slot position {where}"
        if abs_dev <= 1.0:
            return f"✓ Good longitude position {where}"
        return f"⚠️ Longitude deviation from designated slot {where}"
    if abs_dev <= 5.0:
        return f"✅ Within central longitude tolerance {where}"
    return f"⚠️ Central longitude deviation {where}"
