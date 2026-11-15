"""What the Library's shelves hold: every dataset the dashboard uses or scans, whose it is, whether a visitor may take
it home, and how to cite it. The page is views/library.py; the cards and the take-home bundle are built in ui/shelf.py.

Licences follow NOTICE and LICENSE-DATA exactly. A file is offered for download only when its owner's terms let it be
passed on (offer=True); every other one links to its owner and says why it is not offered here.

Each dataset: (key, {
  "name", "icon" (ui/icons.py MASKED), "shelf" (a key of SHELVES),
  "what"      one line: what it is, for a first-time reader,
  "how"       how it is made or measured,
  "left_out"  what it assumes or leaves out,
  "file"      ("repo", path from the repository root) | ("published", ORBIT_GAP or FITTED or NEWS or LATEST_GNSS) | None,
  "date"      where its date is: ("column", name) the newest value in that CSV column | ("json", key) | ("head", key)
              the key near the top of a large JSON file, read without loading the file | None (the file has no date),
  "job"       (workflow file, schedule group) of the job that keeps it, or "hand" for a table a person keeps,
  "licence"   a key of LICENCES, "offer" True or False, "why_not" (when not offered), "link" (the owner's page)}).
"""

# The shelves, in the page's order: (title, icon, one line under the title).
SHELVES = {
    "stories": ("Stories", "broadcast", "What happened to the navigation satellites lately, grouped from the news."),
    "satellites": ("Satellites and their lives", "rocket", "Every satellite launched, lost and kept, and each one's life from launch to end of service."),
    "datasets": ("Datasets", "database", "Every table and file the dashboard reads or scans, with whose it is and how fresh."),
    "takeaways": ("Take-aways", "download", "Files you may take home, free to reuse under their licence."),
    "cite": ("How to cite", "quote", "The words to use when you reuse something from here."),
}
STORIES_SHOWN = 6   # the newest stories on the shelf; the News page has them all

# Groups on the Datasets shelf: (title, one line), in order.
DATASET_GROUPS = {
    "tables": ("Tables we keep", "Satellites, their lifecycles, counts and sources, kept in the project's own files."),
    "published": ("Files our jobs publish", "Written by the project's scheduled jobs to branches of its repository, read by this dashboard."),
    "others": ("From other people", "Records the dashboard reads from their owners. Linked, not handed out here."),
}

CODE_LINK = "https://github.com/SumanthVarma798/GNSS-Constellation-Health-Monitoring-System"
OUR_CREDIT = "data from OpenGNSS (opengnss.org)"   # NOTICE
GCAT_CREDIT = "data from GCAT (J. McDowell, planet4589.org/space/gcat)"   # NOTICE; the same as evidence.settings.GCAT_CITATION
IGS_CREDIT = "built from the International GNSS Service (IGS) satellite metadata file"

# Licence key -> (name shown, link to its terms, how to credit). Whether a file is offered is each dataset's "offer".
LICENCES = {
    "ours": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/", OUR_CREDIT),
    "ours_gcat": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/", f"{OUR_CREDIT}; {GCAT_CREDIT}"),
    "gcat": ("CC BY (GCAT's own)", "https://planet4589.org/space/gcat/", GCAT_CREDIT),
    "igs": ("IGS terms: free to use, acknowledge the IGS", "https://igs.org/", f"{OUR_CREDIT}, {IGS_CREDIT}"),
    "spacetrack": ("Space-Track.org user agreement", "https://www.space-track.org/", "orbital data from Space-Track.org"),
    "celestrak": ("CelesTrak's terms", "https://celestrak.org/", "orbital data from CelesTrak"),
    "publishers": ("each publisher's own", "", "the publisher of each article"),
    "naturalearth": ("public domain (CC0)", "https://www.naturalearthdata.com/about/terms-of-use/", "Made with Natural Earth"),
    "code": ("Apache-2.0", "https://www.apache.org/licenses/LICENSE-2.0", "OpenGNSS contributors"),
}

# Jobs the administration console does not list (evidence/console_settings.py JOBS): workflow -> name.
JOB_NAMES = {"source-record.yml": "Source record"}

ORBIT_GAP, FITTED, NEWS, LATEST_GNSS = "orbit_gap", "fitted", "news", "latest_gnss"

DATASETS = {
    "lifecycles": {
        "name": "Satellite lifecycles", "icon": "rocket", "shelf": "tables",
        "what": "Each step of a satellite's life, from built and launched to service ended, with a source for every step.",
        "how": "Kept by hand from operators' mission pages and updates; registry satellites also get launch and signal-ID steps from the IGS file.",
        "left_out": "Only steps a public source states. Dates known only to the day or month are marked so.",
        "file": ("repo", "registry/lifecycle_events.csv"), "date": ("column", "at_utc"), "job": "hand",
        "licence": "ours", "offer": True, "link": ""},
    "counts": {
        "name": "Launched, lost and kept", "icon": "calculator", "shelf": "tables",
        "what": "How many satellites each constellation and design generation launched, lost at launch or in orbit, retired, and still runs.",
        "how": "Counted from GCAT's catalogues, matched to our registry by catalogue number.",
        "left_out": "GCAT's word on 'operating' is its author's latest, not a live status.",
        "file": ("repo", "registry/library_counts.csv"), "date": ("column", "gcat_updated"),
        "job": ("registry-update.yml", ""), "licence": "ours_gcat", "offer": True, "link": ""},
    "figures": {
        "name": "Money stated by public sources", "icon": "coin", "shelf": "tables",
        "what": "What public sources say each programme cost, in their own currency and year.",
        "how": "Kept by hand; every row names its source and what the figure covers.",
        "left_out": "Nothing is converted, averaged or estimated. A figure no source states reads 'not known'.",
        "file": ("repo", "registry/library_figures.csv"), "date": None, "job": "hand",
        "licence": "ours", "offer": True, "link": ""},
    "satellites": {
        "name": "Satellite registry", "icon": "satellite", "shelf": "tables",
        "what": "Which satellite is which: one row per physical satellite, with its catalogue number and generation.",
        "how": "Rebuilt from the IGS satellite metadata file; any change is proposed as a pull request a person reviews.",
        "left_out": "A satellite the IGS file does not list yet is not here (see sightings in the repository).",
        "file": ("repo", "registry/satellites.csv"), "date": None,
        "job": ("registry-update.yml", ""), "licence": "igs", "offer": True, "link": "https://files.igs.org/pub/station/general/"},
    "signal_ids": {
        "name": "Signal IDs over time", "icon": "broadcast", "shelf": "tables",
        "what": "Which signal ID (PRN) each satellite held, and when. An ID can pass from one satellite to another.",
        "how": "Rebuilt from the IGS satellite metadata file with the registry.",
        "left_out": "An assigned ID is not proof the satellite was broadcasting.",
        "file": ("repo", "registry/signal_ids.csv"), "date": ("column", "valid_from"),
        "job": ("registry-update.yml", ""), "licence": "igs", "offer": True, "link": "https://files.igs.org/pub/station/general/"},
    "catalogue": {
        "name": "Owner and status per satellite", "icon": "database", "shelf": "tables",
        "what": "Each registry satellite's owner, status and end of operations, as a second source states them.",
        "how": "Taken from GCAT's catalogues for the satellites in our registry.",
        "left_out": "Only satellites our registry lists.",
        "file": ("repo", "registry/catalogue.csv"), "date": None,
        "job": ("registry-update.yml", ""), "licence": "gcat", "offer": True, "link": "https://planet4589.org/space/gcat/"},
    "tracked": {
        "name": "Satellites this dashboard tracks", "icon": "radar", "shelf": "tables",
        "what": "The satellites drawn on the dashboard and its name for each; and the few left out on purpose, with why.",
        "how": "Kept by a person; a test checks every satellite with a signal ID today is tracked or explained.",
        "left_out": "Older generations are counted in the Library but not tracked.",
        "file": ("repo", "registry/dashboard_satellites.csv"), "date": ("column", "added"), "job": "hand",
        "licence": "ours", "offer": True, "link": ""},
    "sources": {
        "name": "News sources and their grades", "icon": "search", "shelf": "tables",
        "what": "Every source the news reader scans, with a reliability grade from A (operator) to F (unattributed).",
        "how": "Graded by a person, then checked weekly against the record of claims that held or failed.",
        "left_out": "A grade says how often a source was right before, not whether one article is.",
        "file": ("repo", "evidence/source_grades.csv"), "date": ("column", "graded_on"),
        "job": ("source-record.yml", ""), "licence": "ours", "offer": True, "link": ""},
    "orbit_gap": {
        "name": "Orbit record check", "icon": "map", "shelf": "published",
        "what": "How far each satellite's public orbit record is from the orbit it broadcasts itself, checked every day.",
        "how": "Each record is moved forward and compared with the broadcast orbit read from IGS files via BKG.",
        "left_out": "A satellite with no broadcast file that day is not checked.",
        "file": ("published", ORBIT_GAP), "date": ("json", "day"),
        "job": ("rinex-check.yml", ""), "licence": "ours", "offer": True, "link": ""},
    "fitted": {
        "name": "Fitted orbits", "icon": "planet", "shelf": "published",
        "what": "An orbit fitted to each satellite's own broadcast positions, for satellites whose public record is late.",
        "how": "Fitted to a day of broadcast positions from IGS files via BKG; each says how closely it fits.",
        "left_out": "A fit is only as good as the day it was made from; it ages like any record.",
        "file": ("published", FITTED), "date": ("json", "day"),
        "job": ("rinex-check.yml", ""), "licence": "ours", "offer": True, "link": ""},
    "news": {
        "name": "Latest news file", "icon": "broadcast", "shelf": "published",
        "what": "Headlines and short excerpts about each constellation, sorted into categories, with each source's grade.",
        "how": "Collected from feeds and official pages every 3 hours.",
        "left_out": "Only what feeds publish; paid articles show their opening only.",
        "file": ("published", NEWS), "date": ("json", "generated_at"),
        "job": ("archive.yml", "news"), "licence": "publishers", "offer": False,
        "why_not": "Headlines and excerpts belong to their publishers. Read them on the News page, each linked to its article.",
        "link": ""},
    "latest_gnss": {
        "name": "Newest orbit records", "icon": "satellite", "shelf": "others",
        "what": "The newest public orbit record of every navigation satellite.",
        "how": "Copied from CelesTrak four times a day by our archive job, because CelesTrak refuses this server.",
        "left_out": "A record can be days old; the top bar says how old.",
        "file": ("published", LATEST_GNSS), "date": None,
        "job": ("archive.yml", "orbital"), "licence": "celestrak", "offer": False,
        "why_not": "CelesTrak's records keep its terms; take them from CelesTrak itself.", "link": "https://celestrak.org/"},
    "histories": {
        "name": "A year of orbit records", "icon": "hourglass", "shelf": "others",
        "what": "Every public orbit record of the last year for NavIC, QZSS, BeiDou-3 and GLONASS, which the scores are worked out from.",
        "how": "Downloaded from Space-Track.org each week and bundled with the code.",
        "left_out": "GPS and Galileo histories are not bundled; their newest records come from CelesTrak.",
        "file": ("repo", "data/navic_gp_history.json"), "date": ("head", "timestamp"),
        "job": ("update-tle-data.yml", ""), "licence": "spacetrack", "offer": False,
        "why_not": "Space-Track's user agreement does not let us pass its records on. Sign up there for free to get them.",
        "link": "https://www.space-track.org/"},
    "gcat": {
        "name": "GCAT, the catalogue of space objects", "icon": "database", "shelf": "others",
        "what": "Jonathan McDowell's catalogue of every object launched into space, scanned daily by our archive job.",
        "how": "The Library's counts and the status per satellite are made from it.",
        "left_out": "We keep only the navigation satellites. The whole catalogue is on its own site.",
        "file": None, "date": None, "job": ("archive.yml", "catalogues"), "licence": "gcat", "offer": False,
        "why_not": "The full catalogue is its author's; the parts we use are on the Tables shelf.", "link": "https://planet4589.org/space/gcat/"},
    "igs": {
        "name": "IGS satellite file and broadcast orbits", "icon": "broadcast", "shelf": "others",
        "what": "The International GNSS Service's list of every navigation satellite, and the orbits satellites broadcast.",
        "how": "Scanned daily; the broadcast files are read from BKG for the orbit record check.",
        "left_out": "The broadcast files are large; we keep only what the checks need.",
        "file": None, "date": None, "job": ("archive.yml", "documents"), "licence": "igs", "offer": False,
        "why_not": "Take them from the IGS and BKG, who publish them openly.", "link": "https://igs.org/"},
    "land": {
        "name": "Natural Earth land", "icon": "map", "shelf": "others",
        "what": "The outline of the land drawn under the world maps.",
        "how": "The 110 m land file, bundled with the code.",
        "left_out": "A coarse outline: small islands are missing.",
        "file": None, "date": None, "job": "hand", "licence": "naturalearth", "offer": False,
        "why_not": "Free to everyone; take the original from Natural Earth.", "link": "https://www.naturalearthdata.com/"},
}

# How to cite, in this order: (who, the words).
CITATIONS = [
    ("This dashboard and its own data", "OpenGNSS: GNSS Constellation Health Monitoring System, data from OpenGNSS (opengnss.org), "
     "licensed CC BY 4.0. " + CODE_LINK),
    ("The counts and status per satellite", GCAT_CREDIT + ", licensed CC BY."),
    ("The registry and signal IDs", "International GNSS Service (IGS) satellite metadata file, via OpenGNSS (opengnss.org)."),
    ("Orbit records", "Orbital data from Space-Track.org and CelesTrak (celestrak.org)."),
]
BUNDLE_NAME = "opengnss-library.zip"
