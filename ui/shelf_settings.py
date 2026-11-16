"""What the Library's shelves hold: the data only this project makes (and how to get, use and cite it), the data
others make that we use (and where to go for it), the people already doing this work, and the citations.
The page is views/library.py; the cards are built in ui/shelf.py.

Licences follow NOTICE and LICENSE-DATA. Only the project's own data is offered for download; everything else is
credited to its owner and linked.
"""

# The shelves, in the page's order: (title, icon, the section a jump to it opens). views/library.py draws them.
SHELVES = {
    "stories": ("Stories", "broadcast", "library_stories"),
    "satellites": ("Satellites and their lives", "rocket", "library_systems"),
    "datasets": ("Datasets", "database", "library_ours"),
    "cite": ("How to cite", "quote", "library_cite"),
}
STORIES_SHOWN = 6   # the newest stories on the shelf; the News page has them all
# A constellation as ui.systems names it -> its name in the lifecycle timelines (registry/satellites.csv's), where
# they differ.
LIFECYCLE_CONSTELLATION = {"BeiDou-3": "BeiDou"}

RAW = "https://raw.githubusercontent.com/SumanthVarma798/GNSS-Constellation-Health-Monitoring-System/"
DASHBOARD_LINK = "https://dashboard.opengnss.org"
OUR_LICENCE = ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")
OUR_CREDIT = "data from OpenGNSS (opengnss.org)"   # NOTICE
GCAT_CREDIT = "data from GCAT (J. McDowell, planet4589.org/space/gcat)"   # NOTICE; evidence.settings.GCAT_CITATION

# Jobs the administration console does not list (evidence/console_settings.py JOBS): workflow -> name.
JOB_NAMES = {"source-record.yml": "Source record"}
ORBIT_GAP, FITTED = "orbit_gap", "fitted"   # files read from the orbit-checks branch (ui/data.py)

# ---- Only here: the data this project makes that no one else publishes, most distinctive first.
# file: ("repo", path in the repository) or ("published", ORBIT_GAP or FITTED). date: ("column", name) the newest value
# in a CSV column, ("json", key), or None. job: (workflow, schedule group) or "hand". fields: (name, what it means).
OURS = {
    "orbit_gap": {
        "name": "Orbit record check", "icon": "map", "file": ("published", ORBIT_GAP), "date": ("json", "day"),
        "job": ("rinex-check.yml", ""), "address": RAW + "orbit-checks/orbit_gap.json",
        "what": "Every day, how far each followed satellite's newest public orbit record is from the positions the "
                "satellite broadcasts itself.",
        "why": "Public orbit records (CelesTrak, Space-Track) and broadcast orbits (IGS broadcast navigation files, via "
               "BKG) are each published; this daily comparison of the two is not.",
        "fields": [("day", "the UTC day checked"),
                   ("satellites[].satellite, signal_id", "the satellite and its signal ID that day"),
                   ("record_epoch", "the time of the public orbit record compared"),
                   ("typical_km, largest_km", "the median and the largest distance between the record and the broadcast "
                                              "positions over the day, in km"),
                   ("mostly", "which way the record is off: ahead of or behind the satellite on its path, or off its orbit plane"),
                   ("note", "why a satellite was not compared, such as not in the day's broadcast file"),
                   ("fitted_km", "how far yesterday's fitted orbit (the next card) is from today's broadcast positions")],
        "example": "typical_km 3.2 for a satellite: its newest public record placed it about 3 km from where it said it "
                   "was that day.",
        "not_for": "Navigation or precise positioning. It checks public records; it is not a precise orbit."},
    "fitted": {
        "name": "Orbits fitted to broadcast positions", "icon": "planet", "file": ("published", FITTED),
        "date": ("json", "day"), "job": ("rinex-check.yml", ""), "address": RAW + "orbit-checks/fitted_orbits.json",
        "what": "An orbit fitted to a day of each satellite's own broadcast positions, ready for the SGP4 propagator.",
        "why": "Made here from IGS broadcast navigation files; it stands in when a satellite's public record is days old.",
        "fields": [("day", "the UTC day the broadcast positions are from"),
                   ("satellites[].satellite, signal_id, norad", "the satellite, its signal ID and catalogue number"),
                   ("row", "the fitted orbit, in the same fields as CelesTrak's GP records (OMM), for SGP4"),
                   ("fit_km", "how closely the orbit fits the day's broadcast positions (root mean square, km)"),
                   ("note", "why no orbit was fitted, such as too few broadcast positions")],
        "example": "Give a satellite's row to an SGP4 library that reads OMM records and propagate it a few hours ahead; "
                   "check fit_km first.",
        "not_for": "Anything that needs metre accuracy, or propagating days ahead: a one-day fit ages like any record."},
    "lifecycles": {
        "name": "Satellite lifecycles", "icon": "rocket", "file": ("repo", "registry/lifecycle_events.csv"),
        "date": ("column", "at_utc"), "job": "hand", "address": RAW + "main/registry/lifecycle_events.csv",
        "what": "Each step of a satellite's life, from built and launched to service ended, with a public source for "
                "every step.",
        "why": "Gathered by hand from the operators' mission pages and updates; no one publishes these steps in one table.",
        "fields": [("satellite, step, title", "the satellite, which step of its life, and the step's name"),
                   ("from_utc, at_utc, when", "when the step began and happened, and how exact that is (at, by, about, "
                                               "on the day, in the month)"),
                   ("evidence, result", "what kind of source states it (operator, orbit records, press), and the outcome"),
                   ("detail", "what happened, in words"),
                   ("source_name, source_link", "the public source for this step"),
                   ("picture, picture_credit", "a Wikimedia Commons file and its credit, where there is one")],
        "example": "The NVS-01 rows run from built and tested to in navigation service, each with its date and source.",
        "not_for": "An official timeline: only steps a public source states are here."},
    "sources": {
        "name": "News sources and their grades", "icon": "search", "file": ("repo", "evidence/source_grades.csv"),
        "date": ("column", "graded_on"), "job": ("source-record.yml", ""), "address": RAW + "main/evidence/source_grades.csv",
        "what": "Every news source the dashboard reads, with a reliability grade from A (the operator) to F (unattributed).",
        "why": "Graded by the team and checked each week against the record of claims that held or failed.",
        "fields": [("source_id, name", "the source's address and name"),
                   ("reliability", "A operator, B scientific body, C specialist press, D general news, E social media, "
                                   "F unattributed"),
                   ("graded_by, graded_on, reason", "who graded it, when, and why")],
        "example": "Keep the rows with reliability A for the operators' own advisories.",
        "not_for": "Judging one article: a grade says how often a source held before."},
    "tracked": {
        "name": "Satellites this dashboard follows", "icon": "radar", "file": ("repo", "registry/dashboard_satellites.csv"),
        "date": ("column", "added"), "job": "hand", "address": RAW + "main/registry/dashboard_satellites.csv",
        "what": "The satellites the dashboard scores, and its name for each.",
        "why": "The team's choice, checked by a test against the IGS satellite metadata file so no satellite with a "
               "signal ID today is missed without a reason.",
        "fields": [("svn", "the space vehicle number, as the IGS satellite metadata file gives it"),
                   ("dashboard_name", "the name the dashboard shows"),
                   ("added", "the day it was added, where recorded")],
        "example": "Join on svn to the IGS satellite metadata file for each satellite's generation and catalogue number.",
        "not_for": "A list of every navigation satellite in orbit: older generations are not followed."},
    "counts": {
        "name": "Launched, lost and kept", "icon": "calculator", "file": ("repo", "registry/library_counts.csv"),
        "date": ("column", "gcat_updated"), "job": ("registry-update.yml", ""), "address": RAW + "main/registry/library_counts.csv",
        "what": "How many satellites each constellation and design generation launched, lost, retired and still runs.",
        "why": "Counted here from GCAT, J. McDowell's catalogue of space objects, matched satellite by satellite to the "
               "IGS satellite metadata file. Credit GCAT as well as us.",
        "fields": [("system, programme", "the constellation and its design generation, as GCAT names them"),
                   ("launched, failed_at_launch, failed_in_orbit, retired, operating", "counts of satellites"),
                   ("years_retired, years_operating", "years in service added up over the satellites"),
                   ("gcat_updated", "the day GCAT was last updated when counted")],
        "example": "(launched - failed_at_launch) / launched is the share of launches that reached orbit.",
        "not_for": "Ranking agencies: the constellations began in different decades."},
    "figures": {
        "name": "Money stated by public sources", "icon": "coin", "file": ("repo", "registry/library_figures.csv"),
        "date": None, "job": "hand", "address": RAW + "main/registry/library_figures.csv",
        "what": "What public sources say each programme cost, in their own currency and year, each with its source.",
        "why": "Gathered by hand; nothing is converted or estimated.",
        "fields": [("system, programme", "the constellation and the part of it the figure is for"),
                   ("value, unit, year_of_figure", "the figure as the source states it"),
                   ("covers", "what the figure includes and leaves out"),
                   ("source_name, source_link, status", "where it comes from, and whether the team has reviewed it")],
        "example": "Read covers before using a figure: some are two satellites, some a whole programme.",
        "not_for": "Comparing constellations: the figures cover different things, years and currencies."},
}

# ---- Others' data we use: whose it is, what we use it for, where to go. Not offered here.
OTHERS = [
    ("GCAT, J. McDowell's catalogue of space objects", "database", "https://planet4589.org/space/gcat/",
     "The counts per constellation and each satellite's end of operations.", ("archive.yml", "catalogues")),
    ("IGS satellite metadata file", "satellite", "https://files.igs.org/pub/station/general/",
     "Which satellite is which, signal IDs over time, and launch dates.", ("registry-update.yml", "")),
    ("IGS broadcast navigation files, via BKG", "broadcast", "https://igs.bkg.bund.de/",
     "The positions satellites broadcast, for the orbit record check.", ("rinex-check.yml", "")),
    ("CelesTrak's orbit records", "satellite", "https://celestrak.org/",
     "The newest public orbit record of each satellite.", ("archive.yml", "orbital")),
    ("Space-Track.org's orbit records", "hourglass", "https://www.space-track.org/",
     "A year of orbit records for NavIC, QZSS, BeiDou-3 and GLONASS, which the scores come from.", ("update-tle-data.yml", "")),
    ("News publishers", "broadcast", "",
     "Headlines and short excerpts on the News page, each linked to its article.", ("archive.yml", "news")),
    ("Natural Earth", "map", "https://www.naturalearthdata.com/", "The land outline under the world maps.", "hand"),
]

# ---- People already doing this work, per constellation, from the team's source list (evidence/source_grades.csv
# and source_candidates.csv). Go to them; we credit them. (constellation, [(who, what they do, link)]).
COLLEAGUES = [
    ("Every constellation", [
        ("Jonathan McDowell", "GCAT and Jonathan's Space Report: every launch and every object in orbit",
         "https://planet4589.org/space/jsr/latest.html"),
        ("International GNSS Service (IGS)", "the satellite metadata file and the broadcast and precise orbits",
         "https://igs.org/"),
        ("CelesTrak", "public orbit records, republished for everyone", "https://celestrak.org/"),
        ("Inside GNSS", "specialist GNSS news", "https://insidegnss.com/"),
        ("GPS World", "specialist GNSS news", "https://www.gpsworld.com/")]),
    ("NavIC", [
        ("IndianSpaceflight", "a NavIC page with each satellite's status, and ISRO's replies to information requests",
         "https://www.indianspaceflight.in/navic"),
        ("Indian Space Progress (Jatan Mehta)", "a monthly report on Indian space", "https://jatan.space/"),
        ("ISRO", "the operator's NavIC programme page", "https://www.isro.gov.in/IRNSS_Programme.html")]),
    ("QZSS", [("Cabinet Office of Japan", "the operator's notices to QZSS users", "https://sys.qzss.go.jp/dod/en/naqu/index.html")]),
    ("GPS", [("US Coast Guard Navigation Center", "the official notices to GPS users", "https://navcen.uscg.gov/")]),
    ("Galileo", [
        ("European GNSS Service Centre", "the operator's notices to Galileo users",
         "https://www.gsc-europa.eu/system-service-status/nagu-information"),
        ("European Spaceflight (Andrew Parsonson)", "news of European launches", "https://europeanspaceflight.com/")]),
    ("BeiDou-3", [
        ("China Space Bulletin (Andrew Jones)", "a journalist's reports on China's space programme",
         "https://chinaspacenewsroundup.substack.com/"),
        ("China Space Monitor (Blaine Curcio)", "an analyst's monthly newsletter on China's space sector",
         "https://chinaspacemonitor.substack.com/")]),
    ("GLONASS", [("RussianSpaceWeb (Anatoly Zak)", "a journalist's history and news of GLONASS",
                  "https://www.russianspaceweb.com/glonass.html")]),
]

# ---- How to cite: our own data and the dashboard, then each outside source with the credit its owner asks for
# (as NOTICE records it).
OUR_CITATIONS = [
    ("Our data", "OpenGNSS, <dataset name>, data from OpenGNSS (opengnss.org), licensed CC BY 4.0, <its address>, "
                 "retrieved <date>."),
    ("The dashboard", f"OpenGNSS GNSS Health Monitor, {DASHBOARD_LINK}, retrieved <date>."),
]
OUTSIDE_CITATIONS = [
    ("GCAT", GCAT_CREDIT + "."),
    ("IGS", "Acknowledge the International GNSS Service (IGS) for its satellite metadata file and broadcast files."),
    ("Space-Track.org and CelesTrak", "Credit Space-Track.org and CelesTrak for orbit records, under their terms of use."),
    ("Natural Earth", "Made with Natural Earth."),
]
