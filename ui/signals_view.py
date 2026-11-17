"""The Overview's "Signals heard today" section: for each satellite, the signals an IGS receiver recorded from it.

The numbers come from scripts/signals_heard.py (published to the orbit-checks branch, read by ui/data.py); the
names of the signals and the stations are in ui/signal_settings.py.
"""
from html import escape

from ui import data as dashboard_data
from ui import reveal, surfaces, tooltip
from ui.orbit_age import _day_words
from ui.signal_settings import STATIONS

MEANING = ("A signal counts as heard when at least one station's receiver recorded a code range or carrier phase for it "
           "from that satellite during the day. It says the satellite was sending that signal, not how good it was.")


def _chips(row, stations_read):
    """The cell of one satellite: a chip per signal heard, or why there is none."""
    if row is None:
        return surfaces.chip("not in the signals check", "idle")
    if not row.get("signal_id"):
        return surfaces.chip("no signal ID today", "idle")
    signals = row.get("signals") or {}
    if not signals:
        return surfaces.chip(f"not heard by any of the {stations_read} stations today", "warn")
    return "".join(surfaces.chip(signal, "accent") for signal in signals)


def _stations(row):
    heard = sorted({station for names in ((row or {}).get("signals") or {}).values() for station in names})
    return escape(", ".join(heard)) if heard else "&ndash;"


def _how(payload, read):
    """The one line that says how it was measured, with the data linked."""
    names = "<br>".join(f"<b>{escape(s['name'])}</b>, {escape(s['place'])}: {escape(STATIONS[s['code']][2])}"
                        for s in payload.get("stations", []) if s.get("read") and s.get("code") in STATIONS)
    stations = tooltip.tip_html(f"{read} IGS stations", names)
    folder = payload.get("folder")
    files = (f'<a href="{escape(folder, quote=True)}" target="_blank" rel="noopener">the day\'s files</a>'
             if isinstance(folder, str) and folder.startswith("https://") else "the day's files")
    every = payload.get("sample_every")
    sampled = f", one reading in {every} (every {every * 30 // 60} minutes)" if isinstance(every, int) and every > 1 else ""
    return (f'<p class="small">Measured from {stations}\' 30-second observation files for {escape(_day_words(payload.get("day")) or "the day")} '
            f'(BKG\'s IGS data centre: {files}){sampled}. Result: <a href="{escape(dashboard_data.SIGNALS_URL, quote=True)}" '
            f'target="_blank" rel="noopener">signals_heard.json</a>. {escape(MEANING)}</p>'
            f'<p class="small">Not heard is not the same as not sent: a receiver may not track a signal (none of these '
            f'stations records NavIC\'s S band, for one), or the satellite may have been out of view of all of them.</p>')


def section_markup(payload, names):
    """(summary, body html) for the satellites called `names`, in that order, from the published payload."""
    by_name = {row["satellite"]: row for row in payload.get("satellites", []) if isinstance(row, dict) and "satellite" in row}
    read = sum(bool(s.get("read")) for s in payload.get("stations", []))
    heard = sum(bool((by_name.get(name) or {}).get("signals")) for name in names)
    silent = sum(1 for name in names if name in by_name and by_name[name].get("signal_id") and not by_name[name].get("signals"))
    summary = f"{heard} of {len(names)} satellites heard · {silent} not heard by any of {read} stations · {_day_words(payload.get('day')) or 'day not known'}"
    head = f"<th>Satellite</th><th>{tooltip.tip('Signals heard', MEANING)}</th><th>Heard by</th>"
    lines = "".join(
        f'<tr><th scope="row">{escape(name)} <span class="muted">{escape((by_name.get(name) or {}).get("signal_id") or "")}</span></th>'
        f'<td><div class="sig-chips">{_chips(by_name.get(name), read)}</div></td><td>{_stations(by_name.get(name))}</td></tr>'
        for name in names)
    table = f'<div class="tablewrap"><table class="grid"><thead><tr>{head}</tr></thead><tbody>{lines}</tbody></table></div>'
    return summary, _how(payload, read) + table


def show(constellation):
    """The section for one constellation, open; a notice instead when the published file cannot be read."""
    payload = dashboard_data.signals_heard()
    if not payload.get("satellites"):
        surfaces.show(surfaces.notice("Signals heard: the daily result is not available right now.", "idle"))
        return
    summary, body = section_markup(payload, list(dashboard_data.SATELLITES[constellation]))
    reveal.section(f"signals_{constellation}", "Signals heard today", summary, body, open=True)
