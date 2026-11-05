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

# ---- Lifecycle timelines (ui/components/lifecycle.*) ----
LIFECYCLE_EVENTS_FILE = "lifecycle_events.csv"   # in registry/: kept by hand, every row with its public source
LIFECYCLE_EVENTS_COLUMNS = ["satellite", "step", "title", "from_utc", "at_utc", "when", "evidence", "result", "detail",
                            "picture", "picture_credit", "source_name", "source_link"]
# The steps each series goes through, in order. No agency publishes a checklist like this: it is ISRO's mission
# sequence as its NVS mission pages and updates describe it. A row's step is one of these, or NOTE_STEP for context
# that is not a step (it is shown, and never counted).
LIFECYCLE_STEPS = {
    "NVS": [("built", "Built and tested"), ("launch", "Launch"), ("separation", "Separated in transfer orbit"),
            ("burn", "Orbit raising"), ("gso", "Reached geosynchronous orbit"), ("slot", "At its slot"),
            ("payload", "Payload tested"), ("service", "In navigation service"), ("end", "Service ended"),
            ("disposal", "Moved out of its orbit")],
}
NOTE_STEP = "note"
SERVICE_STEP, END_STEP = "service", "end"
LIFECYCLE_SERIES = {"NVS-01": "NVS", "NVS-02": "NVS", "NVS-03": "NVS"}   # satellite -> its series
SERIES_SYSTEM = {"NVS": "NavIC"}   # series -> navigation system, for a satellite only the hand-kept table has
# Every satellite in the registry also gets these steps, from tables already kept: the IGS file's launch date and
# signal-ID periods (satellites.csv, signal_ids.csv) and GCAT's end of regular operations (catalogue.csv). A signal
# ID assigned is the nearest the registry comes to "in service": an assignment is not proof it was broadcasting.
# Hand-kept rows replace these step by step.
REGISTRY_STEPS = [("launch", "Launch"), ("service", "Signal ID assigned"), ("end", "Regular operations ended")]
SYSTEM_ORDER = ("NavIC", "QZSS", "BeiDou", "GPS", "Galileo", "GLONASS")   # the picker's order: regional systems first
# Design life in years, from the NVS-01 mission brochure ("more than 12 years").
DESIGN_LIFE_YEARS = {"NVS": 12}
# How exact at_utc is. "on": the day only (placed at midday); "in": the month only (placed mid-month).
WHEN_WORDS = {"at": "", "by": "by ", "about": "about ", "on": "", "in": ""}
EVIDENCE_WORDS = {"operator": "operator", "orbit records": "orbit records", "press": "press report",
                  "IGS file": "IGS file", "catalogue": "GCAT"}
FAILED = "failed"
# Pictures are Wikimedia Commons files, loaded by the reader's browser; the file's own page carries its licence.
# Widths are Wikimedia's standard thumbnail steps: other widths are made on demand and may be refused when busy.
COMMONS_PICTURE = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width=500"
COMMONS_LARGE = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width=1280"   # shown when expanded
COMMONS_PAGE = "https://commons.wikimedia.org/wiki/File:{name}"

# ---- What each Library count means: the card its heading opens (ui/library.py). (lead line, [(icon, key term,
# words)], note); icons are names in ui/icons.py MASKED; "{updated}" is GCAT's update date. Read at a glance: one line
# says what it is, the rest where it comes from and how it is counted.
LIBRARY_COLUMN_HELP = {
    "launched": ("Spacecraft launched, as GCAT lists them.",
                 [("rocket", "Reached orbit", "GCAT's payload catalogue, grouped by programme name (the names are in our settings)."),
                  ("alert-triangle", "Never reached orbit", "launches in GCAT's failed-launch catalogue, found by name.")],
                 "GCAT as of {updated}."),
    "failed_at_launch": ("The launch never put the spacecraft in orbit.",
                         [("database", "From", "GCAT's failed-launch catalogue.")], ""),
    "failed_in_orbit": ("Reached orbit, then failed early in its mission.",
                        [("database", "From", "GCAT's result flag for the mission.")], ""),
    "retired": ("Not failed early, and its regular operations have ended.",
                [("power", "Counts", "a full working life and an early end alike."),
                 ("database", "From", "the end date GCAT gives.")], ""),
    "operating": ("GCAT believes it is still operating.",
                  [("broadcast", "Read as", "the catalogue author's latest word, not a live status: he updates it patchily.")], ""),
    "launch_success": ("Share of launches that put the spacecraft in orbit.",
                       [("calculator", "Worked out", "(launched - failed at launch) / launched.")], ""),
    "orbit_success": ("Share of spacecraft in orbit that did not fail early.",
                      [("calculator", "Worked out", "(reached orbit - failed in orbit) / reached orbit.")], ""),
    "satellite_years": ("Years in service, added up over the satellites.",
                        [("power", "Retired", "launch to the end of regular operations."),
                         ("broadcast", "Operating", "launch to GCAT's update date."),
                         ("hourglass", "Approximate", "a date known only to the month or year is taken mid-month or mid-year.")], ""),
    "average_retired": ("Years in service of the retired satellites, per satellite.",
                        [("calculator", "Worked out", "their years in service / how many retired.")],
                        "Design life is not in GCAT, so service is not compared with it."),
    "money": ("Only figures a public source states, each with its source.",
              [("coin", "Not compared", "they cover different things, in different years and currencies.")], ""),
}
