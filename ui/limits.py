"""What each measure is judged against on the Overview and Station-keeping pages, named once.

These are the values the scores already use (analysis/drift_analysis.py, analysis/bundled_run.py).
Writing them here does not change a score: it lets the pages say "should be" next to "is".
"""
from analysis.score_rules import (DRIFT_TOLERANCE_TILTED, OVERDUE_AFTER, QZSS_INCLINATION_TOLERANCE,
                                  SCORE_WEIGHTS, SLOT_ALLOWED, SLOT_ALLOWED_TILTED, STATUS_FROM,
                                  STATUS_WORDS, TILT_GEO_BELOW, default_inclination_tolerance,
                                  longitude_remark, longitude_score, orbit_type, status_emoji, status_word)
from config.config import GEO_NOMINAL_ALTITUDE, GRAVEYARD_ORBIT_MIN

# Longitude drift allowed per day. GEO's comes from the gear (drift_tolerance_gso); tilted orbits use this one.
DRIFT_ALLOWED_TILTED = DRIFT_TOLERANCE_TILTED
NOMINAL_HEIGHT_KM = GEO_NOMINAL_ALTITUDE
SET_ASIDE_HEIGHT_KM = GRAVEYARD_ORBIT_MIN

# Orbit types in the order the Overview groups them, each with one plain line. A tilt under 10 degrees is GEO.
ORBIT_TYPES = {
    "GEO": "Geostationary: holds one longitude over the equator, tilt under 10°",
    "IGSO": "Inclined geosynchronous: tilted 10° or more, traces a figure of eight over one longitude",
    "QZO": "Quasi-zenith: QZSS's tilted geosynchronous orbit, high over Japan",
    "MEO": "Medium Earth orbit: about 20,000 km up, goes round about twice a day",
}

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
