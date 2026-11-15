"""The Home page: a row per system with the count its Overview shows, and the "Worth a look" rules. No network."""
import re

import pytest

from test_dashboard_shell import (celestrak_answers_with_nothing_new, htmls, run,  # noqa: F401 (fixtures)
                                  segmented_controls_rerun)
from test_meo_pages import celestrak_answers_with_two_galileo_satellites, scope  # noqa: F401 (a fixture)
from ui import data, findings, home_settings, palette, shell, system_summary

COUNT = re.compile(r"(\d+ of \d+)</span>")


@pytest.fixture(autouse=True)
def the_dashboard_opens_on_home(monkeypatch):
    monkeypatch.setattr(shell, "DEFAULT_PAGE", shell.HOME)


def rows_of(bodies):
    return [body for body in bodies if body.startswith('<div class="sys ')]


def rows(at):
    return rows_of(htmls(at))


def test_home_is_the_first_page_and_shows_a_row_per_system_in_the_top_bars_order():
    at = run()

    assert shell.PAGES[0][0] == shell.HOME
    assert [re.search(r"<b>([^<]+)</b>", row).group(1) for row in rows(at)] == list(shell.CONSTELLATIONS)
    assert set(home_settings.SYSTEMS) == set(shell.CONSTELLATIONS)
    for row in rows(at):   # each row that was read says who runs the system and where it serves
        who, where = home_settings.SYSTEMS[re.search(r"<b>([^<]+)</b>", row).group(1)]
        assert who and where and (f"{who} · {where}" in row or "Could not be read" in row)


def test_a_satellites_state_is_told_by_the_dots_shape_and_in_words_not_by_colour_alone():
    bodies = htmls(run())

    navic = next(row for row in rows_of(bodies) if "<b>NavIC</b>" in row)
    assert re.search(r'role="img" aria-label="\d+ healthy and in place, \d+ needs a look, 1 set aside"', navic)
    legend = next(body for body in bodies if "What a dot means" in body)
    for words in ("round: healthy and in place", "diamond: needs a look", "square: set aside", "ring: settling in"):
        assert words in legend


def test_a_system_with_no_satellites_draws_no_unnamed_picture(monkeypatch):
    monkeypatch.setattr(system_summary, "summary", lambda name, result, gap=None: {
        "name": name, "sats": [], "healthy": 0, "total": 0, "settling": [], "planes": {}, "in_file": None,
        "flagged_healthy": None, "checked": 0, "broadcast_day": None})

    counted = [row for row in rows(run()) if COUNT.search(row)]

    assert counted and not any('role="img"' in row for row in counted)


def test_each_rows_count_is_the_headline_of_that_systems_overview():
    home = {name: COUNT.search(row) for name, row in zip(shell.CONSTELLATIONS, rows(run()))}

    assert home["NavIC"] and home["Galileo"]   # one judged by slot and one by plane are compared
    for name in shell.CONSTELLATIONS:
        bodies = htmls(run(scope(name)))
        if home[name] is None:   # no orbit data in the test's copy: both pages say so
            assert any(f"No orbit data for {name} yet" in body for body in bodies), name
            continue
        headline = next(body for body in bodies if 'class="head"' in body)
        assert COUNT.search(headline).group(1) == home[name].group(1), name


def test_a_row_opens_that_systems_overview():
    index = shell.CONSTELLATIONS.index("Galileo")

    at = run(lambda at: at.button(key=f"home_open_{index}").click())

    assert at.session_state["scope"] == "Galileo" and at.session_state["page"] == "Overview"
    assert any("healthy and in step" in body for body in htmls(at))


def test_a_system_that_cannot_be_read_says_why_and_the_others_still_show(monkeypatch):
    load = data.load

    def flaky(name, *args, **kwargs):
        if name == "QZSS":
            raise ValueError("no orbit data for QZSS")
        return load(name, *args, **kwargs)
    monkeypatch.setattr(data, "load", flaky)

    at = run()

    said = [row for row in rows(at) if "<b>QZSS</b>" in row]
    assert len(said) == 1 and "Could not be read just now: no orbit data for QZSS" in said[0]
    assert sum(1 for row in rows(at) if COUNT.search(row)) >= 3   # NavIC, BeiDou-3 and Galileo still counted
    assert len(rows(at)) == len(shell.CONSTELLATIONS)


def test_without_a_broadcast_check_the_second_count_says_not_read():
    counted = [row for row in rows(run()) if COUNT.search(row)]

    assert counted and all("not read" in row for row in counted)   # tests/conftest.py: no published check


def test_a_day_with_no_findings_says_so(monkeypatch):
    monkeypatch.setattr(findings, "find", lambda summaries: ([], []))

    assert any("nothing stands out today" in body for body in htmls(run()))


# --- the count's parts ---

def test_broadcast_health_is_read_per_satellite_as_healthy_unhealthy_or_silent():
    result = data.load("NavIC", 90)
    names = [str(name) for name in result["health"]["Satellite"]][:3]
    gap = {"day": "2026-11-13", "satellites": [
        {"satellite": names[0], "signal_id": "I01", "health": 0},
        {"satellite": names[1], "signal_id": "I02", "health": 130},
        {"satellite": names[2], "signal_id": "I03", "health": None}]}

    system = system_summary.summary("NavIC", result, gap)

    read = {sat["name"]: sat["broadcast"] for sat in system["sats"]}
    assert [read[name] for name in names] == ["ok", "bad", "silent"]
    assert (system["checked"], system["in_file"], system["flagged_healthy"]) == (3, 2, 1)
    assert system["healthy"] == sum(sat["ok"] for sat in system["sats"]) and system["total"] == 8   # 7 scored, and IRNSS-1D set aside


# --- "Worth a look": each rule fires, and does not ---

def sat(name, score=100.0, ok=True, broadcast="ok", group="A"):
    return {"name": name, "group": group, "score": score, "state": palette.SLOT_IN, "ok": ok, "broadcast": broadcast}


def system(sats, planes=None, name="Test"):
    return {"name": name, "sats": sats, "planes": planes or {}, "broadcast_day": "2026-11-13"}


def test_tracked_but_silent_fires_for_a_satellite_missing_from_the_file_and_not_for_one_set_aside():
    fired = findings.silent(system([sat("A1"), sat("A2", broadcast="silent")]))
    quiet = findings.silent(system([sat("A1"), sat("A2", broadcast="silent", group="set aside")]))

    assert [f["about"] for f in fired] == [["A2"]] and fired[0]["pair"] == (("tracked", 2), ("in the file", 1))
    assert "13 Nov" in fired[0]["numbers"]
    assert quiet == []


def test_two_sources_disagree_fires_both_ways_and_not_when_they_agree():
    fired = findings.disagree(system([sat("A1"), sat("A2", ok=False), sat("A3", broadcast="bad")]))
    quiet = findings.disagree(system([sat("A1"), sat("A2", ok=False, broadcast="bad"), sat("A3", broadcast="silent")]))

    assert [f["about"] for f in fired] == [["A2"], ["A3"]]
    assert "broadcast as healthy" in fired[0]["line"] and "flagged unhealthy" in fired[1]["line"]
    assert quiet == []


def test_plane_out_of_step_fires_for_one_plane_past_its_limit_and_not_when_every_plane_is():
    within = {"offset": 1.0, "offset_limit": 5.0, "gap": 2.0, "gap_limit": 8.0}
    past = {"offset": 1.0, "offset_limit": 5.0, "gap": 16.0, "gap_limit": 8.0}

    fired = findings.plane(system([], {"A": within, "B": past}))

    assert [f["about"] for f in fired] == [["plane B"]] and fired[0]["size"] == 2.0
    assert "16.0° against a limit of 8°" in fired[0]["numbers"]
    assert findings.plane(system([], {"A": within, "B": {**within, "gap": None}})) == []
    assert findings.plane(system([], {"A": past, "B": past})) == []   # the whole system, not one plane


def test_odd_one_out_fires_under_three_spreads_below_the_median_and_not_in_a_system_of_few():
    steady = [sat(f"A{i}") for i in range(5)]

    fired = findings.odd(system(steady + [sat("low", score=84.0), sat("near", score=86.0)]))

    assert [f["about"] for f in fired] == [["low"]]   # the line is 100 - 3 x 5 = 85
    assert "the line is 85" in fired[0]["numbers"]
    assert findings.odd(system([sat("A1"), sat("A2"), sat("low", score=10.0)])) == []


def test_an_explained_finding_is_counted_apart_and_says_why(monkeypatch):
    monkeypatch.setitem(findings.EXPLAINED, ("silent", "Test", "A2"), "retired, kept for messaging")

    listed, explained = findings.find([system([sat("A1"), sat("A2", broadcast="silent"), sat("A3", broadcast="silent")])])

    assert [f["about"] for f in listed] == [["A3"]]
    assert [(f["about"], f["explained"]) for f in explained] == [(["A2"], "retired, kept for messaging")]


def test_the_largest_finding_of_each_rule_is_listed_first():
    small = system([sat("A1"), sat("A2"), sat("A3", broadcast="silent"), sat("A4", ok=False)], name="Small")
    large = system([sat("B1", broadcast="silent"), sat("B2", broadcast="silent"), sat("B3", ok=False)], name="Large")

    listed, _ = findings.find([small, large])

    assert [(f["rule"], f["system"]) for f in listed] == [("silent", "Large"), ("disagree", "Large"),
                                                          ("silent", "Small"), ("disagree", "Small")]
