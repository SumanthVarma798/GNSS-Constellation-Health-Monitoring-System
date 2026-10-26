"""The live pipeline logic (evidence/pipeline.py): stage states, what runs next, and proof links."""
from datetime import datetime, timedelta, timezone

from evidence import jobs, pipeline
from evidence.console_settings import WORKFLOWS_DIR
from test_decisions import pr
from test_jobs import LOG, NOW, RUNS, WORKFLOWS, run


def workflow_texts():
    names = ("archive.yml", "registry-update.yml", "orbit-ages.yml", "tests.yml")
    return {name: (WORKFLOWS_DIR / name).read_text(encoding="utf-8") for name in names}


def stage_map(stages):
    return {stage["name"]: stage for stage in stages}


def test_a_stage_with_an_in_progress_run_is_running_now():
    stages = pipeline.stages(WORKFLOWS, [run("archive.yml", "2026-10-20T14:30:00Z", status="in_progress")], [],
                             [], workflow_texts(), NOW)

    assert stage_map(stages)["Archive: documents"]["state"] == "waiting"
    assert stage_map(stages)["Archive"]["state"] == "running now"


def test_the_running_stage_keeps_the_current_run_start_time():
    stages = pipeline.stages(WORKFLOWS, [run("registry-update.yml", "2026-10-20T14:30:00Z", status="in_progress")],
                             jobs.run_log("""job,started,ended,result,changed
registry update,2026-10-20T12:15:00Z,2026-10-20T12:17:00Z,ok,nothing
"""), [], workflow_texts(), NOW)

    assert stage_map(stages)["Registry update"]["running_start"] == datetime(2026, 10, 20, 14, 30, tzinfo=timezone.utc)


def test_a_failed_archive_group_stage_takes_its_result_from_the_run_log():
    stages = pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [], workflow_texts(), NOW)
    news = stage_map(stages)["Archive: news"]

    assert news["state"] == "failed"
    assert news["last"]["result"] == "failed: 6 of 44 sources"
    assert news["last"]["changed"] == "https://c"


def test_archive_groups_without_their_own_log_line_stay_waiting():
    stages = stage_map(pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [], workflow_texts(), NOW))

    for name in ("Archive: documents", "Archive: catalogues", "Archive: social"):
        assert stages[name]["state"] == "waiting"
        assert stages[name]["last"] is None
        assert stages[name]["proof"]["run_url"] is None
    assert stages["Archive"]["state"] == "failed"


def test_a_disabled_workflow_stage_is_off_and_has_no_next_run():
    workflows = [*WORKFLOWS, {"path": ".github/workflows/registry-update.yml", "state": "disabled_manually"}]
    stages = pipeline.stages(workflows, RUNS, jobs.run_log(LOG), [], workflow_texts(), NOW)
    registry = stage_map(stages)["Registry update"]

    assert registry["state"] == "off"
    assert registry["next"] is None


def test_the_next_run_is_read_from_the_workflow_schedule():
    stages = pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [], workflow_texts(), NOW)

    assert stage_map(stages)["Archive: documents"]["next"] == datetime(2026, 10, 21, 0, 30, tzinfo=timezone.utc)


def test_stage_proof_links_cover_the_run_archive_commit_and_opened_pull_request():
    log = jobs.run_log("""job,started,ended,result,changed
archive documents,2026-10-20T05:00:00Z,2026-10-20T05:01:00Z,ok,https://github.com/acme/archive/commit/abc1234
registry update,2026-10-20T06:00:00Z,2026-10-20T06:02:00Z,ok,tables changed, proposal opened or updated
""")
    runs = [run("archive.yml", "2026-10-20T05:00:00Z"), run("registry-update.yml", "2026-10-20T06:00:00Z")]
    registry_pr = pr(8, ["decision: registry update"], created="2026-10-20T06:05:00Z")

    stages = pipeline.stages(WORKFLOWS, runs, log, [registry_pr], workflow_texts(), NOW)
    archive = stage_map(stages)["Archive: documents"]
    registry = stage_map(stages)["Registry update"]

    assert archive["proof"]["run_url"] == "https://github.com/x"
    assert archive["proof"]["archive_commit"] == "abc1234"
    assert archive["proof"]["archive_commit_url"] == "https://github.com/acme/archive/commit/abc1234"
    assert registry["proof"]["pr_number"] == 8
    assert registry["proof"]["pr_url"].endswith("/pull/8")
    assert registry["proof"]["pr_state"] == "open"


def test_without_an_explicit_archive_commit_the_stage_says_not_recorded():
    log = jobs.run_log("""job,started,ended,result,changed
archive documents,2026-10-20T05:00:00Z,2026-10-20T05:01:00Z,ok,files updated
""")
    runs = [{**run("archive.yml", "2026-10-20T05:00:00Z"), "head_sha": "abcdef1234567"}]

    stages = pipeline.stages(WORKFLOWS, runs, log, [], workflow_texts(), NOW)

    assert stage_map(stages)["Archive: documents"]["proof"]["archive_commit"] is None
    assert stage_map(stages)["Archive: documents"]["proof"]["archive_commit_url"] is None


def test_what_next_lists_the_soonest_stage_runs_in_the_next_day():
    stages = pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [], workflow_texts(), NOW)
    upcoming = pipeline.what_next(stages, NOW, hours=24)

    assert [item["name"] for item in upcoming][:2] == ["Archive: news", "Archive: documents"]
    assert all((item["at"] - NOW) <= timedelta(hours=24) for item in upcoming)


def test_closed_or_merged_decision_pull_requests_drive_the_decision_stages():
    registry_pr = {**pr(9, ["decision: registry update"], created="2026-10-20T06:05:00Z"), "state": "closed",
                   "merged_at": "2026-10-20T06:15:00Z", "closed_at": "2026-10-20T06:15:00Z"}

    stages = stage_map(pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [registry_pr], workflow_texts(), NOW))

    assert stages["Pull request waiting for a decision"]["state"] == "done"
    assert stages["Decided on the Approvals page"]["state"] == "done"
    assert stages["Merged to main"]["state"] == "done"


def test_an_open_decision_pull_request_keeps_waiting_and_merge_waiting_states():
    waiting = {**pr(10, ["decision: registry update"], created="2026-10-20T06:05:00Z"), "state": "open",
               "merged_at": None, "closed_at": None}

    stages = stage_map(pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [waiting], workflow_texts(), NOW))

    assert stages["Pull request waiting for a decision"]["state"] == "waiting"
    assert stages["Decided on the Approvals page"]["state"] == "waiting"
    assert stages["Merged to main"]["state"] == "waiting"


def test_a_rejected_decision_does_not_mark_merged_to_main_as_failed():
    rejected = {**pr(11, ["decision: registry update"], created="2026-10-20T06:05:00Z"), "state": "closed",
                "merged_at": None, "closed_at": "2026-10-20T06:15:00Z"}

    stages = stage_map(pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [rejected], workflow_texts(), NOW))

    assert stages["Merged to main"]["state"] == "waiting"


def test_decided_and_merged_stages_follow_decision_time_not_creation_time():
    merged_later = {**pr(9, ["decision: registry update"], created="2026-10-18T06:05:00Z"), "state": "closed",
                    "merged_at": "2026-10-20T06:15:00Z", "closed_at": "2026-10-20T06:15:00Z"}
    rejected_earlier = {**pr(10, ["decision: registry update"], created="2026-10-19T06:05:00Z"), "state": "closed",
                        "merged_at": None, "closed_at": "2026-10-19T06:15:00Z"}

    stages = stage_map(pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [merged_later, rejected_earlier],
                                       workflow_texts(), NOW))

    assert stages["Decided on the Approvals page"]["proof"]["pr_number"] == 9
    assert stages["Merged to main"]["proof"]["pr_number"] == 9


def test_an_old_log_line_without_a_matching_recent_run_has_no_run_link():
    old = jobs.run_log("""job,started,ended,result,changed
archive social,2026-09-01T00:00:00Z,2026-09-01T00:01:00Z,ok,nothing
""")
    recent = [run("archive.yml", "2026-10-20T12:15:00Z")]

    feed = pipeline.proof_feed(recent, old, [], limit=20)

    assert feed[0]["link"] is None


def test_the_proof_feed_is_newest_first_and_kept_to_the_limit():
    lines = []
    for minute in range(25):
        at = datetime(2026, 10, 20, 10, minute, tzinfo=timezone.utc)
        lines.append(f"archive news,{at:%Y-%m-%dT%H:%M:%SZ},{(at + timedelta(seconds=30)):%Y-%m-%dT%H:%M:%SZ},ok,nothing")
    log = jobs.run_log("job,started,ended,result,changed\n" + "\n".join(lines) + "\n")
    prs = [
        {**pr(71, ["decision: registry update"], created="2026-10-20T11:00:00Z"), "state": "open"},
        {**pr(72, ["decision: registry update"], created="2026-10-20T09:00:00Z"), "state": "closed",
         "merged_at": "2026-10-20T11:05:00Z", "closed_at": "2026-10-20T11:05:00Z"},
    ]

    feed = pipeline.proof_feed([], log, prs, limit=20)

    assert len(feed) == 20
    assert [event["time"] for event in feed] == sorted((event["time"] for event in feed), reverse=True)
    assert feed[0]["words"].startswith("Pull request #72 merged")
    assert any(event["words"].startswith("Pull request #71 opened") for event in feed)
    assert all(event.get("link_words") for event in feed if event.get("link"))


def test_the_proof_feed_links_manual_archive_all_runs():
    log = jobs.run_log("""job,started,ended,result,changed
archive all,2026-10-20T05:00:00Z,2026-10-20T05:02:00Z,ok,all groups
""")
    feed = pipeline.proof_feed([run("archive.yml", "2026-10-20T05:00:00Z")], log, [], limit=20)

    assert feed[0]["words"] == "archive all finished: ok"
    assert feed[0]["link"] == "https://github.com/x"


def test_a_run_without_an_actions_run_number_is_named_as_a_github_run():
    log = jobs.run_log("""job,started,ended,result,changed
archive documents,2026-10-20T05:00:00Z,2026-10-20T05:01:00Z,ok,nothing
""")
    feed = pipeline.proof_feed([run("archive.yml", "2026-10-20T05:00:00Z")], log, [], limit=20)

    assert feed[0]["link_words"] == "GitHub run"
