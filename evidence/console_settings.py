"""Settings for the administration console (admin.py, issue 17): its jobs, where their run logs are, and what it shows.

Schedules are not repeated here: they are read from the workflow files themselves (evidence/jobs.py), so the two cannot
drift apart. Who may sign in and the GitHub token are in .streamlit/secrets.toml under [admin], never here.
"""
from pathlib import Path
from typing import NamedTuple

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
ARCHIVE_REPOSITORY = "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive"   # private; holds the run logs

ARCHIVE_WORKFLOW = "archive.yml"
REGISTRY_UPDATE_WORKFLOW = "registry-update.yml"
SOURCE_RECORD_WORKFLOW = "source-record.yml"
ORBIT_AGES_WORKFLOW = "orbit-ages.yml"
RINEX_CHECK_WORKFLOW = "rinex-check.yml"
UPDATE_TLE_WORKFLOW = "update-tle-data.yml"
TESTS_WORKFLOW = "tests.yml"

ARCHIVE_ALL_LOG = "archive all"
ARCHIVE_LOG_ALIASES = {ARCHIVE_ALL_LOG: ARCHIVE_WORKFLOW}


class Job(NamedTuple):
    workflow: str
    group: str
    name: str
    what: str
    log_name: str | None
    key: str
    checks: tuple[tuple[str, str], ...]
    run_log: str | None
    stage: bool

# Every job the console lists, in this order.
# - group: the word before ':' in archive.yml schedule comments ("documents", "news", ...), or "".
# - log_name: the job name in the archive run log; when absent, GitHub's workflow runs are used directly.
# - key: stable stage id used by pipeline/UI modules.
# - checks: Healthchecks.io slug + label pairs this job reports to.
# - run_log: CSV path in the archive repository with this job's run lines.
# - stage: True only for jobs that appear as explicit stages in the live pipeline.
JOBS: list[Job] = [
    Job(ARCHIVE_WORKFLOW, "documents", "Archive: documents",
        "Copies the IGS satellite file and other documents", "archive documents", "archive_documents",
        (("archive-documents", "Archive: documents"),), "runs/archive.csv", True),
    Job(ARCHIVE_WORKFLOW, "catalogues", "Archive: catalogues",
        "Copies GCAT's catalogue files", "archive catalogues", "archive_catalogues",
        (("archive-catalogues", "Archive: catalogues"),), "runs/archive.csv", True),
    Job(ARCHIVE_WORKFLOW, "orbital", "Archive: orbit records",
        "Copies CelesTrak's GNSS orbit records", "archive orbital", "archive_orbital",
        (("archive-orbital", "Archive: orbit records"),), "runs/archive.csv", True),
    Job(ARCHIVE_WORKFLOW, "news", "Archive: news",
        "Copies news, official pages and newsletters", "archive news", "archive_news",
        (("archive-news", "Archive: news"),), "runs/archive.csv", True),
    Job(ARCHIVE_WORKFLOW, "social", "Archive: social",
        "Copies Reddit feeds, for the links they carry", "archive social", "archive_social",
        (("archive-social", "Archive: social"),), "runs/archive.csv", True),
    Job(ARCHIVE_WORKFLOW, "x", "Archive: X posts",
        "Copies selected X accounts through twitterapi.io, one page per account", "archive x", "archive_x",
        (("archive-x", "Archive: X posts"),), "runs/archive.csv", False),
    Job(ARCHIVE_WORKFLOW, "launches", "Archive: recent launches",
        "Copies Space-Track's list of payloads launched lately", "archive launches", "archive_launches",
        (("archive-launches", "Archive: recent launches"),), "runs/archive.csv", True),
    Job(REGISTRY_UPDATE_WORKFLOW, "", "Registry update",
        "Rebuilds the satellite tables from the IGS file; proposes any change", "registry update", "registry_update",
        (("registry-update", "Registry update"),), "runs/registry-update.csv", True),
    Job(SOURCE_RECORD_WORKFLOW, "", "Source record",
        "Rebuilds source grades from checked claims; proposes any change", "source record", "source_record",
        (("source-record", "Source record"),), "runs/source-record.csv", False),
    Job(ORBIT_AGES_WORKFLOW, "", "Orbit ages",
        "Measures each satellite's orbit record age; Space-Track fills in old ones", "orbit ages", "orbit_ages",
        (("orbit-ages", "Orbit ages"), ("orbit-fresh", "Orbit ages: every satellite under 2 days")),
        "runs/orbit-ages.csv", True),
    Job(RINEX_CHECK_WORKFLOW, "", "Orbit record check",
        "Measures each orbit record against the satellite's broadcast orbit", "rinex check", "rinex_check",
        (("rinex-check", "RINEX check"),), "runs/rinex-check.csv", True),
    Job(UPDATE_TLE_WORKFLOW, "", "Update orbit data",
        "Refreshes the dashboard's bundled orbit data", None, "update_tle_data",
        (("update-tle-data", "Update orbit data"),), None, False),
    Job(TESTS_WORKFLOW, "", "Tests", "Runs every test on each change", None, "tests", (), None, False),
]

RUN_LOGS = tuple(dict.fromkeys(job.run_log for job in JOBS if job.run_log))  # in the archive: one line per run

ORBIT_LOG_JOB = "archive orbital"   # its last good run is the age of the archived orbit data

RELIABILITY_DAYS = 14   # columns in the day-by-day reliability grid
RECENT_EVENTS = 10      # lines in the Summary's recent events
RUNS_READ = 100         # GitHub's largest page of runs
LOOK_AHEAD_DAYS = 8     # a schedule with no run within this many days says "none in the next week"
PIPELINE_FEED_EVENTS = 20        # lines in the live pipeline's proof feed
PIPELINE_LOOK_AHEAD_HOURS = 24   # how far ahead the live pipeline's Next up panel looks
PIPELINE_READ_EVERY_SECONDS = 30   # how often the live pipeline page refreshes itself
