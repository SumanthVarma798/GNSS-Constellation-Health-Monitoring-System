"""The numbers behind the "next step" lines (ui/next_step.py), listed in one place for the team to confirm.

Physical constants live in analysis/forecast_settings.py (Soop, Handbook of Geostationary Orbits). Everything here is
OUR CHOICE: a first proposal, each to be confirmed by the team.
"""

# Where the satellite is and how fast it drifts now: a fit to the newest element sets, never the mean-motion formula
# (that one carries the Earth's flattening, J2, as a bias).
FIT_DAYS = 7                    # use the element sets of the last this many days ...
FIT_MIN_RECORDS = 3             # ... at least this many, since its last east-west burn ...
FIT_MIN_SPAN_DAYS = 1.5         # ... spread over at least this long, else the look ahead waits ("settling")
STALE_ORBIT_DAYS = 10           # newest element set older than this: no look ahead
STATION_DAYS = 90               # its station: the median position over this many days while parked (drift under 0.25 deg/day)
STATION_MIN_RECORDS = 5
CONFIRM_SPAN_SLACK_DAYS = 10    # "parked 90 days": the records cover at least STATION_DAYS less this
CONFIRM_SHARE_NEAR = 0.8        # and this share of them lie within a box of its station: steady, not drifting past

# Its own box, from its routine east-west burns (analysis/burn_classes.py)
MIN_ROUTINE_BURNS = 3           # routine east-west burns in the last year needed to infer it
OWN_BOX_FALLBACK_SHARE = 0.8    # fewer than that: assume this share of our box

# What "due" means
NEAR_DAYS = 30                  # "nothing due" looks this far ahead
SOON_DAYS = 7                   # a burn or edge this near is marked
DATE_SPREAD_SHARE = 0.05        # the date is shown as a range: plus or minus this share of the days ahead ...
DATE_SPREAD_MIN_DAYS = 1        # ... and at least this many days

# Fuel (a class-level guess; the operator's real budget is not public)
DESIGN_LIFE_YEARS = 15          # typical for a GEO or IGSO navigation satellite bus
FUEL_MIN_DAYS = 90              # fewer days of history than this: no yearly rate
YEARS_CAP = 30                  # "years left" above this is shown as "more than 30"

# The burn timeline's ghost marks
GHOST_HORIZON_DAYS = 45

# Medium orbit: years until a plane reaches its limit
STEADY_DEG_PER_YEAR = 0.005     # a plane moving slower than this is "steady"
MEO_YEARS_CAP = 50
