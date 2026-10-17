"""Settings for the Library page's counts: which GCAT programmes make up each navigation system.

Everything a person may want to adjust about the counts is here. The counting is in evidence/library.py;
the addresses of the catalogue files are in evidence/sources.py.
"""

LIBRARY_COUNTS_FILE = "library_counts.csv"        # in registry/: one row per system and design generation
LIBRARY_MATCHING_FILE = "library_matching.csv"    # in registry/: one row per system, how satellites were matched
LIBRARY_FIGURES_FILE = "library_figures.csv"      # in registry/: kept by hand, every row with its public source

LIBRARY_COUNTS_COLUMNS = ["system", "programme", "launched", "failed_at_launch", "failed_in_orbit", "retired",
                          "operating", "status_not_recorded", "years_retired", "years_operating", "approximate_dates",
                          "first_launch", "last_launch", "gcat_updated"]
LIBRARY_MATCHING_COLUMNS = ["system", "registry_satellites", "registry_found_in_gcat", "registry_not_in_gcat",
                            "also_found_by_programme", "found_by_programme_only", "registry_and_programme_disagree"]
LIBRARY_FIGURES_COLUMNS = ["system", "programme", "measure", "value", "unit", "year_of_figure", "covers",
                           "source_name", "source_link", "status"]

# Each system: the country that runs it, and its GCAT programmes (the "Program" column of the payload
# catalogue), oldest generation first. Spacecraft from the same programmes are one system's, whether or not the
# registry lists them. Checked 17 Oct 2026 against the catalogue's own list of programmes.
SYSTEMS = {
    "GPS": {"country": "United States", "programmes": ["GPS I", "GPS II", "GPS IIA", "GPS IIR", "GPS IIRM", "GPS IIF", "GPS III"]},
    "GLONASS": {"country": "Russia (Soviet Union before 1992)",
                "programmes": ["Uragan", "Uragan-M", "Uragan-M1", "Uragan-K", "Glonass-K2"]},
    "Galileo": {"country": "European Union and European Space Agency", "programmes": ["Giove", "Galileo"]},
    "BeiDou": {"country": "China", "programmes": ["Beidou-1", "Beidou-2G", "Beidou-2I", "Beidou-2M", "Beidou-3G",
                                                  "Beidou-3I", "Beidou-3M", "Beidou-3M2", "Beidou-3M3"]},
    "NavIC": {"country": "India", "programmes": ["IRNSS", "IRNSS 2"]},
    "QZSS": {"country": "Japan", "programmes": ["QZSS"]},
}
OTHER_PROGRAMME = "other generation"   # a registry satellite whose GCAT programme is not listed above

# GCAT objects that carry a listed programme name but are not part of the system.
NOT_THESE = {"S20298": "NASA's Galileo probe to Jupiter, not the navigation system"}

# Launches that never reached orbit have no programme in the catalogue of failed launches, so they are found by the
# spacecraft's name: (system, programme, pattern on the Name column). Found by reading that whole catalogue for
# navigation names on 17 Oct 2026: 8 payloads. A system with no line here has no launch failure in it.
FAILED_LAUNCH_NAMES = [
    ("GPS", "GPS I", r"^Navstar "),
    ("GPS", "GPS IIR", r"^GPS IIR"),
    ("GLONASS", "Uragan-M", r"^Glonass-M "),
]

DAYS_PER_YEAR = 365.25
