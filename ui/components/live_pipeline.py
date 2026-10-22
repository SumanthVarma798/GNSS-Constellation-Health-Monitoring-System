"""Interactive live-pipeline component with three wording depths per stage."""
import csv
from datetime import datetime, timedelta, timezone
import importlib
import io
from pathlib import PurePosixPath
from pathlib import Path
import re
import shlex

from evidence import jobs
from evidence.pipeline_words import PLAIN_STATES, SETTING_SENTENCES, STAGES
from ui.components.master_map import embed

PAGE_FILE = Path(__file__).with_name("live_pipeline.html")

_RUN_NUMBER = re.compile(r"/actions/runs/(\d+)")
_FAILED_SOURCES = re.compile(r"failed:\s*(\d+)\s+of\s+(\d+)\s+sources")
_STATE_TONE = {"running now": "info", "done": "ok", "failed": "bad", "waiting": "warn", "off": "idle"}
_COLLECT = ["archive_documents", "archive_catalogues", "archive_orbital", "archive_news", "archive_social"]
_CHAIN = ["archive", "registry_update", "decision_waiting", "decision_made", "merged_main", "dashboard"]
_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_EVENT_DRIVEN_KEYS = {"decision_waiting", "decision_made", "merged_main", "dashboard"}


def _when(moment):
    return f"{moment.day} {moment:%b} at {moment:%H:%M} UTC" if moment else "not recorded"


def _when_exact(moment):
    return f"{moment:%Y-%m-%d %H:%M:%S UTC}" if moment else "not recorded"


def _duration_words(delta):
    if delta is None:
        return "not recorded"
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds} s"
    minutes, left = divmod(seconds, 60)
    return f"{minutes} min {left:02d} s"


def _last_sentence(last):
    if not last or not last.get("start"):
        return "It has not run yet in the recent record."
    result = (last.get("result") or "not recorded").strip()
    if found := _FAILED_SOURCES.search(result.lower()):
        detail = f"{found.group(1)} of {found.group(2)} sources could not be fetched"
    else:
        detail = f'ended with result "{result}"'
    return f"It last ran on {_when(last['start'])}, took {_duration_words(last.get('duration'))}, and {detail}."


def _next_sentence(next_at):
    return f"Next time: {_when(next_at)}." if next_at else "Next time: no scheduled run is listed."


def _run_id(url):
    return _RUN_NUMBER.search(url or "").group(1) if url and _RUN_NUMBER.search(url or "") else None


def _schedule(workflow_file, schedule_group, workflow_texts):
    if not workflow_file:
        return {"crons": [], "words": [], "note": "No cron: this stage is event-driven."}
    text = workflow_texts.get(Path(workflow_file).name, "")
    crons = jobs.schedules(text).get(schedule_group, [])
    if crons:
        return {"crons": crons, "words": [jobs.schedule_words(cron) for cron in crons], "note": "UTC"}
    return {"crons": [], "words": [], "note": "No cron in this workflow for this stage."}


def _raw_log_line(stage):
    line = stage.get("log_line")
    if not line:
        return "not recorded for this stage"
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="")
    writer.writerow([
        stage.get("log_job") or line.get("job", ""),
        f"{line['started']:%Y-%m-%dT%H:%M:%SZ}",
        line.get("ended", ""),
        line.get("result", ""),
        line.get("changed", ""),
    ])
    return out.getvalue()


def _setting_value_words(value):
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        if total_seconds % 86400 == 0:
            days = total_seconds // 86400
            return f"{days} day{'s' if days != 1 else ''}"
        if total_seconds % 3600 == 0:
            hours = total_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        if total_seconds % 60 == 0:
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        return f"{total_seconds} second{'s' if total_seconds != 1 else ''}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return ", ".join([f"{key}: {item}" for key, item in value.items()]) if value else "(empty)"
    if isinstance(value, (tuple, list)):
        return ", ".join([str(item) for item in value]) if value else "(empty)"
    if isinstance(value, (set, frozenset)):
        return ", ".join([str(item) for item in sorted(value, key=str)]) if value else "(empty)"
    return str(value)


def _setting_display_value(name, value):
    if isinstance(value, int):
        if name.endswith("_SECONDS"):
            return f"{value} second{'s' if value != 1 else ''}"
        if name.endswith("_DAYS"):
            return f"{value} day{'s' if value != 1 else ''}"
    return _setting_value_words(value)


def _repository_short_name(repository):
    repo_name = PurePosixPath(repository).name.lower()
    return "archive repository" if repo_name.endswith("-archive") else "project repository"


def _cron_values(field, low, high):
    allowed = set()
    for part in field.split(","):
        span, _, step = part.partition("/")
        first, last = (low, high) if span == "*" else map(int, span.split("-")) if "-" in span else (int(span), int(span))
        if step and span != "*" and "-" not in span:
            last = high
        allowed.update(range(first, last + 1, int(step or 1)))
    return allowed


def _seconds_from_value(value):
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    if isinstance(value, int):
        return value
    return None


def _seconds_words(seconds):
    if seconds is None:
        return "not recorded"
    if seconds % 86400 == 0:
        return f"{seconds // 86400} d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600} h"
    if seconds % 60 == 0:
        return f"{seconds // 60} min"
    return f"{seconds} s"


def _schedule_marks_daily(crons, next_at):
    minutes = set()
    for cron in crons:
        minute, hour, day, month, weekday = cron.split()
        if day != "*" or month != "*" or weekday != "*":
            continue
        for at_hour in _cron_values(hour, 0, 23):
            for at_minute in _cron_values(minute, 0, 59):
                minutes.add(at_hour * 60 + at_minute)
    next_minute = (next_at.hour * 60 + next_at.minute) if next_at else None
    return [{"minute_of_day": minute, "utc": f"{minute // 60:02d}:{minute % 60:02d}", "is_next": minute == next_minute}
            for minute in sorted(minutes)]


def _cron_weekday_to_strip(weekday):
    return 6 if weekday == 0 else weekday - 1


def _schedule_marks_weekly(crons, next_at):
    marks = {}
    next_pair = (next_at.weekday(), next_at.hour * 60 + next_at.minute) if next_at else None
    for cron in crons:
        minute, hour, day, month, weekday = cron.split()
        if day != "*" or month != "*" or weekday == "*":
            continue
        for week_day in _cron_values(weekday, 0, 6):
            strip_day = _cron_weekday_to_strip(week_day)
            for at_hour in _cron_values(hour, 0, 23):
                for at_minute in _cron_values(minute, 0, 59):
                    minute_of_day = at_hour * 60 + at_minute
                    key = (strip_day, minute_of_day)
                    marks[key] = {"weekday": _WEEKDAYS[strip_day], "weekday_index": strip_day, "minute_of_day": minute_of_day,
                                  "utc": f"{_WEEKDAYS[strip_day]} {at_hour:02d}:{at_minute:02d}", "is_next": key == next_pair}
    return [marks[key] for key in sorted(marks)]


def _result_tone(words):
    said = (words or "").lower()
    if any(ok in said for ok in ("ok", "success", "succeeded", "passed", "merged")):
        return "ok"
    if any(bad in said for bad in ("failed", "failure", "timed out", "error", "cancelled")):
        return "bad"
    if "waiting" in said or "open" in said:
        return "warn"
    return "info" if said else "idle"


def _last_run_visual(last):
    if not last or not last.get("start"):
        return {"recorded": False, "start_utc": "not recorded", "end_utc": "not recorded", "duration_words": "not recorded",
                "duration_seconds": 0, "result_words": "not recorded", "tone": "idle", "start_minute_of_day": 0,
                "end_minute_of_day": 0, "start_weekday_index": 0, "end_weekday_index": 0}
    start = last["start"]
    end = last.get("end") or start
    duration = last.get("duration")
    duration_seconds = max(0, int(duration.total_seconds())) if duration else max(0, int((end - start).total_seconds()))
    day_delta = max(0, (end.date() - start.date()).days)
    start_minute = start.hour * 60 + start.minute
    end_minute = end.hour * 60 + end.minute + day_delta * 24 * 60
    if end_minute <= start_minute:
        end_minute = start_minute + max(1, duration_seconds // 60 or 1)
    result_words = last.get("result", "not recorded")
    return {"recorded": True, "start_utc": _when_exact(start), "end_utc": _when_exact(end), "duration_words": _duration_words(duration),
            "duration_seconds": duration_seconds, "result_words": result_words, "tone": _result_tone(result_words),
            "start_minute_of_day": start_minute, "end_minute_of_day": end_minute, "start_weekday_index": start.weekday(),
            "end_weekday_index": end.weekday()}


def _flow_data(facts):
    commands = facts.get("commands", [])
    inputs = facts.get("inputs", [])
    outputs = facts.get("outputs", [])
    repositories = facts.get("repositories", [])
    paths = facts.get("paths", [])

    script_paths = []
    for command in commands:
        try:
            bits = shlex.split(command)
        except ValueError:
            bits = command.split()
        script_paths.extend([bit for bit in bits if bit.endswith(".py")])

    command_paths = [piece for piece in [facts.get("workflow_file", ""), facts.get("workflow_job", ""), *script_paths] if piece]
    command_path = " | ".join(command_paths) if command_paths else "not recorded"
    project_paths = " | ".join(paths) if paths else "not recorded"

    nodes = [
        {"id": "inputs", "label": "Inputs", "status_words": f"{len(inputs)} item{'s' if len(inputs) != 1 else ''}",
         "path": project_paths, "what": " | ".join(inputs) if inputs else "not recorded"},
        {"id": "command", "label": "Command", "status_words": "workflow + job + script",
         "path": command_path, "what": " | ".join(commands) if commands else "not recorded"},
        {"id": "outputs", "label": "Outputs", "status_words": f"{len(outputs)} item{'s' if len(outputs) != 1 else ''}",
         "path": project_paths, "what": " | ".join(outputs) if outputs else "not recorded"},
    ]
    edges = [{"from": "inputs", "to": "command"}, {"from": "command", "to": "outputs"}]

    for index, repository in enumerate(repositories):
        repo_id = f"repo_{index + 1}"
        nodes.append({"id": repo_id, "label": _repository_short_name(repository), "status_words": "linked",
                      "path": repository, "what": "Repository touched by this step."})
        edges.append({"from": "outputs", "to": repo_id})

    return {"nodes": nodes, "edges": edges, "default_node": "command"}


def _settings_with_values(setting_names, setting_files):
    modules = []
    for path in setting_files:
        module_name = path.removesuffix(".py").replace("/", ".")
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        modules.append((path, module))

    rows = []
    cards = []
    values = {}
    for name in setting_names:
        found = next(((path, getattr(module, name)) for path, module in modules if hasattr(module, name)), None)
        sentence = SETTING_SENTENCES.get(name, "What this setting controls is described in the source comments.")
        if found:
            path, value = found
            value_words = _setting_display_value(name, value)
            raw_value = repr(value)
            rows.append(f"{name} = {value_words} ({path})")
            cards.append({"name": name, "value": value_words, "raw_value": raw_value, "file": path, "sentence": sentence})
            values[name] = value
            continue
        where = ", ".join(setting_files) if setting_files else "unknown file"
        rows.append(f"{name} = not found ({where})")
        cards.append({"name": name, "value": "not found", "raw_value": "not found", "file": where, "sentence": sentence})
    return rows, cards, values


def _retry_backoff_data(setting_values):
    required = {"DOWNLOAD_TRIES", "WAIT_BETWEEN_TRIES_SECONDS", "BACKOFF_FIRST", "BACKOFF_LONGEST"}
    if not required.issubset(setting_values):
        return None
    tries = int(setting_values["DOWNLOAD_TRIES"])
    wait_between = _seconds_from_value(setting_values["WAIT_BETWEEN_TRIES_SECONDS"])
    first_wait = _seconds_from_value(setting_values["BACKOFF_FIRST"])
    longest_wait = _seconds_from_value(setting_values["BACKOFF_LONGEST"])
    if wait_between is None or first_wait is None or longest_wait is None:
        return None
    steps = []
    current = first_wait
    for _ in range(12):
        steps.append(current)
        if current >= longest_wait:
            break
        current = min(current * 2, longest_wait)
    return {"tries": tries, "wait_between_tries_seconds": wait_between, "first_wait_seconds": first_wait,
            "longest_wait_seconds": longest_wait, "steps_seconds": steps, "steps_words": [_seconds_words(step) for step in steps],
            "note": (f"After a refusal: wait {_seconds_words(first_wait)}, then double until the "
                     f"{_seconds_words(longest_wait)} cap.")}


def _schedule_visual(stage_key, schedule, stage, now):
    crons = schedule["crons"]
    if not crons:
        if stage_key in _EVENT_DRIVEN_KEYS:
            return {"kind": "event", "note": "runs when the step before it finishes"}
        return {"kind": "event", "note": schedule["note"]}

    next_at = stage.get("next")
    last_run = _last_run_visual(stage.get("last"))
    now_words = {"weekday_index": now.weekday(), "minute_of_day": now.hour * 60 + now.minute}

    if any(cron.split()[4] != "*" for cron in crons):
        return {"kind": "weekly", "timezone": "UTC", "days": _WEEKDAYS, "marks": _schedule_marks_weekly(crons, next_at),
                "now": now_words, "next_utc": _when(next_at), "last_run": last_run}

    return {"kind": "daily", "timezone": "UTC", "ticks": list(range(0, 25)), "marks": _schedule_marks_daily(crons, next_at),
            "now": now_words, "next_utc": _when(next_at), "last_run": last_run}


def _proof_chips(proof):
    run_id = _run_id(proof.get("run_url"))
    run_words = f"run {run_id}" if run_id else ("GitHub run" if proof.get("run_url") else "not recorded")
    return [
        {"label": "GitHub run", "words": run_words, "url": proof.get("run_url", ""),
         "recorded": bool(proof.get("run_url"))},
        {"label": "Archive commit", "words": proof["archive_commit"][:7] if proof.get("archive_commit") else "not recorded",
         "url": proof.get("archive_commit_url", ""), "recorded": bool(proof.get("archive_commit"))},
        {"label": "Pull request", "words": f"#{proof['pr_number']}" if proof.get("pr_number") else "not recorded",
         "url": proof.get("pr_url", ""), "recorded": bool(proof.get("pr_number"))},
    ]


def payload(stages, next_stage_key, next_at, workflow_texts, now=None):
    """Data for the live-pipeline component."""
    by_key = {stage["key"]: stage for stage in stages}
    cards = []
    now = now or datetime.now(timezone.utc)
    for key, words in STAGES.items():
        stage = by_key.get(key)
        if stage is None:
            continue
        facts = words["technical"]
        schedule = _schedule(facts.get("workflow_file", ""), facts.get("schedule_group", ""), workflow_texts)
        proof = stage.get("proof", {})
        setting_files = facts.get("settings_files", [])
        settings, setting_cards, setting_values = _settings_with_values(facts.get("settings", []), setting_files)
        cards.append({
            "key": key,
            "plain_name": words["plain_name"],
            "technical_name": stage["name"],
            "state_plain": PLAIN_STATES.get(stage["state"], stage["state"]),
            "state_technical": stage["state"],
            "tone": _STATE_TONE.get(stage["state"], "idle"),
            "running": stage["state"] == "running now",
            "next_badge": key == next_stage_key and next_at is not None,
            "next_badge_words": f"Next {_when(next_at)}",
            "what_happens": words["what_happens"],
            "why_it_matters": words["why_it_matters"],
            "last_sentence": _last_sentence(stage.get("last")),
            "next_sentence": _next_sentence(stage.get("next")),
            "workflow_file": facts.get("workflow_file", ""),
            "workflow_job": facts.get("workflow_job", ""),
            "schedule_crons": schedule["crons"],
            "schedule_words": schedule["words"],
            "schedule_note": schedule["note"],
            "schedule_visual": _schedule_visual(key, schedule, stage, now),
            "commands": facts.get("commands", []),
            "inputs": facts.get("inputs", []),
            "outputs": facts.get("outputs", []),
            "repositories": facts.get("repositories", []),
            "flow": _flow_data(facts),
            "settings": settings,
            "settings_cards": setting_cards,
            "retry_backoff": _retry_backoff_data(setting_values),
            "settings_files": setting_files,
            "limits": facts.get("limits", []),
            "last_start_exact": _when_exact((stage.get("last") or {}).get("start")),
            "last_end_exact": _when_exact((stage.get("last") or {}).get("end")),
            "last_duration_exact": _duration_words((stage.get("last") or {}).get("duration")),
            "last_result_exact": (stage.get("last") or {}).get("result", "not recorded"),
            "last_run_visual": _last_run_visual(stage.get("last")),
            "run_id": _run_id(proof.get("run_url")),
            "run_url": proof.get("run_url", ""),
            "commit": proof.get("archive_commit", ""),
            "commit_url": proof.get("archive_commit_url", ""),
            "pr_number": proof.get("pr_number"),
            "pr_url": proof.get("pr_url", ""),
            "pr_state": proof.get("pr_state", ""),
            "proof_chips": _proof_chips(proof),
            "raw_log_line": _raw_log_line(stage),
        })
    return {
        "cards": cards,
        "collect_keys": [key for key in _COLLECT if key in by_key],
        "chain_keys": [key for key in _CHAIN if key in by_key],
        "default_key": next((stage["key"] for stage in stages if stage["state"] == "running now"), next_stage_key or stages[0]["key"]),
    }


def live_pipeline_html(tokens_css, font, data):
    """HTML for the live-pipeline component."""
    page = PAGE_FILE.read_text(encoding="utf-8").replace("__TOKENS__", tokens_css).replace("__FONT__", font)
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(data)};", 1)
