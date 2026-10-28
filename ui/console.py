"""The administration console's look and parts: two colour schemes, icons, and builders that return HTML.

Light is "Classic bold" (Windows 2000 and Server 2003 classic: navy bands, grey bevelled buttons); dark is
"Operations dark" (near-black, with bright blue, green, amber and red). "Auto" follows the computer's own setting
(decided 20 Oct 2026, issue 17). Text passed in is escaped; only parameters whose names end in _html are markup.
"""
import base64
import functools
from html import escape
from pathlib import Path

CSS_FILE = Path(__file__).with_name("console.css")
SCHEMES = {"auto": "Auto", "light": "Light", "dark": "Dark"}
TONES = ("ok", "warn", "bad", "info", "idle")

FONT = '"Segoe UI", Tahoma, "Helvetica Neue", Arial, sans-serif'
_COMMON = {"font": FONT, "mono": 'Consolas, "SF Mono", Menlo, monospace'}
LIGHT = {  # Classic bold
    "ink": "#000", "muted": "#4a4a4a", "link": "#0645ad", "frame": "#000", "edge": "#808080", "edge-soft": "#e3e1d8",
    "outline": "#000", "hard": "4px 4px 0 #000", "hard-sm": "2px 2px 0 #000",
    "title-bg": "linear-gradient(90deg, #0a246a, #3a6ea5 65%, #a6caf0)",
    "title-ink": "#fff", "title-edge": "2px solid #000", "chrome": "#d4d0c8", "chrome-ink": "#000", "chrome-edge": "#808080",
    "status-bg": "#d4d0c8", "status-ink": "#000", "tree-bg": "#fff", "tree-ink": "#000", "tree-line": "#808080", "pane": "#fff", "pane-alt": "#f1efe2",
    "head-bg": "#0a246a", "head-ink": "#fff", "vhead-bg": "linear-gradient(90deg, #0a246a, #2b5797)", "vhead-ink": "#fff",
    "vhead-sub": "#dce6f7", "th-bg": "#d4d0c8", "th-ink": "#000", "th-bevel": "inset -1px -1px #808080, inset 1px 1px #fff",
    "row-alt": "#f7f6f1", "hover": "#e5ecf7", "select": "#0a246a", "select-ink": "#fff", "select-edge": "#0a246a",
    "btn-bg": "#d4d0c8", "btn-hover": "#ece9e2", "btn-ink": "#000", "btn-edge": "#000",
    "btn-bevel": "inset -1px -1px #404040, inset 1px 1px #fff, inset -2px -2px #808080, inset 2px 2px #dfdfdf",
    "btn-bevel-pressed": "inset 1px 1px #808080, inset -1px -1px #fff", "btn-def-bg": "#0a246a", "btn-def-ink": "#fff",
    "input-bg": "#fff", "input-edge": "#7a7a7a",
    "well-bevel": "inset 1px 1px #808080, inset -1px -1px #fff", "big": "#0a246a",
    "ok": "#007a1f", "warn": "#a15c00", "bad": "#c00000", "info": "#0a246a", "idle": "#5f5f5f",
    "c-ok": "#00a03c", "c-bad": "#e81123", "c-warn": "#ff8c00", "c-info": "#0063b1", "c-c": "#f2c80f", "c-idle": "#a8a8a8",
    "axis": "#606060", "cell-off-bg": "#eeeeee", "tile-bg": "#fff", "badge-ink": "#fff",
    # Chart roles, validated with the dataviz skill's validate_palette.js (20 Oct 2026): normal runs in a quiet grey,
    # failures in red (they separate for red-green colour blindness; green against red does not), and the source
    # grades as one ordered blue ramp, A darkest, every step clear of the surface.
    "c-quiet": "#858585", "g-a": "#1c5cab", "g-b": "#2a78d6", "g-c": "#5598e7", "g-d": "#86b6ef", "g-none": "#c9c9c9",
}
DARK = {  # Operations dark
    "ink": "#e6edf3", "muted": "#9aa7b4", "link": "#4cc2ff", "frame": "#2f81f7", "edge": "#30363d", "edge-soft": "#1c2128",
    "outline": "#c9d1d9", "hard": "4px 4px 0 #6e7681", "hard-sm": "2px 2px 0 #6e7681",
    "title-bg": "#0d1117", "title-ink": "#e6edf3",
    "title-edge": "2px solid #2f81f7", "chrome": "#161b22", "chrome-ink": "#e6edf3", "chrome-edge": "#30363d",
    "status-bg": "#1f6feb", "status-ink": "#fff", "tree-bg": "#0d1117", "tree-ink": "#e6edf3", "tree-line": "#6e7681", "pane": "#0d1117", "pane-alt": "#11161d",
    "head-bg": "#1f6feb", "head-ink": "#fff", "vhead-bg": "#161b22", "vhead-ink": "#58a6ff", "vhead-sub": "#9aa7b4",
    "th-bg": "#161b22", "th-ink": "#c9d1d9", "th-bevel": "inset -1px -1px #010409, inset 1px 1px #8b949e",
    "row-alt": "#10151c", "hover": "#1c2633",
    "select": "#1f4f8f", "select-ink": "#fff", "select-edge": "#2f81f7", "btn-bg": "#21262d", "btn-hover": "#3a4553", "btn-ink": "#e6edf3",
    "btn-edge": "#3d444d",
    "btn-bevel": "inset -1px -1px #010409, inset 1px 1px #8b949e, inset -2px -2px #000, inset 2px 2px #6e7681",
    "btn-bevel-pressed": "inset 1px 1px #010409, inset -1px -1px #6e7681",
    "btn-def-bg": "#238636", "btn-def-ink": "#fff", "input-bg": "#0d1117",
    "input-edge": "#3d444d", "well-bevel": "inset 1px 1px #010409, inset -1px -1px #6e7681", "big": "#e6edf3",
    "ok": "#3fb950", "warn": "#e3b341", "bad": "#ff7b72", "info": "#58a6ff", "idle": "#8b949e",
    "c-ok": "#3fb950", "c-bad": "#f85149", "c-warn": "#db6d28", "c-info": "#2f81f7", "c-c": "#d29922", "c-idle": "#484f58",
    "axis": "#6e7681", "cell-off-bg": "#161b22", "tile-bg": "#11161d", "badge-ink": "#fff",
    "c-quiet": "#6e7681", "g-a": "#9ec5f4", "g-b": "#6da7ec", "g-c": "#3987e5", "g-d": "#256abf", "g-none": "#30363d",
}

# Each icon's drawing, 16 by 16. st.html drops <svg> elements, so icon() hands each one over as an image.
ICONS = {
    "ok": '<circle cx="8" cy="8" r="7" fill="#2e8b3a"/><path d="M4.5 8.2l2.3 2.3 4.7-5" fill="none" stroke="#fff" stroke-width="1.8"/>',
    "warn": '<path d="M8 1.2L15.2 14H.8z" fill="#f3b32a" stroke="#9a6a00"/><rect x="7.2" y="5.5" width="1.6" height="4.6" fill="#3d2a00"/><rect x="7.2" y="11.2" width="1.6" height="1.6" fill="#3d2a00"/>',
    "bad": '<circle cx="8" cy="8" r="7" fill="#c62828"/><path d="M5 5l6 6M11 5l-6 6" stroke="#fff" stroke-width="1.8"/>',
    "info": '<circle cx="8" cy="8" r="7" fill="#2a6fc9"/><rect x="7.2" y="7" width="1.6" height="5" fill="#fff"/><rect x="7.2" y="4" width="1.6" height="1.6" fill="#fff"/>',
    "idle": '<circle cx="8" cy="8" r="7" fill="#8a929c"/><rect x="4" y="7.1" width="8" height="1.8" fill="#fff"/>',
    "sat": '<rect x="6" y="6" width="4" height="4" fill="#9aa7b8" stroke="#46566b"/><rect x="1" y="6.5" width="4" height="3" fill="#5b8fd6" stroke="#2c4f86"/><rect x="11" y="6.5" width="4" height="3" fill="#5b8fd6" stroke="#2c4f86"/>',
    "summary": '<rect x="1" y="2" width="14" height="10" fill="#e3edf9" stroke="#4a6fa5"/><rect x="3" y="4" width="10" height="6" fill="#9cc3ec"/><rect x="6" y="12" width="4" height="2" fill="#4a6fa5"/>',
    "jobs": '<circle cx="8" cy="8" r="6.5" fill="#fff" stroke="#6a7f9a"/><path d="M8 4v4.5l3 1.5" fill="none" stroke="#1d3c66" stroke-width="1.5"/>',
    "approvals": '<path d="M3 1h7l3 3v11H3z" fill="#fff" stroke="#5f7da6"/><path d="M5.5 9l2 2 3.5-4" fill="none" stroke="#217a2b" stroke-width="1.6"/>',
    "sources": '<circle cx="8" cy="8" r="6.5" fill="#d8ecff" stroke="#3a6db0"/><path d="M1.5 8h13M8 1.5c-2.5 2.5-2.5 10.5 0 13M8 1.5c2.5 2.5 2.5 10.5 0 13" fill="none" stroke="#3a6db0"/>',
    "design": '<rect x="1" y="2" width="5" height="4" fill="#fff" stroke="#3a6db0"/><rect x="10" y="2" width="5" height="4" fill="#fff" stroke="#3a6db0"/><rect x="5.5" y="10" width="5" height="4" fill="#dff1e1" stroke="#217a2b"/><path d="M6 4h4M3.5 6v2h9V6M8 8v2" fill="none" stroke="#3a6db0"/>',
    "work": '<rect x="2" y="1.5" width="12" height="13" fill="#fff" stroke="#5f7da6"/><path d="M4.5 5h7M4.5 8h7M4.5 11h4.5" stroke="#1d3c66" stroke-width="1.4"/>',
    "pipeline": '<rect x="1.5" y="4.5" width="4" height="7" fill="#fff" stroke="#3a6db0"/><rect x="6.5" y="2.5" width="4" height="11" fill="#dff1e1" stroke="#217a2b"/><rect x="11.5" y="5.5" width="3" height="5" fill="#fff" stroke="#3a6db0"/><path d="M5.7 8h.6M10.7 8h.6" stroke="#1d3c66" stroke-width="1.2"/>',
    "alerts": '<path d="M8 1.8a4.2 4.2 0 0 0-4.2 4.2v2.2l-1.5 2.5h11.4l-1.5-2.5V6A4.2 4.2 0 0 0 8 1.8z" fill="#fff" stroke="#3a6db0"/><circle cx="8" cy="12.8" r="1.2" fill="#f3b32a" stroke="#9a6a00"/>'
}


_SIGNIN_JPEG = Path(__file__).with_name("assets") / "signin-gps-satellite.jpg"


@functools.lru_cache(maxsize=1)
def _signin_photo_data_uri():
    """The sign-in satellite photo as a data URI (read once; Streamlit static serving is off)."""
    encoded = base64.b64encode(_SIGNIN_JPEG.read_bytes()).decode()
    return f"data:image/jpeg;base64,{encoded}"


def signin_card(words):
    """Centred sign-in card: framed NASA GPS photo, caption, and message (`words` already escaped)."""
    photo = _signin_photo_data_uri()
    caption = "Artist's conception of a GPS Block II-F satellite. NASA, public domain."
    return (
        f'<div class="c-signin">'
        f'<div class="c-signin-photo"><div class="bar">GPS Block II-F</div>'
        f'<img src="{photo}" alt="" width="440" height="352"></div>'
        f'<p class="c-signin-cap">{escape(caption)}</p>'
        f'<div class="in"><p class="c-signin-words">{words}</p></div></div>'
    )


def _block(tokens):
    return ":root {" + "".join(f"--{name}: {value};" for name, value in {**_COMMON, **tokens}.items()) + "}"


def token_css(scheme):
    """The colour tokens for a scheme: 'light', 'dark', or 'auto', which follows the computer's setting."""
    return {"light": _block(LIGHT), "dark": _block(DARK)}.get(
        scheme, _block(LIGHT) + "@media (prefers-color-scheme: dark) {" + _block(DARK) + "}")


def theme_css(scheme):
    """The console's stylesheet for a scheme."""
    return f"<style>{token_css(scheme)}{CSS_FILE.read_text(encoding='utf-8')}</style>"


def _tone(tone):
    if tone not in TONES:
        raise ValueError(f"unknown tone {tone!r}; use one of {', '.join(TONES)}")
    return tone


def icon(name, size=16):
    """An icon; words beside it always say what it means, so it has no alt text."""
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="{size}" height="{size}">{ICONS[name]}</svg>'
    return (f'<img class="ic" alt="" width="{size}" height="{size}" '
            f'src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}">')


def status(tone, words):
    """A status in words, with its icon and colour; the words always carry it."""
    return f'<span class="c-status {_tone(tone)}">{icon(tone)}{escape(words)}</span>'


def current_page_css(url_path):
    """Selects the current page in the console tree. Streamlit 1.45 marks it only with a generated class name, so the
    link is found by its address instead: the default page's ends in '/', the others in '/<url_path>'."""
    link = f'[data-testid="stSidebarNavLink"][href$="/{escape(url_path, quote=True)}"]'
    return (f"<style>:is({link}, {link}:hover) {{ background: var(--select); border-color: var(--select-edge); }}"
            f"{link} * {{ color: var(--select-ink) !important; font-weight: 700; }}</style>")


def title_bar(page_title):
    return (f'<div class="c-title">{icon("sat")}<b>GNSS Health Monitor</b><span class="sep">-</span>'
            f'<span>Administration Console</span><span class="sep">-</span><span>{escape(page_title)}</span></div>')


def view_head(icon_name, title, line):
    return f'<div class="c-view">{icon(icon_name, 32)}<div><h2>{escape(title)}</h2><p>{escape(line)}</p></div></div>'


def section(title, body_html, right="", flush=False):
    """A band with the title (and a note on the right), then the body."""
    note = f"<span>{escape(right)}</span>" if right else ""
    return f'<div class="c-sect"><h3>{escape(title)}{note}</h3><div class="in{" flush" if flush else ""}">{body_html}</div></div>'


def attention(items):
    """What needs a look: (tone, title, detail, page) items, each with a coloured edge and its icon."""
    rows = "".join(f'<li class="{_tone(tone)}">{icon(tone)}<div><b>{escape(title)}</b><div>{escape(detail)}</div></div></li>'
                   for tone, title, detail, _ in items)
    return f'<ul class="c-attn">{rows}</ul>'


def day_columns(days, labels):
    """A small column per day, as plain blocks so they follow light and dark: the day's runs as height, failures in red
    above the quiet grey successes, a day with no run a short tick. Each column says its day on hover."""
    top = max((sum(day) for day in days if day), default=1) or 1
    columns = ""
    for label, day in zip(labels, days):
        if not day:
            columns += f'<span class="none" title="{escape(label, quote=True)}: did not run"></span>'
            continue
        ok, failed = day
        words = escape(f"{label}: {ok} succeeded" + (f", {failed} failed" if failed else ""), quote=True)
        columns += (f'<span title="{words}" style="height:{100 * (ok + failed) / top:.0f}%">'
                    + (f'<i class="bad" style="flex:{failed}"></i>' if failed else "")
                    + (f'<i class="ok" style="flex:{ok}"></i>' if ok else "") + "</span>")
    failures = [f"{label} {day[1]}" for label, day in zip(labels, days) if day and day[1]]
    succeeded = sum(day[0] for day in days if day)
    alt = (f"Runs per day over {len(days)} days: {succeeded} succeeded; "
           + (f"failed: {', '.join(failures)}" if failures else "none failed"))
    return f'<div class="c-trend" role="img" aria-label="{escape(alt, quote=True)}">{columns}</div>'


def stack(parts, label):
    """A bar in parts with a 2px gap between them, then its legend: parts are (count, colour token, words). Each part
    says its count on hover; the legend says them all."""
    total = sum(count for count, _, _ in parts) or 1
    bars = "".join(f'<i style="flex:{count / total:.4f} 1 0;background:var(--{token})" title="{escape(words, quote=True)}: {count}"></i>'
                   for count, token, words in parts if count)
    legend = "".join(f'<span><b style="background:var(--{token})"></b>{escape(words)} {count}</span>' for count, token, words in parts)
    return f'<div class="c-stack" role="img" aria-label="{escape(label, quote=True)}">{bars}</div><div class="c-legend">{legend}</div>'


def tile(tone, title, status_html, big, sub, extra_html=""):
    """One stat tile: a top edge in the status colour, the label and its status in words, the value in ink, a line
    under it, and a picture (a trend, a meter or a bar in parts)."""
    return (f'<div class="c-tile {_tone(tone)}"><h4>{escape(title)}{status_html}</h4><div class="big">{escape(big)}</div>'
            f'<div class="sub">{escape(sub)}</div>{extra_html}</div>')


def hero(value, words, tone):
    """The one figure a page leads with."""
    return f'<div class="c-hero {_tone(tone)}"><span class="v">{escape(str(value))}</span><span class="w">{escape(words)}</span></div>'


def meter(share, tone, label):
    """A track filled to `share` (0 to 1) in the status colour, the rest a lighter track."""
    filled = max(0.0, min(1.0, share))
    return (f'<div class="c-meter" role="img" aria-label="{escape(label, quote=True)}" title="{escape(label, quote=True)}">'
            f'<i class="{_tone(tone)}" style="width:{100 * filled:.1f}%"></i></div>')


def tiles(tile_htmls):
    return f'<div class="c-tiles">{"".join(tile_htmls)}</div>'


def list_view(columns, rows_html, numeric=()):
    """A list view: headings, then rows of cells that are already markup. `numeric` names columns set to the right."""
    head = "".join(f'<th scope="col">{escape(c)}</th>' for c in columns)
    body = "".join("<tr>" + "".join(f'<td{" class=num" if columns[i] in numeric else ""}>{cell}</td>'
                                    for i, cell in enumerate(row)) + "</tr>" for row in rows_html)
    return f'<div class="c-lv-wrap"><table class="c-lv"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def key_values(pairs_html):
    """A property sheet: (label, value markup) pairs."""
    return '<dl class="c-kv">' + "".join(f"<dt>{escape(k)}</dt><dd>{v}</dd>" for k, v in pairs_html) + "</dl>"


def reliability_grid(grid, names):
    """Days across, scheduled jobs down: a tick when every run that day succeeded, the failures counted, a dash for none."""
    head = '<th class="name" scope="col">Job</th>' + "".join(
        f'<th scope="col"{" class=today" if i == len(grid["days"]) - 1 else ""}>{escape(d)}</th>' for i, d in enumerate(grid["days"]))
    body = ""
    for workflow, days in grid["rows"].items():
        cells = ""
        for i, day in enumerate(days):
            today = " today" if i == len(days) - 1 else ""
            when = escape(grid["days"][i])
            if day is None:
                cells += f'<td class="{today.strip()}"><span class="m none" title="{when}: did not run">–</span></td>'
            elif day[1]:
                cells += (f'<td class="{today.strip()}"><span class="m bad" title="{when}: {day[1]} failed, {day[0]} succeeded">'
                          f'✕{day[1] if day[1] > 1 else ""}</span></td>')
            else:
                cells += f'<td class="{today.strip()}"><span class="m ok" title="{when}: {day[0]} succeeded">✓</span></td>'
        body += f'<tr><td class="name">{escape(names.get(workflow, workflow))}</td>{cells}</tr>'
    return f'<div class="c-rel"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def notice(text, tone):
    return f'<div class="c-notice {_tone(tone)}" role="status">{escape(text)}</div>'


def pipeline_diagram(stages, next_stage_name=None, next_at=None):
    """The pipeline as connected stage boxes, with each stage's state in words and colour."""
    tones = {"running now": "info", "done": "ok", "failed": "bad", "waiting": "warn", "off": "idle"}
    by_name = {stage["name"]: stage for stage in stages}
    archive_names = [stage["name"] for stage in stages if stage["name"].startswith("Archive: ")]
    chain_names = ["Archive", "Registry update", "Pull request waiting for a decision", "Decided on the Approvals page",
                   "Merged to main", "Dashboard"]

    def box(stage, order=None):
        tone = tones.get(stage["state"], "idle")
        badge = ""
        if next_stage_name and stage["name"] == next_stage_name and next_at:
            badge = f'<span class="next">{escape(f"Next {when(next_at)} UTC")}</span>'
        order_badge = f'<span class="order" aria-hidden="true">{order}</span>' if order is not None else ""
        running = " running" if stage["state"] == "running now" else ""
        return (f'<div class="c-pipe-stage {tone}{running}"><h4>{order_badge}{escape(stage["name"])}{badge}</h4>'
                f'<p>{status(tone, stage["state"])}</p></div>')

    archives = "".join(box(by_name[name]) for name in archive_names if name in by_name)
    chain_rows = [name for name in chain_names if name in by_name]
    chain = [box(by_name[name], order=index + 1) for index, name in enumerate(chain_rows)]
    return ('<div class="c-pipe">'
            f'<div class="c-pipe-archives">{archives}</div>'
            '<div class="c-pipe-arrow c-pipe-join" aria-hidden="true">→</div>'
            f'<div class="c-pipe-chain">{"".join(chain)}</div>'
            "</div>")


def status_bar(parts_html, right):
    """The bar along the bottom: a few states on the left, when it was read on the right."""
    return '<div class="c-statusbar">' + "".join(f"<span>{p}</span>" for p in parts_html) + f"<span>{escape(right)}</span></div>"


def when(moment):
    """'20 Oct 12:15' in UTC, or a dash."""
    return f"{moment.day} {moment:%b %H:%M}" if moment else "–"
