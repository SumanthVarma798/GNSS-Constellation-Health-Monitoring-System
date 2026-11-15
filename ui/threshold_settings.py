"""The gear's settings: the limits a reader may move for one visit, and what to know before moving one.

Each setting says what it does, what raising and lowering it does, and when a reader would change it, in words
checked against the code that uses it (analysis/maneuver_detection.py, analysis/health_assessment.py). A value moved
here applies to the system chosen, on that system's pages, for this visit; the Home page always uses the defaults.
"""
from ui import limits

# The settings in the order shown, in two groups. Each: key in config.DEFAULT_PARAMS, label, the name the analysis
# and older notes use, smallest, largest, step, number format, then the four things to know.
BURNS = "Finding burns"
SCORING = "Scoring"
GROUPS = {
    BURNS: "A burn is found where a satellite's orbit steps suddenly and stays stepped. These four decide how sudden "
           "and how large a step must be. They change the burns listed on Station-keeping and, through upkeep and "
           "regularity, the scores of the constellations judged by slot.",
    SCORING: "How strictly a satellite is marked for leaving its target orbit. These three apply to the constellations "
             "judged by longitude slot: NavIC, QZSS and BeiDou-3's high orbit.",
}
# Said in place of the scoring group for a system judged by orbital plane, whose limits are not moved here.
BY_PLANE = ("{name} is judged by orbital plane. Its scoring limits come from its orbit design and are listed under "
            "\"Measured against limits\" on its Overview; they are not changed here.")

SETTINGS = [
    {"key": "z_threshold", "group": BURNS, "label": "How unusual a step must be", "also": "Z-score threshold",
     "low": 1.0, "high": 10.0, "step": 0.5, "format": "%.1f",
     "what": "Each change in orbit size or tilt from one record to the next is compared with that satellite's usual "
             "changes. A step counts only when it is this many times larger than usual.",
     "raise": "Fewer, surer burns. A small burn can be missed.",
     "lower": "More burns found. Ordinary noise in the orbit records can be taken for one.",
     "when": "Raise it when a satellite with noisy records shows burns it did not make. Lower it when a burn you "
             "know of is not listed."},
    {"key": "sma_threshold", "group": BURNS, "label": "Smallest change in orbit size (km)", "also": "SMA change",
     "low": 0.1, "high": 5.0, "step": 0.1, "format": "%.1f",
     "what": "The orbit's size (its semi-major axis) must change by at least this much, and stay changed, to count "
             "as an east-west burn.",
     "raise": "Only larger east-west burns count.",
     "lower": "Smaller burns count, and so does more tracking noise.",
     "when": "Lower it for satellites held in place with small, frequent burns. Raise it when tracking noise of "
             "about a kilometre is being listed as burns."},
    {"key": "inc_threshold", "group": BURNS, "label": "Smallest change in tilt (°)", "also": "Inclination change",
     "low": 0.001, "high": 0.1, "step": 0.001, "format": "%.3f",
     "what": "The orbit's tilt (its inclination) must change by at least this much, and stay changed, to count as a "
             "north-south burn.",
     "raise": "Only larger north-south burns count.",
     "lower": "Smaller tilt corrections count, and so does more noise.",
     "when": "Lower it to see small tilt corrections. Raise it when slow natural tilt change is being listed as "
             "burns."},
    {"key": "persist_window", "group": BURNS, "label": "How long a step must last (records)",
     "also": "Persistence window", "low": 1, "high": 10, "step": 1, "format": "%d",
     "what": "The middle value of this many records before a step is compared with the middle value of as many "
             "after it. A step that does not last is dropped.",
     "raise": "A change must hold for longer: fewer false burns, but two burns close together can be missed.",
     "lower": "A step is accepted sooner: one odd record is more likely to count as a burn.",
     "when": "Raise it when single odd records are being listed as burns."},
    {"key": "inclination_tolerance", "group": SCORING, "label": "Tilt allowed from the target (°)",
     "also": "Inclination tolerance", "low": 0.1, "high": 5.0, "step": 0.1, "format": "%.1f",
     "what": "How far a satellite's tilt may sit from its target before the tilt part of its score falls.",
     "raise": "More forgiving: a satellite whose tilt has wandered still scores well.",
     "lower": "Stricter: a small departure costs points.",
     "when": "Raise it for a constellation that lets tilt wander by design (QZSS starts at 4°). Lower it to see which "
             "satellites are held most tightly."},
    {"key": "drift_tolerance_gso", "group": SCORING, "label": "Drift allowed for a geostationary satellite (°/day)",
     "also": "GEO drift tolerance", "low": 0.01, "high": 0.5, "step": 0.01, "format": "%.2f",
     "what": "How fast a geostationary satellite may drift east or west before the drift part of its score falls. "
             "Satellites on tilted orbits are allowed a fixed 2° a day.",
     "raise": "Slow, deliberate moves between slots are not marked down.",
     "lower": "A satellite starting to leave its slot is caught sooner.",
     "when": "Lower it to watch for early drift. Raise it while a satellite is being moved on purpose."},
    {"key": "maneuver_uniformity_threshold", "group": SCORING, "label": "How uneven burn spacing may be",
     "also": "Manoeuvre uniformity CoV", "low": 0.1, "high": 2.0, "step": 0.1, "format": "%.1f",
     "what": "The spread of the gaps between burns, divided by their average gap: 0 is perfectly regular. Above this "
             "value the regularity part of the score falls.",
     "raise": "Irregular burn schedules still score well.",
     "lower": "Only evenly spaced burns keep full marks.",
     "when": "Raise it for an operator that burns when needed rather than on a calendar."},
]
# QZSS's tilted satellites are allowed more tilt by default, as analysis/bundled_run.py does.
DEFAULTS_BY_SYSTEM = {"QZSS": {"inclination_tolerance": limits.QZSS_INCLINATION_TOLERANCE}}
