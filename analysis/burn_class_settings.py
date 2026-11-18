"""Every number the burn classifier (analysis/burn_classes.py) uses, named, so a reviewer can see and change each one.

Physical constants are measured or taken from the literature. Everything marked OUR CHOICE is a judgement made here,
not a standard: the team is asked to confirm each before a count built on it is shown.
"""

# ---- physics (GEO, semi-major axis 42,164 km) -----------------------------------------------------------------------
DRIFT_PER_KM = -0.012842        # change of longitude drift, degrees a day, per km of semi-major axis (lower drifts east)
DV_PER_KM = 0.03646             # m/s of tangential burn per km of semi-major axis change
DV_PER_DEG_INCLINATION = 53.7   # m/s per degree of GEO inclination change (3.075 km/s x 1 degree in radians)
LON_ACCEL_K = 0.0017            # degrees/day^2, peak longitude acceleration (Soop, Handbook of Geostationary Orbits)
LON_ACCEL_STABLE = 75.1         # degrees east, the stable point the acceleration pulls towards
LON_ACCEL_MIN = 1.0e-4          # degrees/day^2: weaker than this (a slot near a stable or unstable point) the cycle model is not used

# ---- context windows (OUR CHOICE, team to confirm) ------------------------------------------------------------------
BEFORE_DAYS = 2.0               # records this many days up to the last one before the burn give "before"
AFTER_DAYS = 2.0                # records from the first one after the burn for this many days give "after"
DRIFT_NOISE = 0.005             # degrees/day: a drift smaller than this has no usable sign (a routine cycle swings +-0.02 to 0.04)

# ---- rule 0: artefact (OUR CHOICE, team to confirm) -----------------------------------------------------------------
EW_MAX_DV = 20.0                # m/s: a single east-west burn above this is not a station-keeping burn (a relocation is ~4 m/s)
NS_MAX_DEG = 1.0                # degrees: an inclination step above this costs ~50 m/s
CONTAMINATED_DAYS = 1.0         # a burn whose window starts this close to the end of an impossible step starts on the same bad record
REVERSAL_DAYS = 90              # a step that is undone within this many days ...
REVERSAL_NET = 0.25             # ... to within this share of its size ...
REVERSAL_SERIES_SHARE = 0.25    # ... while the series between the two moved less than this share of the step, is a record error

# ---- rule 1: relocation (OUR CHOICE, team to confirm) ---------------------------------------------------------------
RELOCATION_MIN_KM = 19.0        # each burn of the pair changes the semi-major axis by at least this (drift ~0.25 degrees a day)
RELOCATION_MIN_DRIFT = 0.25     # degrees/day: drift between the pair, as commissioning.SETTLED_DRIFT_DEG_PER_DAY
RELOCATION_MIN_DAYS = 2.0       # the drift lasts at least this long between the two burns
RELOCATION_MAX_DAYS = 400.0     # and the second burn follows within this many days of the first
RELOCATION_SHIFT_DEG = 5.0      # a big burn with no mate is still a relocation if the satellite's longitude moved this far across it
LATER_FROM_DAYS = 3.0           # "later" for that move: records from this many days after the burn ...
LATER_TO_DAYS = 30.0            # ... to this many

# ---- rule 2: end of life (OUR CHOICE, team to confirm) --------------------------------------------------------------
DISPOSAL_SEQUENCE_DAYS = 45     # raising burns within this many days before the one reaching the graveyard belong to it

# ---- rule 3 and 4: routine (OUR CHOICE, team to confirm) ------------------------------------------------------------
MIN_PRIORS = 3                  # own earlier burns needed before a satellite is its own norm
MIN_PEERS = 3                   # burns of its peers (same constellation, same orbit type, same kind) when it has too few
MIN_PEERS_NS = 2                # the same for north-south burns, of which a satellite makes two or three a year
INTERVAL_MARGIN = 0.25          # T1: inside the own inter-quartile range widened by this share, or this share of the model interval
SIZE_BAND = (0.5, 2.0)          # T2: size as a multiple of the norm
BOX_GEO = 0.5                   # degrees: the longitude box of a GEO satellite (analysis/score_rules.SLOT_ALLOWED)
BOX_TILTED = 5.0                # degrees: the central-longitude box of a tilted one (analysis/score_rules.SLOT_ALLOWED_TILTED)
NS_MIN_GAP_DAYS = 40            # rule 4: days since the satellite's previous north-south burn
NS_MAX_DELTA_A = 3.0            # rule 4: km, a north-south burn that also moves the semi-major axis more is not one ...
ACCOMPANIED_DAYS = 1.0          # ... unless an east-west burn of the same satellite is this close: that one is judged on its own

# ---- rule 5: response after being off (OUR CHOICE, team to confirm) -------------------------------------------------
DRIFT_TOLERANCE_GEO = 0.05      # degrees/day, analysis/score_rules.DRIFT_TOLERANCE_GEO
CLUSTER_BURNS = 3               # this many burns ...
CLUSTER_DAYS = 7                # ... within this many days
QUICK_REVERSAL_DAYS = 3         # opposite-sign east-west burns this close (and not a relocation)

# ---- summary (OUR CHOICE, team to confirm) --------------------------------------------------------------------------
WINDOW_DAYS = 365
MIN_DECIDED = 8                 # fewer decided burns than this in the window and a constellation's share is "too few to rate"
CONFIDENCE_LEVELS = ("low", "medium", "high")
COUNTED_CONFIDENCE = "medium"   # irregular burns are counted at this confidence or better
WILSON_Z = 1.96                 # 95 per cent interval
