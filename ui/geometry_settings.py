"""The Geometry page's settings and words, in one place: where position quality is worked out, how finely
time is stepped, and what each measure means and should be.

The places and the quality bands are the team's, from config/config.py (as app.py used them).
"""
from config.config import (CHINA_KEY_POINTS, DEFAULT_PARAMS, DOP_QUALITY_THRESHOLDS, INACTIVE_SATELLITES,
                           INDIA_EXTREME_POINTS, JAPAN_KEY_POINTS, MEO_SYSTEMS)
from analysis.score_rules import DRIFT_TOLERANCE_TILTED
from ui import palette

# The page's sections, in the order offered.
SECTIONS = ["Position quality", "Sky and ground", "Orbit trends"]

# The places each constellation's position quality is worked out for: {name: (latitude, longitude)}.
# The global systems (MEO) have no service area of their own to bound, so they take places already on the regional
# lists, spread from 7° N to 54° N and 77° E to 140° E. Our choice; any other place can be typed or clicked.
GLOBAL_PLACES = {name: places[name] for places, name in (
    (INDIA_EXTREME_POINTS, "Capital (Delhi)"), (INDIA_EXTREME_POINTS, "Southernmost (Indira Point)"),
    (CHINA_KEY_POINTS, "Capital (Beijing)"), (CHINA_KEY_POINTS, "Northernmost (Mohe, Heilongjiang)"),
    (JAPAN_KEY_POINTS, "Capital (Tokyo)"))}
PLACES = {"NavIC": INDIA_EXTREME_POINTS, "QZSS": JAPAN_KEY_POINTS, "BeiDou-3": CHINA_KEY_POINTS,
          **{system: GLOBAL_PLACES for system in MEO_SYSTEMS}}

# World cities a reader can choose as "your place" and to compare with: {"city, country": (latitude, longitude)}.
# Capitals and large cities on every continent, so a reader from anywhere finds somewhere they know. Our choice, in
# degrees to two places; any other place can still be typed or clicked in Sky and ground.
CITIES = {
    "Hyderabad, India": (17.39, 78.49), "Delhi, India": (28.61, 77.21), "Mumbai, India": (19.08, 72.88),
    "Chennai, India": (13.08, 80.27), "Kolkata, India": (22.57, 88.36), "Bengaluru, India": (12.97, 77.59),
    "Port Blair, India": (11.62, 92.73), "Srinagar, India": (34.08, 74.80),
    "Chongqing, China": (29.56, 106.55), "Beijing, China": (39.90, 116.41), "Shanghai, China": (31.23, 121.47),
    "Guangzhou, China": (23.13, 113.26), "Urumqi, China": (43.83, 87.62), "Harbin, China": (45.80, 126.54),
    "Lhasa, China": (29.65, 91.17), "Hong Kong, China": (22.32, 114.17),
    "Tokyo, Japan": (35.69, 139.69), "Osaka, Japan": (34.69, 135.50), "Sapporo, Japan": (43.06, 141.35),
    "Naha, Japan": (26.21, 127.68), "Seoul, South Korea": (37.57, 126.98), "Ulaanbaatar, Mongolia": (47.89, 106.91),
    "Bangkok, Thailand": (13.76, 100.50), "Hanoi, Vietnam": (21.03, 105.85), "Singapore, Singapore": (1.35, 103.82),
    "Jakarta, Indonesia": (-6.21, 106.85), "Manila, Philippines": (14.60, 120.98), "Dhaka, Bangladesh": (23.81, 90.41),
    "Karachi, Pakistan": (24.86, 67.01), "Kathmandu, Nepal": (27.72, 85.32), "Colombo, Sri Lanka": (6.93, 79.86),
    "Tashkent, Uzbekistan": (41.30, 69.24), "Dubai, United Arab Emirates": (25.20, 55.27),
    "Tehran, Iran": (35.69, 51.39), "Riyadh, Saudi Arabia": (24.71, 46.68), "Istanbul, Turkey": (41.01, 28.98),
    "Sydney, Australia": (-33.87, 151.21), "Perth, Australia": (-31.95, 115.86), "Auckland, New Zealand": (-36.85, 174.76),
    "Cairo, Egypt": (30.04, 31.24), "Lagos, Nigeria": (6.52, 3.38), "Nairobi, Kenya": (-1.29, 36.82),
    "Addis Ababa, Ethiopia": (9.03, 38.74), "Johannesburg, South Africa": (-26.20, 28.05),
    "Casablanca, Morocco": (33.57, -7.59), "Kinshasa, DR Congo": (-4.44, 15.27),
    "London, United Kingdom": (51.51, -0.13), "Paris, France": (48.86, 2.35), "Berlin, Germany": (52.52, 13.41),
    "Madrid, Spain": (40.42, -3.70), "Rome, Italy": (41.90, 12.50), "Moscow, Russia": (55.76, 37.62),
    "Stockholm, Sweden": (59.33, 18.07), "Reykjavik, Iceland": (64.15, -21.94),
    "New York, United States": (40.71, -74.01), "Los Angeles, United States": (34.05, -118.24),
    "Chicago, United States": (41.88, -87.63), "Anchorage, United States": (61.22, -149.90),
    "Honolulu, United States": (21.31, -157.86), "Toronto, Canada": (43.65, -79.38),
    "Vancouver, Canada": (49.28, -123.12), "Mexico City, Mexico": (19.43, -99.13), "Bogota, Colombia": (4.71, -74.07),
    "Lima, Peru": (-12.05, -77.04), "Sao Paulo, Brazil": (-23.55, -46.63), "Buenos Aires, Argentina": (-34.60, -58.38),
    "Santiago, Chile": (-33.45, -70.67), "McMurdo Station, Antarctica": (-77.85, 166.67),
}
# "Your place" and the place to compare it with, until the reader chooses: a city in each constellation's service area
# (and one far from it, to compare against). The global constellations start at the same pair.
DEFAULT_PLACES = {"NavIC": ("Hyderabad, India", "Chongqing, China"), "QZSS": ("Tokyo, Japan", "Hyderabad, India"),
                  "BeiDou-3": ("Beijing, China", "Hyderabad, India")}
GLOBAL_DEFAULT_PLACES = ("Hyderabad, India", "London, United Kingdom")
CITY_STEP_MINUTES = 5     # the cities' position quality is worked out on the clock's five-minute steps, so it can be kept
MAP_REGION_PAD_DEG = 14   # a regional constellation's map shows its key places and this much around them
YOU_LABEL, COMPARE_LABEL = "Your place", "Compare with"


def default_places(constellation):
    return DEFAULT_PLACES.get(constellation, GLOBAL_DEFAULT_PLACES)


def city_short(name):
    """'Chongqing' for 'Chongqing, China': the word drawn beside a mark on a map."""
    return name.split(",")[0]


# Satellites the team marks as not in service. "In service" leaves them out, as app.py did by default.
NOT_IN_SERVICE = tuple(INACTIVE_SATELLITES)
SATELLITE_CHOICES = ["In service", "All"]

ELEVATION_MASK_DEG = DEFAULT_PARAMS["elevation_mask_deg"]   # a satellite lower in the sky than this is not counted
ELEVATION_MASK_RANGE = (0, 30)

TREND_HOURS = 24          # position quality over the last day, as app.py's DOP trends
TREND_STEP_MINUTES = 15
SKY_HOURS = 24            # the sky view runs over the next day...
SKY_STEP_MINUTES = 10     # ...ten minutes a step, so playing it moves smoothly...
SKY_FRAME_MS = 100        # ...and a day plays in about 15 seconds
NEXT_HOURS = 24           # when each satellite next comes into view or leaves it: the next day...
NEXT_STEP_MINUTES = 1     # ...to the minute
TRACK_HOURS = 24          # ground tracks: the next or the past day
TRACK_STEP_MINUTES = 15
TRACK_WINDOWS = ["Next 24 hours", "Past 24 hours"]
CLICK_GRID_DEG = 2        # a click on the map picks the nearest point of a grid this fine
# A place of the reader's own: typed as latitude, longitude, or clicked on the map.
PLACE_EXAMPLE = "28.61, 77.21"
PLACE_HELP = ("Latitude, then longitude, in degrees: for example 28.61, 77.21. South and west are negative, "
              "or write N, S, E or W after the number (28.61 N, 77.21 E).")
CENTRAL_LON_HALF_HOURS = 12        # central longitude: a day of track around each element set...
CENTRAL_LON_STEP_MINUTES = 15      # ...as app.py's historical central longitude, one element set a week

# Dilution of precision. (key, name, what it means in one plain line). TDOP has no band in config, so no "should be".
DOP_MEASURES = [
    ("GDOP", "All together", "your 3D position and the receiver's clock"),
    ("PDOP", "Position", "where you are in 3D"),
    ("HDOP", "Along the ground", "where you are north-south and east-west"),
    ("VDOP", "Height", "how high you are, up and down"),
    ("TDOP", "Clock", "the receiver's own clock"),
]
# What a distance measurement is worth. ASSUMPTION, ours: about 5 m (one standard deviation) of error in each
# satellite's measured distance for a single-frequency civil receiver. Its size is in the few-metre range of the user
# range error budgets in Kaplan and Hegarty, Understanding GPS/GNSS (3rd ed., 2017); GPS.gov quotes about 4.9 m
# (95 %) for a phone in the open. Not measured here: change it and every metre figure follows.
UERE_M = 5.0
UERE_WORDS = (f"{UERE_M:g} m is our assumption for the error of one distance measurement (one standard deviation, a "
              "single-frequency civil receiver): the few-metre budgets in Kaplan and Hegarty, Understanding GPS/GNSS, "
              "and GPS.gov's 4.9 m (95 %) for a phone in the open sky. A two-frequency receiver does better.")
DOP_LINE = ("DOP says how much the satellites' layout multiplies the error of one distance measurement: "
            f"position error is about DOP × {UERE_M:g} m, and 1 is the best layout there can be.")
# From first principles, one step at a time (the first is the line always shown, the rest one step deeper).
DOP_STEPS = [
    "A receiver times a radio signal from each satellite; time × the speed of light is its distance from that satellite.",
    "One distance puts you somewhere on a sphere around that satellite. Three spheres cross at two points, one of them "
    "out in space; a fourth satellite also settles the receiver's clock. So at least 4 satellites are needed.",
    "Every distance is a little off. Where the spheres cross at wide angles they pin the position tightly; where they "
    "cross at shallow angles, as satellites bunched in one part of the sky do, the position smears along the crossing.",
    "DOP (dilution of precision) is that smearing as one number: position error is about DOP × the error of one "
    "distance measurement. DOP 1 is the best case; DOP 4 makes the error four times bigger.",
]
SPREAD_ANGLES = (45, 135)      # the sketch: two satellites this many degrees above the horizon, left and right...
BUNCHED_ANGLES = (80, 100)     # ...and two bunched together overhead
SPREAD_LINE = ("Same distance error each time; the highlighted patch is where the receiver could be. Satellites spread "
               "apart pin it to a small patch; satellites bunched together leave a long smear.")
# What each band's metres are like, to the upper edge of the band (roughly: 5 m a car, 10 m a bus, 25 m a swimming pool).
BAND_LIKE = {"Ideal": "a large car", "Excellent": "a bus", "Good": "a swimming pool", "Moderate": "an Olympic pool",
             "Fair": "a football pitch", "Poor": "more than a football pitch"}
PLAIN_DOP = [("GDOP", "all of it: position and clock"), ("PDOP", "3D position: along the ground and in height"),
             ("HDOP", "position on the ground"), ("VDOP", "height")]
DOP_BANDS = DOP_QUALITY_THRESHOLDS
SEEN_WORDS = "Satellites in view: above the elevation mask. A position needs at least 4."
DOP_SOURCE = "Bands from Isik and others (2020), Robotics 9(3) 66."
# A quality band's status colour. The band's own word is always shown with it.
QUALITY_STATUS = {"Ideal": "ok", "Excellent": "ok", "Good": "ok", "Moderate": "warn", "Fair": "bad", "Poor": "bad"}

# Sky and ground's "What this shows" (ui/tooltip.glance): a lead, then (icon in ui/icons.py, key term, words), then
# a note. Plane spacing is from analysis/raan_analysis.py.
SKY_GROUND_LEAD = "Where the satellites are over the ground, and in the sky above one place."
SKY_GROUND_KEY = [
    ("map", "Map", "each satellite's ground track and where it is now; the crosses are the key places."),
    ("click", "Pick a place", "click the map, choose a key place or type a latitude and longitude to see its sky."),
    ("radar", "Sky", "overhead in the middle, the horizon at the edge; the dotted ring is the elevation mask."),
    ("player-play", "Next 24 hours", "play or drag through them."),
    ("planet", "Plane spacing", "satellites sharing one ground track should cross the equator northward at evenly "
                                "spaced points around Earth's axis (the node, or right ascension of the ascending "
                                "node): N satellites, 360 ÷ N degrees apart. Uneven spacing leaves gaps in the sky "
                                "and worsens position quality."),
]
# Why a medium-orbit constellation's planes are checked differently from inclined ones, said once on the page.
PLANE_WHY_INCLINED = ("Inclined orbits go round once a day, so satellites sharing a ground track are checked "
                      "against each other: N of them should have nodes 360 ÷ N degrees apart.")
PLANE_WHY_MEO = ("Medium orbits go round about twice a day and share no ground track, so each plane's node is "
                 "checked against planes spaced {spacing:g}° apart ({planes} planes), as on the Overview.")
GROUND_LINE = ("Each line is where one satellite passes over the ground; its dot is where it is now. The rings mark "
               "your place and the place you compare with.")
GROUND_DEEPER = ("A geostationary satellite hangs over one point of the equator, so its track is a dot. An inclined "
                 "geosynchronous or quasi-zenith satellite goes round once a day and traces a figure of eight "
                 "north and south of the equator. The crosses are the constellation's key places. Click anywhere "
                 "on the map to see the sky from there. Hover a track for the time, the point under it and its height.")
SKY_LINE = ("The sky as you would see it lying on your back at this place: the middle is straight overhead, the edge "
            "is the horizon, and each mark is a satellite.")
SKY_DEEPER = ("A satellite near the middle is high and its signal crosses little air; near the edge it is low and "
              "less reliable. The dotted ring is the elevation mask: a satellite below it is not counted. The count "
              "above the picture is how many are in view and the DOP they give at that moment. Press play to run "
              "the next 24 hours, or drag the line. Hover or tap a mark for the satellite's name and its height in "
              "the sky.")
TIMELINE_LINE = ("One row per satellite: a bar is a stretch of the next 24 hours when it is above the elevation mask, "
                 "and the time on a bar is when it rises.")
TIMELINE_DEEPER = ("The line marked now is the present. Rows are sorted: satellites in view now first (the ones "
                   "setting soonest at the top), then by the next rise. A row with no bar stays below the mask for "
                   "the whole day. A geostationary satellite stays at one point in the sky, so it is either in view "
                   "all day or never. Times are in your own time zone. Scroll down for the rest of the rows.")
PLANE_LINE_DEEPER = ("Plane spacing is worked out from the orbits' nodes: the points where each orbit crosses the "
                     "equator going north, measured round Earth's axis. Even spacing leaves no big gap in the sky.")
DOP_TREND_LINE = ("The line is how well spread the satellites were over your place in the last 24 hours (lower is better); "
                  "the bars under it count how many were in view.")
DOP_TREND_DEEPER = ("GDOP is the heavy line; PDOP, HDOP and VDOP are the thinner ones. The dotted lines are the band "
                    "edges: below the top line is excellent, below the middle one good, below the lowest moderate. "
                    "The bars should stay at 4 or more; fewer and no position can be worked out. The tiles give the "
                    "best, worst and average of the day.")
SKY_GROUND_NOTE = ("Plane spacing of inclined orbits is shown for information; it is not part of the health score. "
                   "A medium orbit's plane node is: the Overview scores it.")
SPACING_STATUS = {"Ideal": "ok", "Good": "ok", "Moderate": "warn", "Poor": "bad", "N/A": "idle"}

# Orbit trends: one row per satellite, one column per measure. (column in the history, name, unit, what it means).
TRENDS = [
    ("INCLINATION", "Tilt", "degrees", "inclination: the angle between the orbit and the equator"),
    ("altitude_km", "Height", "km", "average height above Earth"),
    ("LonDrift_deg_per_day", "Drift", "degrees a day", "how fast the satellite slides east or west"),
    ("central_lon", "Centre", "degrees east", "central longitude: the middle of its ground track over a day"),
]
# Drift and centre are measured against one turn a day over one longitude: they say nothing about a MEO satellite,
# which circles the globe (GPS drifts about 360 degrees a day by that measure). MEO systems get tilt and height only.
GEOSYNCHRONOUS_ONLY = ("LonDrift_deg_per_day", "central_lon")
MEO_TRENDS = [trend for trend in TRENDS if trend[0] not in GEOSYNCHRONOUS_ONLY]
# How a trend is put in a sentence: (column in the history: what it is called, its unit, the span under which it counts
# as steady, decimals). Our choice of "steady": about what the figure moves by from one element set to the next.
TREND_WORDS = {"INCLINATION": ("tilt", "°", 0.05, 2), "altitude_km": ("height", " km", 2.0, 1),
               "LonDrift_deg_per_day": ("drift", "° a day", 0.02, 3), "central_lon": ("centre", "°", 0.05, 2)}
DRIFT_TOLERANCE_IGSO = DRIFT_TOLERANCE_TILTED   # degrees a day: analysis.health_assessment's default for inclined orbits

# How each orbit type is drawn. Colour is backed by the shape and the name, never alone.
ORBIT_COLOURS = {"GEO": palette.ACCENT, "IGSO": palette.INK, "QZO": palette.INK}
ORBIT_SYMBOLS = {"GEO": "circle", "IGSO": "diamond", "QZO": "diamond"}
ORBIT_WORDS = {"GEO": "geostationary", "IGSO": "inclined geosynchronous", "QZO": "quasi-zenith"}
OTHER_ORBIT = "IGSO"
