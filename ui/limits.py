"""What each measure is judged against on the Overview and Station-keeping pages, named once.

These are the values the scores already use (analysis/drift_analysis.py, analysis/bundled_run.py).
Writing them here does not change a score: it lets the pages say "should be" next to "is".
"""
import math

from analysis.score_rules import (DRIFT_TOLERANCE_TILTED, OVERDUE_AFTER, QZSS_INCLINATION_TOLERANCE,
                                  SCORE_WEIGHTS, SLOT_ALLOWED, SLOT_ALLOWED_TILTED, STATUS_FROM,
                                  STATUS_WORDS, TILT_GEO_BELOW, default_inclination_tolerance,
                                  longitude_remark, longitude_score, orbit_type, status_emoji, status_word)
from config.config import GEO_NOMINAL_ALTITUDE, GRAVEYARD_ORBIT_MIN

# Longitude drift allowed per day. GEO's comes from the gear (drift_tolerance_gso); tilted orbits use this one.
DRIFT_ALLOWED_TILTED = DRIFT_TOLERANCE_TILTED
NOMINAL_HEIGHT_KM = GEO_NOMINAL_ALTITUDE
SET_ASIDE_HEIGHT_KM = GRAVEYARD_ORBIT_MIN

# A geosynchronous satellite on an orbit that is not quite a circle (eccentricity e) speeds up and slows down once a
# day, so it swings east and west of its mean longitude by about 2 x e radians of its orbit's radius.
GEO_RADIUS_KM = 42164.0


def ecc_swing_km(e, radius_km=GEO_RADIUS_KM):
    """How far, in km, a geosynchronous satellite of eccentricity `e` swings east or west of its mean longitude: 2 e a."""
    return 2 * e * radius_km


# A geostationary satellite is held within SLOT_ALLOWED["GEO"] degrees of its slot, so it may swing no further than that:
# an eccentricity of half that angle in radians (0.5 degrees: 0.0044, about 368 km). A limit set for a tilted orbit
# (QZSS's 0.099, BeiDou-3's 0.05) is far wider and would let a geostationary satellite swing some 10 degrees.
GEO_ECC_MAX = math.radians(SLOT_ALLOWED["GEO"]) / 2

# Orbit types in the order the Overview groups them, each with one plain line. A tilt under 10 degrees is GEO.
ORBIT_TYPES = {
    "GEO": "Geostationary: holds one longitude over the equator, tilt under 10°",
    "IGSO": "Inclined geosynchronous: tilted 10° or more, traces a figure of eight over one longitude",
    "QZO": "Quasi-zenith: QZSS's tilted geosynchronous orbit, high over Japan",
    "MEO": "Medium Earth orbit: about 20,000 km up, goes round about twice a day",
}

# The things that keep a navigation satellite useful, and what shows each (ui/system_summary.py); the burn record, the
# fourth, is below.
#   orbit    it is on the orbit it should be on: every part listed scores in the top band (80 or more)
#   station  it is being held there: it is in its slot or in step in its plane, and the part listed is in the top band
#   clock    no clock message that day landed further than CLOCK_STEADY_NS from what the one before predicted
# "slot" is a satellite held over one longitude (the parts are ui.orbit_section.PARTS' labels); "plane" is one in a
# medium orbit (the parts are analysis.meo_geometry's). How often and how evenly a satellite burns (Upkeep,
# Regularity) is how station is kept, not whether it is: it is shown beside the measure, not counted in it.
MEASURES = {"orbit": {"slot": ("Inclination",), "plane": ("plane", "inclination", "height", "eccentricity")},
            "station": {"slot": ("Drift",), "plane": ("spacing",)}}
BURN_PARTS = ("Upkeep", "Regularity")   # a slot satellite's burns: on time, and evenly spaced
# The burn record, the score's fourth measure ("care"): how regularly the satellite is looked after, from the kind of each
# burn (analysis/burn_classes.py; its thresholds are in analysis/burn_class_settings.py). OUR CHOICE, for the team to confirm.
#   A satellite passes when it made no irregular burn (a response, or off its pattern, at medium confidence or better)
#   in the last CARE_RECENT_DAYS days AND its irregular share of the judged burns of the last 365 days is at most
#   CARE_MAX_SHARE. With fewer than CARE_MIN_JUDGED judged burns it is not judged. Relocations and end-of-life burns are
#   planned: neutral, in neither count.
CARE_RECENT_DAYS = 90
CARE_MAX_SHARE = 0.25
CARE_MIN_JUDGED = 3
CLOCK_STEADY_NS = 30.0   # our choice: 30 ns is 9 m of range, far past a steady clock's steps (about 1 ns)
# The clock score judges only the satellites in service today, so a constellation whose clocks have failed in orbit
# can still score high: the record of those that failed (registry/clock_record.csv) is said beside it.
CLOCK_RECORD = ("Clock record: {lost} of {launched} {name} satellites launched are reported to have lost atomic clocks in orbit.",
                "The score above judges only the satellites in service today. Sources:")

# A constellation's score (ui.system_summary.score_of) weighs its four measures by what a failure costs its users,
# which depends on the mission. Our choice, for the team to confirm; Need help reading this page? gives the reasons
# (ui/home_settings.py HOW, "Weights"). A regional constellation has 7 or 8 satellites, none spare, all in every
# user's sky: a bad clock corrupts every fix in its service area with nothing to stand in, and a satellite off its
# station moves coverage off the region. A global one has 24 to 35, 8 to 12 in view: a receiver can leave out one bad
# clock, a neighbour covers one satellite out of step, and the planes and spacing set the coverage everywhere.
MISSION = {"NavIC": "regional", "QZSS": "regional"}   # every other constellation is global
# The burn record ("care") weighs 10% for every mission, taken in proportion from the other three (clock, station, orbit):
# our choice, for the team to confirm. A constellation with no burn history (the medium-orbit ones) has no burn record
# to read, and the other three are scaled back up to 100%, so its score is what it was.
MEASURE_WEIGHTS = {"regional": {"clock": 0.45, "station": 0.27, "orbit": 0.18, "care": 0.10},
                   "global": {"clock": 0.36, "orbit": 0.315, "station": 0.225, "care": 0.10}}
