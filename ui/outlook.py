"""The look ahead drawn, not written: what ui/next_step.py works out, as pictures for the pages.

- outlook(): a constellation's east-west station-keeping outlook. Figures first (manoeuvres due, the soonest deadband
  edge, slots to confirm), then one track per satellite from today: the drift towards the deadband edge, the ideal
  manoeuvre window, the last chance and the edge itself. The numbers are in the shared tooltip on each row.
- figures(): the figures alone, for a constellation card on Home.
- planes(): a medium-orbit constellation's planes, each one's RAAN offset against its limit and the years to reach it.
- fuel(): Δv per year, the years left as a band, and north-south inclination against its target, per satellite.
"""
from html import escape

import pandas as pd

from ui import next_step, tooltip
from ui import next_step_settings as N

TONE = {"ok": "ok", "accent": "accent", "warn": "warn", "idle": "idle"}


def _at(days, horizon):
    return f"{100 * min(max(days, 0), horizon) / horizon:.1f}%"


def _as_of(text):
    return f'<span class="ol-asof">{escape(text)} · {escape(next_step.CAVEAT)}</span>' if text else ""


def _figure(value, label, tone="idle"):
    return f'<div class="ol-fig {tone}"><b class="num">{escape(str(value))}</b><span>{escape(label)}</span></div>'


def _summary(forecasts, now):
    """(due, soonest, confirm): satellites whose last chance falls within NEAR_DAYS, the soonest deadband edge as
    (days, name), the satellites whose slot is to confirm."""
    worked = [f for f in forecasts if f["status"] in ("ok", "weak") and not f["confirm"]]
    due = [f for f in worked if f["status"] == "ok" and (d := next_step._row_days(f, "last_chance", now)) is not None
           and d <= N.NEAR_DAYS]
    edges = sorted((e, f["name"]) for f in worked if (e := next_step._edge_days(f, now)) is not None)
    return due, (edges[0] if edges else None), [f["name"] for f in forecasts if f.get("confirm")]


def figures(forecasts, now):
    """The three figures, for a card: manoeuvres due, the soonest deadband edge, slots to confirm ('' with nothing worked out)."""
    forecasts = [f for f in forecasts if f["status"] in ("ok", "weak")]
    if not forecasts:
        return ""
    due, soonest, confirm = _summary(forecasts, now)
    out = [_figure(len(due), f"E-W manoeuvres due ≤ {N.NEAR_DAYS} d", "warn" if due else "ok")]
    if soonest:
        out.append(_figure(f"{soonest[0]} d", f"to deadband edge · {soonest[1]}",
                           "warn" if soonest[0] <= N.SOON_DAYS else "accent" if soonest[0] <= N.NEAR_DAYS else "ok"))
    if confirm:
        out.append(_figure(len(confirm), "slot to confirm", "idle"))
    return '<div class="ol-figs">' + "".join(out) + "</div>"


def _card(f, now):
    """The row's tooltip: every number behind the track."""
    items = []
    if f["status"] == "ok":
        for kind, words in (("ideal", "Ideal manoeuvre"), ("last_chance", "Last chance")):
            row = f["rows"][kind]
            if row["delta_lambda_dot_deg_per_day"] is None:
                items.append(("", words, "none due on this drift"))
            elif kind == "last_chance" and f["confirm"]:
                items.append(("", words, "slot to confirm"))
            else:
                when = next_step._range(row["date"], now) if kind == "ideal" else next_step._day(row["date"])
                items.append(("", words, f"{when} · Δa {row['delta_a_km']:+.1f} km · Δv {row['delta_v_m_s']:.2f} m/s"))
    edge = next_step._edge_days(f, now)
    items.append(("", "Deadband edge", f"in {edge} d, uncorrected" if edge is not None else "not reached on this drift"))
    items.append(("", "Longitude", f"{f['pos']:+.2f}° from {'its station' if f['confirm'] else 'its slot'}, "
                                   f"deadband ±{f['box']:g}°"))
    note = next_step._confirm_words(f) or ("" if f["own_known"] else
                                           f"Own deadband not yet known from its manoeuvres: {N.OWN_BOX_FALLBACK_SHARE:g} of ours assumed.")
    return tooltip.glance(f["name"], items, note)


def _row(f, now, horizon):
    edge = next_step._edge_days(f, now)
    marks = []
    if edge is not None and edge <= horizon:
        marks.append(f'<i class="ol-drift" style="width:{_at(edge, horizon)}"></i>')
        marks.append(f'<u class="ol-edge" style="left:{_at(edge, horizon)}" title="deadband edge"></u>')
    else:
        marks.append('<i class="ol-drift far" style="width:100%"></i>')
    if f["status"] == "ok":
        ideal = f["rows"]["ideal"]
        if ideal["delta_lambda_dot_deg_per_day"] is not None:
            centre = next_step._in_days(ideal["date"], now)
            spread = max(N.DATE_SPREAD_MIN_DAYS, round(N.DATE_SPREAD_SHARE * centre))
            if centre - spread <= horizon:
                marks.append(f'<em class="ol-ideal" style="left:{_at(centre - spread, horizon)};'
                             f'width:{_at(2 * spread + 0.6, horizon)}"></em>')
        last = next_step._row_days(f, "last_chance", now)
        if last is not None and not f["confirm"] and last <= horizon:
            marks.append(f'<s class="ol-last" style="left:{_at(last, horizon)}"></s>')
    tone = ("idle" if f["confirm"] else "warn" if edge is not None and edge <= N.SOON_DAYS
            else "accent" if edge is not None and edge <= N.NEAR_DAYS else "ok")
    value = ("slot to confirm" if f["confirm"] else f"{edge} d" if edge is not None and edge <= horizon
             else f"> {horizon} d")
    name = tooltip.tip_html(escape(f["name"]), _card(f, now), key=f"ol-{f['name']}")
    return (f'<div class="ol-row {tone}"><span class="ol-name">{name}</span>'
            f'<span class="ol-track">{"".join(marks)}</span><span class="ol-val">{escape(value)}</span></div>')


def outlook(forecasts, now, as_of="", horizon=None):
    """A constellation's east-west outlook: the figures, a day axis, one track per satellite (soonest edge first)."""
    horizon = horizon or 2 * N.NEAR_DAYS
    shown = [f for f in forecasts if f["status"] in ("ok", "weak")]
    if not shown:
        return ""
    order = sorted(shown, key=lambda f: (bool(f["confirm"]), next_step._edge_days(f, now) is None,
                                         next_step._edge_days(f, now) or 0))
    ticks = "".join(f'<span style="left:{_at(d, horizon)}">{"today" if d == 0 else f"{d} d"}</span>'
                    for d in range(0, horizon + 1, horizon // 4))
    key = tooltip.legend([("var(--accent)", "ideal manoeuvre window"), ("var(--warn)", "last chance"),
                          ("var(--bad)", "deadband edge, uncorrected", "diamond")], label="Key")
    return (f'<div class="ol"><b class="ol-title">East-west station-keeping · next {horizon} d</b>{figures(shown, now)}<div class="ol-head"><span class="ol-axis">{ticks}</span>{key}</div>'
            + "".join(_row(f, now, horizon) for f in order) + _as_of(as_of) + "</div>")


def planes(system, drift, as_of="", years_cap=N.MEO_YEARS_CAP, compact=False):
    """A medium-orbit constellation: one gauge per plane, its RAAN offset against its limit, and the years to reach it
    (compact: the figures alone, for a card)."""
    rows, firsts = [], []
    for plane, d in sorted((drift or {}).items()):
        limit, offset, rate = d["offset_limit"], d["offset"], d["rate"]
        moving_out = abs(rate) >= N.STEADY_DEG_PER_YEAR and (offset * rate > 0 or abs(offset) < 0.05)
        years = 0.0 if abs(offset) > limit else (limit - abs(offset)) / abs(rate) if moving_out else None
        if years is not None and years < years_cap:
            firsts.append((years, plane))
        tone = "warn" if years is not None and years < 1 else "accent" if years is not None and years < 5 else "ok"
        value = ("past limit" if years == 0.0 else "steady" if years is None or years >= years_cap
                 else f"≈ {years * 12:.0f} mo" if years < 1 else f"≈ {years:.0f} yr")
        arrow = "" if not moving_out else ("→" if offset >= 0 else "←")
        card = tooltip.glance(f"Plane {plane}", [("", "RAAN offset", f"{offset:+.2f}° of ±{limit:g}°"),
                                                  ("", "Rate", f"{rate:+.3f}° per year"),
                                                  ("", "Limit reached", value)])
        rows.append(f'<div class="ol-row {tone}"><span class="ol-name">{tooltip.tip_html(escape(f"Plane {plane}"), card, key=f"pl-{system}-{plane}")}</span>'
                    f'<span class="ol-gauge"><i style="left:{50 + 50 * max(-1, min(1, offset / limit)):.1f}%">{arrow}</i></span>'
                    f'<span class="ol-val">{escape(value)}</span></div>')
    if not rows:
        return ""
    first = min(firsts) if firsts else None
    figs = (_figure(len(rows) - sum(1 for y, _ in firsts if y == 0.0), f"of {len(rows)} planes within RAAN limit", "ok")
            + (_figure(f"plane {first[1]}", f"first to its limit · ≈ {first[0]:.0f} yr" if first[0] >= 1 else "first to its limit",
                       "accent" if first[0] >= 1 else "warn") if first else _figure("none", "plane moving to its limit", "ok")))
    if compact:
        return f'<div class="ol-figs">{figs}</div>'
    return (f'<div class="ol"><b class="ol-title">Orbital planes · RAAN offset against its limit</b><div class="ol-figs">{figs}</div>'
            '<div class="ol-head"><span class="ol-axis"><span style="left:0">−limit</span><span style="left:50%">0</span>'
            '<span style="left:100%">+limit</span></span></div>' + "".join(rows) + _as_of(f"as of {next_step._day(as_of)}" if as_of else "") + "</div>")


def fuel(forecasts, fuel_by_satellite, now):
    """One row per satellite: Δv a year as a bar, years left as a band (class-typical), north-south inclination
    against its target ± tolerance as a gauge."""
    names = [n for n, f in forecasts.items() if f.get("status") in ("ok", "weak") or fuel_by_satellite.get(n)]
    rates = [fuel_by_satellite[n]["rate"] for n in names if fuel_by_satellite.get(n)]
    if not names:
        return ""
    top = max(rates or [1.0])
    cap = N.YEARS_CAP
    rows = []
    for n in names:
        fl, f = fuel_by_satellite.get(n), forecasts[n]
        rate = (f'<span class="fu-bar"><i style="width:{100 * fl["rate"] / top:.1f}%"></i></span>'
                f'<span class="num">{fl["rate"]:.1f}</span>') if fl else '<span class="muted">–</span>'
        if fl and fl["years"]:
            low, high = (min(y, cap) for y in fl["years"])
            width = max(6, 100 * (high - low) / cap)   # at least a visible stub, ending at the scale's end when past it
            years = (f'<span class="fu-bar band"><em style="left:{min(100 * low / cap, 100 - width):.1f}%;width:{width:.1f}%"></em></span>'
                     f'<span class="num">{"&gt; " + str(cap) if low >= cap else f"{low:.0f}–{high:.0f}" if round(low) != round(high) else f"{low:.0f}"}</span>')
        else:
            years = '<span class="muted">–</span>'
        ns = f.get("ns")
        if ns:
            off = (f["inclination"] - f["target"]) / (2 * f["tolerance"])
            out = abs(f["inclination"] - f["target"]) > f["tolerance"]
            incl = (f'<span class="fu-gauge{" out" if out else ""}"><em></em><i style="left:{50 + 50 * max(-1, min(1, off)):.1f}%"></i></span>'
                    f'<span class="num">{f["inclination"]:.2f}°</span>')
            card = tooltip.glance(f"{n} · north-south", [
                ("", "Inclination", f"{f['inclination']:.2f}° against {f['target']:g}° ±{f['tolerance']:g}°"),
                ("", "Correction", f"Δv ≈ {ns['correction_delta_v_m_s']:.0f} m/s"),
                ("", "Delay cost", f"≈ {ns['delay_cost_m_s_per_day']:.2f} m/s per day")])
            incl = tooltip.tip_html(incl, card, key=f"ns-{n}")
        else:
            incl = '<span class="muted">–</span>'
        rows.append(f'<div class="fu-row"><b>{escape(n)}</b><span class="fu-cell">{rate}</span>'
                    f'<span class="fu-cell">{years}</span><span class="fu-cell">{incl}</span></div>')
    head = ('<div class="fu-row hd"><span></span><span>Δv per year, m/s</span><span>Years left at this rate</span>'
            '<span>Inclination vs target</span></div>')
    return (f'<div class="fu">{head}{"".join(rows)}'
            + (f'<span class="ol-asof">Years left: typical for this class; the operator\'s Δv budget is not public.</span>'
               if any(fl and not fl["from_budget"] for fl in fuel_by_satellite.values()) else "") + "</div>")
