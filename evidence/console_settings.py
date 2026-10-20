"""Settings for the administration console (admin.py, issue 17): its jobs, where their run logs are, and what it shows.

Schedules are not repeated here: they are read from the workflow files themselves (evidence/jobs.py), so the two cannot
drift apart. Who may sign in and the GitHub token are in .streamlit/secrets.toml under [admin], never here.
"""
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
ARCHIVE_REPOSITORY = "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive"   # private; holds the run logs
RUN_LOGS = ("runs/archive.csv", "runs/registry-update.csv")   # in the archive: one line per run (ARCHIVE_RUN_COLUMNS)

# Every job the console lists, in this order: (workflow file, schedule group, name, what it does, its name in the run
# log). The group is the word that starts the comment after a cron line in archive.yml ("documents", "news", ...);
# "" for a workflow with one schedule or none. A job with no run-log name is read from GitHub's record alone.
JOBS = [
    ("archive.yml", "documents", "Archive: documents", "Copies the IGS satellite file and other documents", "archive documents"),
    ("archive.yml", "catalogues", "Archive: catalogues", "Copies GCAT's catalogue files", "archive catalogues"),
    ("archive.yml", "orbital", "Archive: orbit records", "Copies CelesTrak's GNSS orbit records", "archive orbital"),
    ("archive.yml", "news", "Archive: news", "Copies news, official pages and newsletters", "archive news"),
    ("archive.yml", "social", "Archive: social", "Copies Reddit feeds, for the links they carry", "archive social"),
    ("registry-update.yml", "", "Registry update", "Rebuilds the satellite tables from the IGS file; proposes any change",
     "registry update"),
    ("update-tle-data.yml", "", "Update orbit data", "Refreshes the dashboard's bundled orbit data", None),
    ("tests.yml", "", "Tests", "Runs every test on each change", None),
]
ORBIT_LOG_JOB = "archive orbital"   # its last good run is the age of the archived orbit data
TESTS_WORKFLOW = "tests.yml"

RELIABILITY_DAYS = 14   # columns in the day-by-day reliability grid
RECENT_EVENTS = 10      # lines in the Summary's recent events
RUNS_READ = 100         # GitHub's largest page of runs
LOOK_AHEAD_DAYS = 8     # a schedule with no run within this many days says "none in the next week"
