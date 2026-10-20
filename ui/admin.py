"""The admin page's parts: the count waiting, one card per item, and a pull request's text as plain reading.

Items come from evidence/decisions.py. Every builder returns an HTML string; all text is escaped, since titles and
pull request text come from outside (the weekly job copies lines from the IGS file into its pull request).
"""
import re
from html import escape

from evidence.decision_settings import WAIT_WARN_DAYS
from evidence.decisions import waited
from ui import reveal, surfaces

CSS = """<style>
.dc { display: grid; gap: 10px; margin: 0 0 14px; }
.dc .dc-top { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.dc .dc-title { font-size: 18px; font-weight: 650; color: var(--ink); overflow-wrap: anywhere; }
.dc .wait { display: block; height: 6px; border-radius: 999px; background: var(--well); box-shadow: var(--pressed); }
.dc .wait i { display: block; height: 100%; border-radius: 999px; background: var(--ok); opacity: .75; }
.dc .wait.warn i { background: var(--warn); }
.dc a, .pr-text a { color: var(--accent); overflow-wrap: anywhere; }
.pr-text { font-size: 14px; color: var(--ink); overflow-wrap: anywhere; }
.pr-text h4 { font-size: 15px; margin: 14px 0 6px; } .pr-text h4:first-child { margin-top: 0; }
.pr-text p, .pr-text ul { margin: 6px 0; } .pr-text li { margin: 3px 0; }
.pr-text pre { white-space: pre-wrap; font-size: 13px; background: var(--well); border-radius: 12px; padding: 8px 12px; }
.admin-head { display: flex; flex-wrap: wrap; gap: 10px 24px; align-items: center; margin-bottom: 8px; }
.admin-head .r { display: flex; flex-wrap: wrap; gap: 8px; }
</style>"""

NOT_SET_UP = ("The admin page is not set up on this computer. It needs Google sign-in, the list of people who may "
              "sign in, and a GitHub token, all in .streamlit/secrets.toml (see .streamlit/secrets.example.toml).")
INTRO = ("Decisions waiting for the team, in plain words. Each one is a pull request in the project's private "
         "copy, and the pull request stays the only record. Sign in with the Google account on the team's list.")

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def _inline(text):
    """One line: escaped, then **bold** and [words](http link) put back."""
    text = _BOLD.sub(r"<b>\1</b>", escape(text))
    return _LINK.sub(r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', text)


def text_html(markdown):
    """A pull request's text as reading: headings, bullet lists, bold, links and indented lines. Nothing else in it is
    read as markup."""
    out, bullets = [], []

    def end_list():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    for line in markdown.splitlines():
        plain = line.strip()
        if plain.startswith(("- ", "* ")):
            bullets.append(_inline(plain[2:]))
            continue
        end_list()
        if not plain:
            continue
        if plain.startswith("#"):
            out.append(f"<h4>{_inline(plain.lstrip('#').strip())}</h4>")
        elif line.startswith(("    ", "\t")):
            out.append(f"<pre>{escape(plain)}</pre>")
        else:
            out.append(f"<p>{_inline(plain)}</p>")
    end_list()
    return f'<div class="pr-text">{"".join(out)}</div>'


def headline(items, groups):
    """How many items wait, then how many in each group."""
    late = sum(waited(i["waited_days"])[1] == "warn" for i in items)
    chips = "".join(surfaces.chip(f"{group}: {len(its)}", "accent") for group, its in groups)
    if late:
        chips += surfaces.chip(f"{late} past a fortnightly call", "warn")
    return (f'<div class="admin-head">{surfaces.big_number(len(items), "waiting for a decision")}'
            f'<div class="r">{chips}</div></div>')


def card(item):
    """One item: its kind, how long it has waited (in words and as a bar filling over a fortnight), what is asked,
    the summary from the top of the pull request, and who raised it."""
    words, status = waited(item["waited_days"])
    share = min(100.0, 100 * item["waited_days"] / WAIT_WARN_DAYS)
    opened = item["opened"]
    return (f'<div class="raised dc"><div class="dc-top">{surfaces.chip(item["kind"], "accent")}'
            f'{surfaces.chip(words, status)}</div>'
            f'<span class="wait {status}" role="img" aria-label="{escape(words, quote=True)}">'
            f'<i style="width:{share:.0f}%"></i></span>'
            f'<div class="dc-title">{escape(item["title"])}</div>'
            + (text_html(item["summary"]) if item["summary"] else "")
            + f'<div class="small">Raised by {escape(item["raised_by"])} on {opened.day} {opened:%b %Y}. '
              f'<a href="{escape(item["link"], quote=True)}" target="_blank" rel="noopener noreferrer">'
              f'Pull request {item["number"]} on GitHub</a></div></div>')


def group_line(its):
    """The plain line under a group's name."""
    return reveal.count(len(its), "item") + ", the longest waiting first"
