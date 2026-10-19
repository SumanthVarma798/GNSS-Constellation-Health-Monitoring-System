"""The Geometry page's settings and words, in one place: where position quality is worked out, how finely
time is stepped, and what each measure means and should be.

The places and the quality bands are the team's, from config/config.py (as app.py used them).
"""
from config.config import (CHINA_KEY_POINTS, DEFAULT_PARAMS, DOP_QUALITY_THRESHOLDS, INACTIVE_SATELLITES,
                           INDIA_EXTREME_POINTS, JAPAN_KEY_POINTS)
from ui import palette

# The page's sections, in the order offered.
SECTIONS = ["Position quality", "Sky view", "Ground tracks", "Orbit trends", "Plane spacing"]

# The places each constellation's position quality is worked out for: {name: (latitude, longitude)}.
PLACES = {"NavIC": INDIA_EXTREME_POINTS, "QZSS": JAPAN_KEY_POINTS, "BeiDou-3": CHINA_KEY_POINTS}

# Satellites the team marks as not in service. "In service" leaves them out, as app.py did by default.
NOT_IN_SERVICE = tuple(INACTIVE_SATELLITES)
SATELLITE_CHOICES = ["In service", "All"]

ELEVATION_MASK_DEG = DEFAULT_PARAMS["elevation_mask_deg"]   # a satellite lower in the sky than this is not counted
ELEVATION_MASK_RANGE = (0, 30)

TREND_HOURS = 24          # position quality over the last day, as app.py's DOP trends
TREND_STEP_MINUTES = 15
SKY_HOURS = 24            # the sky view runs over the next day...
SKY_STEP_MINUTES = 60     # ...an hour a step
TRACK_HOURS = 24          # ground tracks: the next or the past day
TRACK_STEP_MINUTES = 15
TRACK_WINDOWS = ["Next 24 hours", "Past 24 hours"]
CENTRAL_LON_HALF_HOURS = 12        # central longitude: a day of track around each element set...
CENTRAL_LON_STEP_MINUTES = 15      # ...as app.py's historical central longitude, one element set a week

# Dilution of precision. (key, name, what it means in one line). TDOP has no band in config, so no "should be".
DOP_INTRO = ("Dilution of precision (DOP): how much the layout of the satellites in the sky multiplies "
             "ranging error into position error. 1 is ideal; lower is better.")
DOP_MEASURES = [
    ("GDOP", "Overall", "position and clock error together"),
    ("PDOP", "Position", "error in all three directions"),
    ("HDOP", "Across the ground", "error north-south and east-west"),
    ("VDOP", "Height", "error up and down"),
    ("TDOP", "Clock", "error in the receiver's time"),
]
DOP_BANDS = DOP_QUALITY_THRESHOLDS
SEEN_WORDS = "Satellites in view: above the elevation mask. A position needs at least 4."
DOP_SOURCE = "Bands from Isik and others (2020), Robotics 9(3) 66."
# A quality band's status colour. The band's own word is always shown with it.
QUALITY_STATUS = {"Ideal": "ok", "Excellent": "ok", "Good": "ok", "Moderate": "warn", "Fair": "bad", "Poor": "bad"}

# Orbit plane spacing, from analysis/raan_analysis.py.
SPACING_INTRO = ("Satellites that share one ground track should cross the equator northward at evenly spaced "
                 "points around Earth's axis (the node, or right ascension of the ascending node): "
                 "N satellites, 360 ÷ N degrees apart. Uneven spacing leaves gaps in the sky and worsens position "
                 "quality. Shown for information; it is not part of the health score.")
SPACING_STATUS = {"Ideal": "ok", "Good": "ok", "Moderate": "warn", "Poor": "bad", "N/A": "idle"}

# Orbit trends: one row per satellite, one column per measure. (column in the history, name, unit, what it means).
TRENDS = [
    ("INCLINATION", "Tilt", "degrees", "inclination: the angle between the orbit and the equator"),
    ("altitude_km", "Height", "km", "average height above Earth"),
    ("LonDrift_deg_per_day", "Drift", "degrees a day", "how fast the satellite slides east or west"),
    ("central_lon", "Centre", "degrees east", "central longitude: the middle of its ground track over a day"),
]
DRIFT_TOLERANCE_IGSO = 2.0   # degrees a day: analysis.health_assessment's default for inclined orbits

# How each orbit type is drawn. Colour is backed by the shape and the name, never alone.
ORBIT_COLOURS = {"GEO": palette.ACCENT, "IGSO": palette.INK, "QZO": palette.INK}
ORBIT_SYMBOLS = {"GEO": "circle", "IGSO": "diamond", "QZO": "diamond"}
ORBIT_WORDS = {"GEO": "geostationary", "IGSO": "inclined geosynchronous", "QZO": "quasi-zenith"}
OTHER_ORBIT = "IGSO"
