"""What each measure is judged against on the Overview and Station-keeping pages, named once.

These are the values the scores already use (analysis/drift_analysis.py, analysis/bundled_run.py).
Writing them here does not change a score: it lets the pages say "should be" next to "is".
"""
from config.config import GEO_NOMINAL_ALTITUDE, GRAVEYARD_ORBIT_MIN

# Longitude drift allowed per day. GEO's comes from the gear (drift_tolerance_gso); tilted orbits use this one,
# assess_drift_health's default.
DRIFT_ALLOWED_TILTED = 2.0
# Distance from its own slot that still earns the full longitude score (bundled_run._longitude_score).
SLOT_ALLOWED = {"GEO": 0.5}
SLOT_ALLOWED_TILTED = 5.0
NOMINAL_HEIGHT_KM = GEO_NOMINAL_ALTITUDE
SET_ASIDE_HEIGHT_KM = GRAVEYARD_ORBIT_MIN
OVERDUE_AFTER = 1.5   # a burn is overdue once 1.5 times its expected interval has passed (health_assessment)
QZSS_INCLINATION_TOLERANCE = 4.0   # QZSS's default inclination tolerance, as assess_constellation and the gear

# The overall score's parts and their weights in per cent (bundled_run's _weights), with the labels the tiles use.
SCORE_WEIGHTS = [("Inclination", 30), ("Upkeep", 25), ("Drift", 20), ("Longitude", 15), ("Regularity", 10)]
# Status words by the lowest score that earns them (bundled_run's bands).
STATUS_FROM = [("Healthy", 80), ("Fair", 60), ("Degraded", 40), ("Critical", 0)]

# Orbit types in the order the Overview groups them, each with one plain line. A tilt under 10 degrees is GEO.
ORBIT_TYPES = {
    "GEO": "Geostationary: holds one longitude over the equator, tilt under 10°",
    "IGSO": "Inclined geosynchronous: tilted 10° or more, traces a figure of eight over one longitude",
    "QZO": "Quasi-zenith: QZSS's tilted geosynchronous orbit, high over Japan",
    "MEO": "Medium Earth orbit: about 20,000 km up, goes round about twice a day",
}
TILT_GEO_BELOW = 10.0

# The three things that keep a navigation satellite useful, and what shows each (ui/system_summary.py).
#   orbit    it is on the orbit it should be on: every part listed scores in the top band (80 or more)
#   station  it is being held there: it is in its slot or in step in its plane, and the part listed is in the top band
#   clock    no clock message that day landed further than CLOCK_STEADY_NS from what the one before predicted
# "slot" is a satellite held over one longitude (the parts are ui.orbit_section.PARTS' labels); "plane" is one in a
# medium orbit (the parts are analysis.meo_geometry's). How often and how evenly a satellite burns (Upkeep,
# Regularity) is how station is kept, not whether it is: it is shown beside the measure, not counted in it.
MEASURES = {"orbit": {"slot": ("Inclination",), "plane": ("plane", "inclination", "height", "eccentricity")},
            "station": {"slot": ("Drift",), "plane": ("spacing",)}}
BURN_PARTS = ("Upkeep", "Regularity")   # a slot satellite's burns: on time, and evenly spaced
CLOCK_STEADY_NS = 30.0   # our choice: 30 ns is 9 m of range, far past a steady clock's steps (about 1 ns)
