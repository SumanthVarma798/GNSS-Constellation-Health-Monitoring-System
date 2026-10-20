"""What each medium Earth orbit (MEO) system's orbits should be: GPS, GLONASS and Galileo.

Every value says where it comes from and how sure we are of it:
  CHECKED     read in the document itself (17 Oct 2026)
  SUMMARY     read through a summary of the page, numbers quoted from it; check against the page
  OUR_CHOICE  no document sets it; the dashboard's own tolerance, for the team to confirm

Angles are degrees, lengths kilometres. "Argument of latitude" is the angle along the orbit from
the ascending node: where in its plane a satellite is. The slot tables give each slot's argument of
latitude at the source's reference epoch; every slot moves at the same rate, so only the differences
between slots of one plane are used, and the epoch does not matter.
"""
from typing import NamedTuple

CHECKED, SUMMARY, OUR_CHOICE = "checked", "source summary", "our choice"

GPS_SPS = ("GPS Standard Positioning Service Performance Standard, 4th edition (September 2008), section 3.2, "
           "tables 3.2-1 to 3.2-3, https://rosap.ntl.bts.gov/view/dot/16930")
GLONASS_ICD = ("GLONASS Interface Control Document, navigational radiosignal in bands L1, L2, edition 5.1 (2008), "
               "section 5, https://www.unavco.org/help/glossary/docs/ICD_GLONASS_5.1_(2008)_en.pdf")
GALILEO_GSC = ("European GNSS Service Centre, Orbital and Technical Parameters (source ESA, reference epoch "
               "21 Nov 2016), https://www.gsc-europa.eu/system-service-status/orbital-and-technical-parameters")
DASHBOARD = "The dashboard's own tolerance; no document sets one."


class Nominal(NamedTuple):
    value: object
    source: str
    label: str


def _galileo_slots():
    """Plane A slot n sits at 180.153 + 45 (n - 1); plane B is 15 degrees on, plane C 30 (Walker 24/3/1).
    This reproduces the source's 24-row table. The auxiliary slots are listed as the source gives them."""
    slots = {f"{plane}{n:02d}": (180.153 + 15 * k + 45 * (n - 1)) % 360
             for k, plane in enumerate("ABC") for n in range(1, 9)}
    return slots | {"A12": 247.653, "B14": 352.653, "B15": 37.653, "C12": 277.653, "C13": 322.653, "C17": 142.653}


def _glonass_slots():
    """The source's formula: slot j at 145 deg 26' 37'' + 15 (27 - 3j + 25 j*), j* the integer part of (j - 1) / 8."""
    return {str(j): (145 + 26 / 60 + 37 / 3600 + 15 * (27 - 3 * j + 25 * ((j - 1) // 8))) % 360 for j in range(1, 25)}


# The 24 baseline slots (table 3.2-1) and the six expanded ones (table 3.2-2), at 1 July 1993.
_GPS_SLOTS = {
    "A1": 268.126, "A2": 161.786, "A3": 11.676, "A4": 41.806,
    "B1": 80.956, "B2": 173.336, "B3": 309.976, "B4": 204.376,
    "C1": 111.876, "C2": 11.796, "C3": 339.666, "C4": 241.556,
    "D1": 135.226, "D2": 265.446, "D3": 35.156, "D4": 167.356,
    "E1": 197.046, "E2": 302.596, "E3": 66.066, "E4": 333.686,
    "F1": 238.886, "F2": 345.226, "F3": 105.206, "F4": 135.346,
    "B1F": 94.916, "B1A": 66.356, "D2F": 282.676, "D2A": 257.976, "F2F": 0.456, "F2A": 334.016,
}

# Per system. "registry_planes" turns the registry's plane column into the plane's name; a plane the
# registry gives that is not here (Galileo's "X") is outside the nominal planes. "slots" are
# {registry slot name: argument of latitude}; a satellite whose slot is not listed has no slot to
# be measured against. Tolerances: within it a part scores 100 (see analysis/meo_geometry.py).
NOMINAL = {
    "GPS": {
        "registry_planes": Nominal({str(n): p for n, p in enumerate("ABCDEF", 1)}, GPS_SPS, CHECKED),
        "plane_spacing_deg": Nominal(60.0, GPS_SPS + ", table 3.2-1", CHECKED),
        "plane_tolerance_deg": Nominal(5.0, DASHBOARD + " The source leaves the node free (range 180 degrees).",
                                       OUR_CHOICE),
        "inclination_deg": Nominal(55.0, GPS_SPS + ", table 3.2-3", CHECKED),
        "inclination_tolerance_deg": Nominal(3.0, GPS_SPS + ", table 3.2-3, operational range", CHECKED),
        "semi_major_axis_km": Nominal(26559.7, GPS_SPS + ", table 3.2-3", CHECKED),
        "semi_major_axis_tolerance_km": Nominal(
            10.0, DASHBOARD + " The source adjusts the axis only to keep the spacing (note 1).", OUR_CHOICE),
        "eccentricity_max": Nominal(0.02, GPS_SPS + ", table 3.2-3, operational range", CHECKED),
        "slots": Nominal(_GPS_SLOTS, GPS_SPS + ", tables 3.2-1 and 3.2-2", CHECKED),
        "spacing_tolerance_deg": Nominal(4.0, GPS_SPS + ", table 3.2-3, note 1: spacing kept within 4 degrees",
                                         CHECKED),
    },
    "GLONASS": {
        "registry_planes": Nominal({"1": "1", "2": "2", "3": "3"}, GLONASS_ICD + ", 5.1", CHECKED),
        "plane_spacing_deg": Nominal(120.0, GLONASS_ICD + ", 5.1", CHECKED),
        "plane_tolerance_deg": Nominal(2.0, DASHBOARD, OUR_CHOICE),
        "inclination_deg": Nominal(64.8, GLONASS_ICD + ", 5.2", CHECKED),
        "inclination_tolerance_deg": Nominal(1.0, DASHBOARD, OUR_CHOICE),
        # The source gives the draconic period, 11 h 15 min 44 s; this is the axis two-body motion gives for it.
        "semi_major_axis_km": Nominal(round((398600.4418 * (40544 / (2 * 3.141592653589793)) ** 2) ** (1 / 3), 1),
                                      GLONASS_ICD + ", 5.2, from the period 11 h 15 min 44 s", CHECKED),
        "semi_major_axis_tolerance_km": Nominal(10.0, DASHBOARD, OUR_CHOICE),
        "eccentricity_max": Nominal(0.01, DASHBOARD + " The source gives 0.", OUR_CHOICE),
        "slots": Nominal(_glonass_slots(), GLONASS_ICD + ", 5.2", CHECKED),
        "spacing_tolerance_deg": Nominal(5.0, GLONASS_ICD + ", 5.2: within 5 degrees of the ideal slot", CHECKED),
    },
    "Galileo": {
        "registry_planes": Nominal({"1": "A", "2": "B", "3": "C"}, GALILEO_GSC, SUMMARY),
        "plane_spacing_deg": Nominal(120.0, GALILEO_GSC, SUMMARY),
        "plane_tolerance_deg": Nominal(2.0, DASHBOARD, OUR_CHOICE),
        "inclination_deg": Nominal(56.0, GALILEO_GSC, SUMMARY),
        "inclination_tolerance_deg": Nominal(2.0, DASHBOARD, OUR_CHOICE),
        "semi_major_axis_km": Nominal(29599.8, GALILEO_GSC, SUMMARY),
        "semi_major_axis_tolerance_km": Nominal(10.0, DASHBOARD, OUR_CHOICE),
        "eccentricity_max": Nominal(0.01, DASHBOARD + " The source gives 0.", OUR_CHOICE),
        "slots": Nominal(_galileo_slots(), GALILEO_GSC, SUMMARY),
        "spacing_tolerance_deg": Nominal(4.0, DASHBOARD, OUR_CHOICE),
        # The two satellites a launch fault left in an eccentric orbit (registry plane X), judged against it.
        "extended": Nominal({"semi_major_axis_km": 27977.6, "eccentricity": 0.162, "inclination_deg": 49.850},
                            GALILEO_GSC + ", auxiliary satellites Ext01 and Ext02", SUMMARY),
        "extended_eccentricity_tolerance": Nominal(0.01, DASHBOARD, OUR_CHOICE),
    },
}

# One line each: what a measure means, for the page.
MEANINGS = {
    "plane": "Plane: how far its orbit's node sits from where its plane should be",
    "spacing": "Spacing: the gap to the next satellite along the plane, against the gap between their slots",
    "inclination": "Inclination: the tilt of its orbit to the equator",
    "height": "Height: the size of its orbit (semi-major axis)",
    "eccentricity": "Eccentricity: how far its orbit is from a circle",
}

# One line each: what a plane card's figures mean (ui/meo_overview.py, analysis/meo_geometry.plane_drift).
PLANE_MEANINGS = {
    "In step": "In step: the satellites whose gaps to their neighbours along the plane are within the limit of the "
               "gaps between their slots",
    "Need a look": "Need a look: the satellites with any measure well past its limit (a part score under 80)",
    "Node": "Node: how far this plane's node sits from the pattern of equally spaced planes fitted to every satellite",
    "Drift": "Drift: how fast that distance changes, from the Earth's flattening acting on its satellites' tilt and "
             "height. Worked out from the newest orbits, not measured over time",
    "Gaps": "Gaps: the worst gap between neighbours in this plane, against the gap between their slots",
}
