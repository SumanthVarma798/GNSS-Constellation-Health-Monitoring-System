"""Single-source checks for job metadata used by console, alerts, and pipeline."""
import re

from evidence import jobs
from evidence.alert_settings import CHECKS
from evidence.console_settings import ARCHIVE_WORKFLOW, JOBS, RUN_LOGS, WORKFLOWS_DIR

_PING_PATH = re.compile(r"hc-ping\.com/\$KEY/([^\"'\s]+)")
_RUNS_CSV = re.compile(r"runs/[a-z0-9-]+\.csv")
_TAIL_RUN_LOG = re.compile(r"tail\s+-n\s+1\s+archive/(runs/[a-z0-9-]+\.csv)")
_LOG_RUN = re.compile(r"--log\s+([a-z0-9-]+)")
_ARCHIVE_GROUP_VAR = re.compile(r"archive-(?:\$\{[Gg][Rr][Oo][Uu][Pp]\}|\$[Gg][Rr][Oo][Uu][Pp])$")


def _workflow_texts():
    return {path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS_DIR.glob("*.yml")}


def _archive_groups(workflow_texts):
    return set(jobs.schedules(workflow_texts[ARCHIVE_WORKFLOW]))


def test_jobs_cover_scheduled_workflows_and_archive_groups_both_ways():
    workflow_texts = _workflow_texts()
    archive_groups = _archive_groups(workflow_texts)
    workflow_files = {path.name for path in WORKFLOWS_DIR.glob("*.yml")}
    jobs_by_pair = {(job.workflow, job.group) for job in JOBS}
    job_workflows = {job.workflow for job in JOBS}
    scheduled_workflows = {workflow for workflow, text in workflow_texts.items() if jobs.schedules(text)}

    assert len(jobs_by_pair) == len(JOBS)
    assert all(job.workflow in workflow_files for job in JOBS)
    assert scheduled_workflows <= job_workflows
    assert all(any(job.workflow == workflow for job in JOBS) for workflow in scheduled_workflows)
    assert {job.group for job in JOBS if job.workflow == ARCHIVE_WORKFLOW and job.group} == archive_groups
    assert all(job.workflow == ARCHIVE_WORKFLOW and job.group in archive_groups for job in JOBS if job.group)


def _expand_slug(path, archive_groups):
    first = path.split("?", 1)[0].split("/", 1)[0]
    if _ARCHIVE_GROUP_VAR.fullmatch(first):
        return {f"archive-{group}" for group in archive_groups}
    return {first}


def test_healthcheck_slugs_match_workflow_pings_both_ways():
    workflow_texts = _workflow_texts()
    archive_groups = _archive_groups(workflow_texts)
    pinged = set()
    # Only scheduled workflows are watched: a hand-run workflow (drills.yml) pings its own check when someone runs it.
    for text in (text for text in workflow_texts.values() if jobs.schedules(text)):
        for path in _PING_PATH.findall(text):
            pinged |= _expand_slug(path, archive_groups)
    check_slugs = {slug for slug, _ in CHECKS}

    assert pinged <= check_slugs
    assert check_slugs <= pinged


def test_run_logs_match_workflow_run_log_files():
    workflow_texts = _workflow_texts()
    text = "\n".join(workflow_texts.values())
    all_runs_csv = set(_RUNS_CSV.findall(text))
    run_logs = {f"runs/{name}.csv" for name in _LOG_RUN.findall(text)} | set(_TAIL_RUN_LOG.findall(text))

    # Every listed run log is a runs/*.csv file mentioned by workflows.
    assert run_logs <= all_runs_csv
    assert run_logs <= set(RUN_LOGS)
    assert set(RUN_LOGS) <= run_logs
