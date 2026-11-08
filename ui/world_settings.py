"""The World map page's settings, in one place: where the globe starts, the NavIC service area, and the colours
for each system and broadcast-health state.
"""
from ui import palette

# The globe's home view: centred on India, so the systems whose service areas matter most are in the middle.
HOME_LAT = 15.0
HOME_LON = 80.0

# The service area of each regional system, drawn as a dashed outline while that system is the only one shown.
# NavIC's extended service area: 30°S-50°N, 30°E-130°E.
SERVICE_AREAS = {
    "NavIC": {"south": -30.0, "north": 50.0, "west": 30.0, "east": 130.0, "label": "NavIC service area (approx.)"},
}

# One quiet colour per constellation. BeiDou-3 reuses the dashboard's BeiDou colour.
SYSTEM_COLOURS = {
    "GPS": palette.CONSTELLATION_COLOURS["GPS"],
    "Galileo": palette.CONSTELLATION_COLOURS["Galileo"],
    "GLONASS": palette.CONSTELLATION_COLOURS["GLONASS"],
    "BeiDou-3": palette.CONSTELLATION_COLOURS["BeiDou"],
    "BeiDou-3 MEO": palette.CONSTELLATION_COLOURS["BeiDou"],
    "NavIC": palette.CONSTELLATION_COLOURS["NavIC"],
    "QZSS": palette.CONSTELLATION_COLOURS["QZSS"],
}

# Broadcast health colours, the same states ui/orbit_age.py uses.
HEALTH_COLOURS = {"ok": palette.OK, "warn": palette.WARN, "bad": palette.BAD, "idle": palette.IDLE}
