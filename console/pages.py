"""The administration console's pages: one list for navigation, links, and page metadata."""
from dataclasses import dataclass
from typing import Any

import streamlit as st


@dataclass(frozen=True)
class ConsolePage:
    section: str
    path: str
    title: str
    material_icon: str
    icon_key: str
    url_path: str
    default: bool = False


SUMMARY = ConsolePage("Overview", "console/summary.py", "Summary", ":material/dashboard:", "summary", "", default=True)
DESIGN = ConsolePage("Overview", "console/design.py", "System design", ":material/account_tree:", "design", "design")
ASK = ConsolePage("Overview", "console/ask.py", "Ask", ":material/forum:", "ask", "ask")

SOURCES = ConsolePage("Monitoring", "console/sources.py", "Sources", ":material/public:", "sources", "sources")
JOBS = ConsolePage("Monitoring", "console/jobs.py", "Jobs", ":material/schedule:", "jobs", "jobs")
PIPELINE = ConsolePage("Monitoring", "console/pipeline.py", "Live pipeline", ":material/conveyor_belt:", "pipeline", "pipeline")
ALERTS = ConsolePage("Monitoring", "console/alerts.py", "Alerts", ":material/notifications_active:", "alerts", "alerts")

WORK = ConsolePage("Work", "console/work.py", "Issues and pull requests", ":material/list_alt:", "work", "work")
APPROVALS = ConsolePage("Work", "console/approvals.py", "Approvals", ":material/task_alt:", "approvals", "approvals")
CONTACT = ConsolePage("Work", "console/contact.py", "Contact inbox", ":material/mail:", "contact", "contact")

PAGES = (SUMMARY, DESIGN, ASK, SOURCES, JOBS, PIPELINE, ALERTS, WORK, APPROVALS, CONTACT)
BY_PATH = {entry.path: entry for entry in PAGES}


def page(path: str) -> ConsolePage:
    return BY_PATH[path]


def navigation_sections() -> dict[str, list[st.Page]]:
    """The console tree for st.navigation: sections with their pages."""
    built: dict[str, list[st.Page]] = {}
    for entry in PAGES:
        args: dict[str, Any] = {"title": entry.title, "icon": entry.material_icon, "default": entry.default}
        if entry.url_path:
            args["url_path"] = entry.url_path
        built.setdefault(entry.section, []).append(st.Page(entry.path, **args))
    return built


def page_link(path: str, label: str | None = None, **kwargs: Any):
    """A console page link with the page's title and material icon by default."""
    entry = page(path)
    st.page_link(entry.path, label=label or entry.title, icon=entry.material_icon, **kwargs)
