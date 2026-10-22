"""Interactive live-pipeline component with three wording depths per stage."""
import csv
import importlib
import io
import re
from pathlib import Path

from evidence import jobs
from evidence.pipeline_words import PLAIN_STATES, STAGES
from ui.components.master_map import embed

PAGE_FILE = Path(__file__).with_name("live_pipeline.html")

_RUN_NUMBER = re.compile(r"/actions/runs/(\d+)")
_FAILED_SOURCES = re.compile(r"failed:\s*(\d+)\s+of\s+(\d+)\s+sources")
_STATE_TONE = {"running now": "info", "done": "ok", "failed": "bad", "waiting": "warn", "off": "idle"}
_COLLECT = ["archive_documents", "archive_catalogues", "archive_orbital", "archive_news", "archive_social"]
_CHAIN = ["archive", "registry_update", "decision_waiting", "decision_made", "merged_main", "dashboard"]


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
    if isinstance(value, str):
        return value
    if isinstance(value, Path):
        return str(value)
    return repr(value)


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
    for name in setting_names:
        found = next(((path, getattr(module, name)) for path, module in modules if hasattr(module, name)), None)
        if found:
            path, value = found
            rows.append(f"{name} = {_setting_value_words(value)} ({path})")
            continue
        where = ", ".join(setting_files) if setting_files else "unknown file"
        rows.append(f"{name} = not found ({where})")
    return rows


def payload(stages, next_stage_key, next_at, workflow_texts):
    """Data for the live-pipeline component."""
    by_key = {stage["key"]: stage for stage in stages}
    cards = []
    for key, words in STAGES.items():
        stage = by_key.get(key)
        if stage is None:
            continue
        facts = words["technical"]
        schedule = _schedule(facts.get("workflow_file", ""), facts.get("schedule_group", ""), workflow_texts)
        proof = stage.get("proof", {})
        setting_files = facts.get("settings_files", [])
        settings = _settings_with_values(facts.get("settings", []), setting_files)
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
            "commands": facts.get("commands", []),
            "inputs": facts.get("inputs", []),
            "outputs": facts.get("outputs", []),
            "repositories": facts.get("repositories", []),
            "settings": settings,
            "settings_files": setting_files,
            "limits": facts.get("limits", []),
            "last_start_exact": _when_exact((stage.get("last") or {}).get("start")),
            "last_end_exact": _when_exact((stage.get("last") or {}).get("end")),
            "last_duration_exact": _duration_words((stage.get("last") or {}).get("duration")),
            "last_result_exact": (stage.get("last") or {}).get("result", "not recorded"),
            "run_id": _run_id(proof.get("run_url")),
            "run_url": proof.get("run_url", ""),
            "commit": proof.get("archive_commit", ""),
            "commit_url": proof.get("archive_commit_url", ""),
            "pr_number": proof.get("pr_number"),
            "pr_url": proof.get("pr_url", ""),
            "pr_state": proof.get("pr_state", ""),
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
