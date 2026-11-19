"""The Home page: a row per system with the count its Overview shows, and the "Worth a look" rules. No network."""
import re

import pandas as pd
import pytest

from test_dashboard_shell import (celestrak_answers_with_nothing_new, htmls, run,  # noqa: F401 (fixtures)
                                  segmented_controls_rerun)
from test_meo_pages import celestrak_answers_with_two_galileo_satellites, scope  # noqa: F401 (a fixture)
from ui import burn_groups, data, findings, home_data, home_settings, limits, palette, shell, system_summary, systems

COUNT = re.compile(r"(\d+ of \d+) satellites healthy and in place")   # said with a card's score
HEADLINE = re.compile(r"(\d+ of \d+)</span>")   # a constellation's own page leads with it
NAME = re.compile(r"<b>(?:<span[^>]*></span>)?([^<]+)</b>")   # a row's name, after its mark


@pytest.fixture(autouse=True)
def the_dashboard_opens_on_home(monkeypatch):
    monkeypatch.setattr(shell, "DEFAULT_PAGE", shell.HOME)


def rows_of(bodies):
    return [body for body in bodies if body.startswith(('<div class="sys ', '<details class="sys '))]


def rows(at):
    return rows_of(htmls(at))


def test_home_is_the_first_page_and_shows_a_row_per_system_in_the_top_bars_order():
    at = run()

    assert shell.PAGES[0][0] == shell.HOME
    assert [NAME.search(row).group(1) for row in rows(at)] == list(systems.SYSTEMS)
    assert set(home_settings.SYSTEMS) == set(systems.SYSTEMS)
    for row in rows(at):   # each row that was read says who runs the system and where it serves
        who, where = home_settings.SYSTEMS[NAME.search(row).group(1)]
        assert who and where and (f"{who} · {where}" in row or "Could not be read" in row)


def test_a_cards_states_ring_its_score_and_are_counted_in_words_beside_each_mark():
    navic = next(row for row in rows(run()) if "NavIC</b>" in row)
    head, body = navic.split("</summary>")

    # the ring: one part per state, in proportion, opening at the bottom like a speedometer
    ring = re.search(r'--ring: conic-gradient\(from -135deg, ([^"]+)\)"', head).group(1)
    assert ring.startswith("var(--ok) 0.0deg") and "var(--bad)" in ring and "var(--warn)" in ring
    # the same counts in words, each beside its mark, so colour is never the only sign; none a link in the head
    assert re.search(r'<span><i class="ok"></i>\d+ healthy and in place</span>', head)
    assert '<span><i class="bad"></i>1 set aside</span>' in head and "how-link" not in head
    # opened, each state's words open their own explanation in "Need help reading this page?"
    assert re.search(r'<a class="how-link" href="#how-needs-a-look"[^>]*>needs a look</a>', body)
    assert '<a class="how-link" href="#how-set-aside"' in body


def test_a_system_with_no_satellites_draws_no_empty_split(monkeypatch):
    monkeypatch.setattr(system_summary, "summary", lambda name, result, gap=None: {
        "name": name, "sats": [], "healthy": 0, "total": 0, "settling": {}, "planes": {}, "in_file": None,
        "flagged_healthy": None, "checked": 0, "broadcast_day": None, "orbit": (0, 0), "station": (0, 0),
        "clock": (0, 0), "clock_typical_ns": None, "score": None, "score_parts": [], "flag_agrees": (0, 0),
        "care": (0, 0), "burn_record": None})

    counted = [row for row in rows(run()) if COUNT.search(row)]

    assert counted and all("--ring: none" in row and ">–</b>" in row and '<i class="ok">' not in row for row in counted)


def test_each_rows_count_is_the_headline_of_that_systems_overview_added_up_over_its_parts():
    home = {system: COUNT.search(row) for system, row in zip(systems.SYSTEMS, rows(run()))}

    assert home["NavIC"] and home["Galileo"] and home["BeiDou-3"]   # judged by slot, by plane, and one with two parts
    for system, parts in systems.SYSTEMS.items():
        healthy = total = 0
        for part in parts:
            bodies = htmls(run(scope(part)))
            headline = next((HEADLINE.search(body) for body in bodies if 'class="ovh"' in body), None)
            if headline is None:   # no orbit data in the test's copy: the part's own page says so
                assert any(f"No orbit data for {part} yet" in body for body in bodies), part
                continue
            count, of = headline.group(1).split(" of ")
            healthy, total = healthy + int(count), total + int(of)
        assert (home[system].group(1) if home[system] else None) == (f"{healthy} of {total}" if total else None), system


def test_a_system_of_two_parts_is_one_row_with_each_part_under_it():
    beidou = [row for row in rows(run()) if "BeiDou-3" in row]

    assert len(beidou) == 1 and "BeiDou-3</b>" in beidou[0] and "China · global" in beidou[0]
    assert re.search(r"IGSO &amp; GEO \d+ of \d+", beidou[0])
    assert "MEO could not be read just now: No orbit data for BeiDou-3 MEO yet" in beidou[0]


def test_a_part_of_a_system_shows_the_whole_systems_count_over_its_own(monkeypatch):
    lines = [body for body in htmls(run(scope("BeiDou-3"))) if 'class="sysline"' in body]

    assert len(lines) == 1 and "BeiDou-3</b>" in lines[0] and "IGSO &amp; GEO" in lines[0]
    assert not any('class="sysline"' in body for body in htmls(run(scope("NavIC"))))   # one part: no line


def test_a_cards_button_opens_that_systems_overview():
    index = list(systems.SYSTEMS).index("Galileo")
    assert run().button(key=f"home_explore_{index}").label == "Explore Galileo further"

    at = run(lambda at: at.button(key=f"home_explore_{index}").click())

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

    said = [row for row in rows(at) if "QZSS</b>" in row]
    assert len(said) == 1 and "Could not be read just now: no orbit data for QZSS" in said[0]
    assert sum(1 for row in rows(at) if COUNT.search(row)) >= 3   # NavIC, BeiDou-3 and Galileo still counted
    assert len(rows(at)) == len(systems.SYSTEMS)


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

    assert [f["about"] for f in fired] == [["A2"]] and fired[0]["pair"] == (("tracked here", 2), ("in the IGS file", 1))
    assert "13 Nov" in fired[0]["numbers"] and "IGS daily broadcast file" in fired[0]["line"]
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


def test_the_words_a_row_explains_are_links_to_the_point_in_how_to_read_that_explains_them():
    bodies = htmls(run())

    how = next(b for b in bodies if 'class="how-grid"' in b)
    cards = set(re.findall(r'<div class="how well(?: wide)?" id="([^"]+)"', how))
    assert cards == {"how-what-is-measured", "how-how", "how-what-we-are-working-towards"}
    targets = cards | set(re.findall(r'<div class="how-p" id="([^"]+)"', how))
    for words, heading in home_settings.HOW_LINKS.items():
        assert heading in {title for _, title, _ in home_settings.HOW}   # each points at a card that exists
    navic = next(row for row in rows_of(bodies) if "NavIC</b>" in row)
    links = re.findall(r'<a class="how-link" href="#([^"]+)"[^>]*>([^<]+)</a>', navic)
    # opened: the measures in the score, then what is shown beside it, then the states, each landing on its point
    assert links[:6] == [("how-" + words.replace(" ", "-"), words) for words in (
        "orbit kept", "station held", "clock steady", "burn record", "says healthy", "flag matches our check")]
    assert ("how-needs-a-look", "needs a look") in links and ("how-set-aside", "set aside") in links
    assert {target for target, _ in links} <= targets


def test_how_to_read_says_it_in_short_bullets_with_a_picture_for_each_term():
    how = next(b for b in htmls(run()) if 'class="how-grid"' in b)

    measured = how.split('id="how-what-is-measured"')[1].split('id="how-how"')[0]
    assert re.findall(r"<h4>([^<]+)</h4>", measured) == ["The score", "The states round the score",
                                                       "Key health attributes", "Extra details"]
    # each state beside its own mark, each attribute beside its icon, the score beside a small ring
    assert re.search(r'id="how-needs-a-look"><span class="how-pic"><span class="dots"><i class="warn"></i>', measured)
    assert re.search(r'id="how-clock-steady"><span class="how-pic"><span class="ic"', measured)
    assert 'id="how-score"><span class="how-pic"><span class="gauge mini"' in measured
    # the mission weights as bars, from ui/limits.py, and words in bullets rather than paragraphs
    assert '<div class="wbars">' in measured and "Clock<small>45%</small>" in measured and "Clock<small>36%</small>" in measured
    assert "Burn<small>10%</small>" in measured
    assert measured.count("<li>") >= 8
    # what is not done yet is framed as what we are working towards, open to working together
    assert "Working together" in how and "What is left out" not in how
    assert '<div class="how well" id="how-how">' in how   # a card of one group keeps its place in the row


def test_a_second_visit_in_the_same_hour_does_not_count_a_constellation_again(monkeypatch):
    counted, real = [], system_summary.summary
    monkeypatch.setattr(system_summary, "summary",
                        lambda name, result, gap=None: counted.append(name) or real(name, result, gap))

    run()   # opens the page and runs it again: two visits already
    first = list(counted)
    run()

    assert first and counted == first and len(set(first)) == len(first)   # each part counted once, then kept


# --- the three measures: orbit kept, station held, clock steady ---

def test_a_satellite_is_judged_on_orbit_station_and_clock_and_not_judged_where_nothing_shows_it():
    result = data.load("NavIC", 90)
    names = [str(name) for name in result["health"]["Satellite"]][:2]
    steady = {"records": 14, "drift_ns_per_day": 800.0, "typical_step_ns": 0.4, "largest_step_ns": 30.0}   # on the line: still steady
    stepped = {**steady, "typical_step_ns": 1.2, "largest_step_ns": 30.1}
    gap = {"day": "2026-11-13", "satellites": [
        {"satellite": names[0], "signal_id": "I01", "health": 0, "clock": steady},
        {"satellite": names[1], "signal_id": "I02", "health": 0, "clock": stepped}]}

    system = system_summary.summary("NavIC", result, gap)

    by_name = {sat["name"]: sat for sat in system["sats"]}
    assert [by_name[name]["clock_steady"] for name in names] == [True, False]
    assert system["clock"] == (1, 2) and system["clock_typical_ns"] == 0.8   # the middle of 0.4 and 1.2
    for sat in system["sats"]:
        if sat["group"] == "set aside":
            assert sat["orbit"] is None and sat["station"] is None   # nothing scored: not judged, not failed
            continue
        tilt, drift = sat["parts"]["Inclination"], sat["parts"]["Drift"]
        assert sat["orbit"] == (tilt >= 80) and sat["station"] == (drift >= 80 and sat["state"] == palette.SLOT_IN)
    judged = [sat for sat in system["sats"] if sat["orbit"] is not None]
    assert system["orbit"] == (sum(sat["orbit"] for sat in judged), len(judged)) and len(judged) == 7
    assert system_summary.summary("NavIC", result)["clock"] == (0, 0)   # no broadcast check: no clock judged


def test_an_open_card_shows_the_scores_measures_raised_then_what_is_only_seen_pressed_in():
    navic = next(row for row in rows(run()) if "NavIC</b>" in row)
    body = navic.split("</summary>")[1]

    in_score, seen = body.split('<div class="tiles in">')[1].split('<div class="tiles seen">')
    seen = re.split(r'<div class="(?:card-notes|dots)', seen)[0]
    tile = r'class="how-link"[^>]*>([^<]+)</a>[^<]*</span><b class="[^"]*">(.*?)</b>'
    assert [(words, re.sub(r"<[^>]+>", "", value)) for words, value in re.findall(tile, in_score)][:3] == [
        ("orbit kept", re.findall(tile, in_score)[0][1].replace("<small>", "").replace("</small>", "")),
        ("station held", re.findall(tile, in_score)[1][1].replace("<small>", "").replace("</small>", "")),
        ("clock steady", "not read")]   # no broadcast check in tests
    assert re.fullmatch(r"\d+ of 7", re.sub(r"<[^>]+>", "", re.findall(tile, in_score)[0][1]))   # 7 scored
    assert [words for words, _ in re.findall(tile, seen)] == ["says healthy", "flag matches our check", "irregular burns"]
    assert "too little history" not in seen   # NavIC is held by slot: its burns are found
    # the burn record: as a measure of the score (satellites that pass) and, seen, how many of the burns were irregular
    assert re.search(r'burn record</a></span><b class="num[^"]*">\d+ <small>of \d+</small>', in_score)
    assert re.search(r"\d+ <small>of \d+ burns irregular</small></b><span class=\"small\">(\d+% \(\d+–\d+%\)|too few to rate)", seen)


def test_clock_stepped_fires_for_a_step_past_the_line_and_not_for_steady_clocks():
    def heard(name, step):
        return {**sat(name), "clock_steady": step <= 30, "clock": {"largest_step_ns": step}}

    fired = findings.clock(system([heard("A1", 2.0), heard("A2", 42009.3), heard("A3", 35.0), sat("A4")]))
    quiet = findings.clock(system([heard("A1", 2.0), heard("A2", 29.9), sat("A3")]))

    assert [f["about"] for f in fired] == [["A2", "A3"]] and fired[0]["pair"] == (("largest step, ns", 42009), ("steady up to, ns", 30.0))
    assert "2 clocks stepped more than 30 ns" in fired[0]["line"] and "1 of 3 clocks heard were steady" in fired[0]["numbers"]
    assert quiet == []


def test_a_constellations_own_page_declares_the_three_measures_and_lists_every_satellite_against_them():
    for name, station_words in (("NavIC", "in its slot and not drifting"), ("Galileo", "in step with its plane")):
        bodies = htmls(run(scope(name)))

        strip = next(body for body in bodies if 'class="ovh"' in body)   # the header declares the measures in its sum
        assert re.search(r"Orbit kept \d+% of its", strip) and re.search(r"Station held \d+% of its", strip)
        assert "says healthy: not read" in strip   # no broadcast check in tests
        table = next(body for body in bodies if "Orbit kept<small>" in body)
        assert station_words in table and "Clock steady<small>no step past 30 ns in the day" in table
        counted = int(HEADLINE.search(strip).group(1).split(" of ")[1])
        assert table.count("<tr>") - 1 == counted   # a line per satellite the page counts


def published_copy(made, window_days=90, **changes):
    """Home's parts as the archive job would publish them, counted here from the test's data."""
    from ui import time_range
    parts = {}
    for name in (name for names in systems.SYSTEMS.values() for name in names):
        try:
            parts[name] = home_data.part_summary(name, time_range.DEFAULT_DAYS, "h", "f", "c")
        except ValueError:   # no orbit data for it in the test's copy: the job would leave it out too
            pass
    return {"made": made, "window_days": window_days, "parts": {**parts, **changes}}


def test_home_reads_the_published_count_while_it_is_fresh_and_says_when_it_was_counted(monkeypatch):
    from datetime import datetime, timedelta, timezone
    made = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    copy = published_copy(made)
    copy["parts"]["NavIC"] = {**copy["parts"]["NavIC"], "healthy": 1}   # so the page shows the copy's number
    monkeypatch.setattr(home_data, "_snapshot", lambda: copy)
    counted = []

    def count_here(*args):   # as the real one does for a part with no orbit data in the test's copy
        counted.append(args)
        raise ValueError("no orbit data")
    monkeypatch.setattr(home_data, "part_summary", count_here)

    bodies = htmls(run())

    assert {args[0] for args in counted} == {name for names in systems.SYSTEMS.values() for name in names} - set(copy["parts"])
    assert "NavIC" in copy["parts"]   # only the parts the copy leaves out are counted on the server
    navic = next(row for row in rows_of(bodies) if "NavIC</b>" in row)
    assert re.search(r"; 1 of \d+ satellites healthy and in place", navic)
    assert any(f"counted {made[8:10]} " in body for body in bodies if 'class="head"' in body)


def test_a_published_count_that_is_old_for_another_time_range_or_malformed_is_counted_here_instead(monkeypatch):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (now - home_settings.SNAPSHOT_MAX_AGE - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for copy in (published_copy(old), published_copy(fresh, window_days=30), {"made": "yesterday"}, {}):
        monkeypatch.setattr(home_data, "_snapshot", lambda copy=copy: copy)
        assert home_data.published(90) == (None, {})
    good = published_copy(fresh)["parts"]["NavIC"]
    broken = published_copy(fresh, GPS={"healthy": 3}, Galileo={**good, "sats": [None]}, Bogus=good)
    monkeypatch.setattr(home_data, "_snapshot", lambda: broken)
    made, parts = home_data.published(90)
    # a part without what Home reads, with a satellite not in shape, or not a part at all is left out; the rest kept
    assert made and "NavIC" in parts and not {"GPS", "Galileo", "Bogus"} & set(parts)
    assert run().exception == []   # and Home counts what was left out itself


def test_the_job_writes_every_part_it_can_count_in_the_shape_home_reads(monkeypatch):
    import json
    from datetime import datetime, timezone
    from scripts import home_snapshot
    monkeypatch.setattr(data, "refresh", lambda: None)   # no network in tests: count from the test's copy

    payload = json.loads(json.dumps(home_snapshot.snapshot(datetime(2026, 11, 16, 6, tzinfo=timezone.utc)),
                                    default=home_snapshot._plain))
    monkeypatch.setattr(home_data, "_snapshot", lambda: payload)

    made, parts = home_data.published(90, now=datetime(2026, 11, 16, 8, tzinfo=timezone.utc))
    assert payload["made"] == "2026-11-16T06:00:00Z" and made and set(parts) == set(payload["parts"]) >= {"NavIC", "Galileo"}


# --- one score per constellation ---

def test_the_score_weighs_the_measures_by_mission_and_shares_out_one_not_read():
    counts = {"orbit": (2, 7), "station": (6, 7), "clock": (3, 3), "care": (7, 7)}
    no_care = {key: value for key, value in counts.items() if key != "care"}
    regional, global_ = system_summary.score_of(counts, "NavIC"), system_summary.score_of(counts, "Galileo")
    no_clock = system_summary.score_of({"orbit": (31, 32), "station": (18, 24), "clock": (0, 0), "care": (0, 0)}, "GPS")

    # NavIC is regional: clock 45%, station 27%, orbit 18%, burn record 10%; Galileo global: clock 36%, orbit 31.5%,
    # station 22.5%, burn record 10% (the burn record takes a tenth of each of the other three's old weight)
    assert regional[0] == round(100 * .45 + 600 / 7 * .27 + 200 / 7 * .18 + 100 * .10)
    assert [(key, rate, pytest.approx(weight)) for key, rate, weight in regional[1]] == [
        ("clock", 100.0, pytest.approx(.45)), ("station", 600 / 7, pytest.approx(.27)),
        ("orbit", 200 / 7, pytest.approx(.18)), ("care", 100.0, pytest.approx(.10))]
    assert global_[0] == round(100 * .36 + 200 / 7 * .315 + 600 / 7 * .225 + 100 * .10) and global_[0] < regional[0]
    for weights in limits.MEASURE_WEIGHTS.values():
        assert abs(sum(weights.values()) - 1) < 1e-9
    # a part takes its constellation's weights; a measure not read is left out and the rest scaled up to add to 1
    assert system_summary.score_of(counts, "BeiDou-3 MEO") == system_summary.score_of(counts, "BeiDou-3")
    assert no_clock[0] == round(100 * 31 / 32 * .315 / .54 + 75 * .225 / .54)
    assert [(key, weight) for key, _, weight in no_clock[1]] == [("orbit", pytest.approx(.315 / .54)), ("station", pytest.approx(.225 / .54))]
    # no burn record read (a medium-orbit constellation, or counts made before it existed): the old three, as they were
    # (clock 40%, orbit 35%, station 25% for a global one), so its score is unchanged
    old = system_summary.score_of(no_care, "Galileo")
    assert old[0] == round(100 * .4 + 200 / 7 * .35 + 600 / 7 * .25)
    assert [(key, rate, pytest.approx(weight)) for key, rate, weight in old[1]] == [
        ("clock", 100.0, pytest.approx(.4)), ("orbit", 200 / 7, pytest.approx(.35)), ("station", 600 / 7, pytest.approx(.25))]
    assert system_summary.score_of({"orbit": (0, 0), "station": (0, 0), "clock": (0, 0)}, "GPS") == (None, [])


def test_each_card_leads_with_its_score_and_its_how_scored_tip_says_when_it_is_from_fewer_measures():
    navic = next(row for row in rows(run()) if "NavIC</b>" in row)
    head, body = navic.split("</summary>")

    # the score sits to the right of the name, big in the middle of its ring, with the count in place said with it
    score = re.search(r'</div><div class="gauge" [^>]*aria-label="Score (\d+) out of 100; \d+ of \d+ satellites healthy '
                      r'and in place"><b class="num (ok|warn|bad)">\1</b><small>/ 100</small></div><span class="sys-go"', head)
    assert head.index('class="sys-id"') < head.index('class="gauge"')
    assert score and f'<details class="sys card {score.group(2)}">' in navic   # the card's edge in the score's colour
    # no broadcast check in tests, so no clock: the tip on "how this is scored" says the score is from 3 of 4 (the burn record is read)
    assert 'tabindex="0" aria-describedby="tt-' in head and ">how this is scored</span>" in head
    assert "From 3 of 4 today: 1 measure could not be read, so the others count for its share." in head
    # the tip names the weights for NavIC's mission, heaviest first
    assert re.search(r"weighed for a regional constellation.*Clock steady 45%.*Station held 27%.*Orbit kept 18%.*Burn record 10%", head)
    assert "Shown beside" not in body


def test_a_constellations_page_opens_up_its_score_into_its_sum():
    bodies = htmls(run(scope("NavIC")))

    strip = next(body for body in bodies if 'class="ovh"' in body)
    # in pictures, with a short key: each attribute's name and its weight over its share of the bar, the points it
    # adds under it; the score once, large, in the header. Clock not read: its 45% shared out, so station weighs 49%, orbit 33%, the burn record 18%
    assert re.search(r'<div class="ovh-score (ok|warn|bad)" role="img" aria-label="score \d+ of 100"><b class="num">\d+</b>', strip)
    assert re.search(r'<span class="ss-name">Station</span><span class="ss-w num">49%</span>.*?<span class="ss-pts">\+<b '
                     r'class="num">\d+</b></span>.*?<span class="ss-name">Orbit</span><span class="ss-w num">33%</span>.*?'
                     r'<span class="ss-name">Burn</span><span class="ss-w num">18%</span>', strip)
    assert "ss-total" not in strip   # not said twice
    assert "width: its weight" in strip and "filled: satellites that pass" in strip
    # read aloud in full instead
    assert re.search(r'aria-label="Station held \d+% of its 49% share: [\d.]+ points, Orbit kept \d+% of its 33% share: '
                     r'[\d.]+ points, Burn record \d+% of its 18% share: [\d.]+ points; score \d+ out of 100, weighed for a regional constellation; 1 not read today', strip)


def _burn(satellite, days_ago, burn_class, now, counted=True):
    return {"satellite": satellite, "when": now - pd.Timedelta(days=days_ago), "burn_class": burn_class, "counted": counted}


def test_a_satellite_passes_the_burn_record_with_no_irregular_burn_in_90_days_and_at_most_a_quarter_in_a_year():
    from ui import burn_record
    now = pd.Timestamp("2026-11-16")
    rows = ([_burn("steady", d, "routine east-west", now) for d in (20, 80, 140, 200)]
            + [_burn("recent", d, "routine east-west", now) for d in (200, 150, 100, 60)] + [_burn("recent", 30, "response", now)]
            + [_burn("old", d, "routine east-west", now) for d in (20, 60, 100)] + [_burn("old", 200, "off pattern", now)]
            + [_burn("many", d, "routine east-west", now) for d in (20, 60)] + [_burn("many", d, "response", now) for d in (150, 200)]
            + [_burn("few", d, "routine east-west", now) for d in (20, 60)]
            + [_burn("guess", d, "response", now, counted=False) for d in (10, 20, 30)]   # low confidence: not counted
            + [_burn("moved", d, "relocation", now, counted=False) for d in (10, 20, 30)]   # planned: neutral
            + [_burn("past", 400, "routine east-west", now)] * 4)   # outside 365 days
    care = burn_record.care_of(pd.DataFrame(rows), now)

    assert care["steady"] is True                 # no irregular burn at all
    assert care["recent"] is False                # one in the last 90 days, though 1 of 5 is under a quarter
    assert care["old"] is True                    # 1 of 4 is exactly a quarter, and 200 days ago: passes
    assert care["many"] is False                  # 2 of 4 irregular, both older than 90 days
    assert care["few"] is None                    # 2 judged burns: not judged
    assert care.get("guess") is None and care.get("moved") is None and "past" not in care


def test_the_burn_record_counts_what_the_burns_were_and_says_too_few_to_rate_under_8():
    from ui import burn_record
    now = pd.Timestamp("2026-11-16")
    rows = ([_burn("A", d, "routine east-west", now) for d in range(10, 330, 40)] + [_burn("A", 5, "response", now)]
            + [_burn("A", 50, "relocation", now, counted=False), _burn("A", 70, "artefact", now, counted=False),
               _burn("A", 90, "unexplained", now, counted=False)])
    record = burn_record.record_of(pd.DataFrame(rows), now)

    assert (record["routine"], record["response"], record["off"], record["planned"], record["open"], record["artefact"]) == (8, 1, 0, 1, 1, 1)
    assert (record["decided"], record["irregular"]) == (9, 1)
    assert burn_record.words(record) == "1 of 9 burns irregular (11%, 2–44%)"
    small = burn_record.record_of(pd.DataFrame(rows[:3] + rows[8:9]), now)
    assert burn_record.words(small).startswith("too few to rate (1 of 4 burns irregular")
    assert burn_record.words(None) == "" and burn_record.record_of(None) is None
    both = burn_record.combine([record, small, None])
    assert both["decided"] == 13 and both["irregular"] == 2 and both["routine"] == 11


def test_a_flag_matches_where_it_says_what_we_count_and_a_constellations_burn_record_adds_its_parts_up():
    parts = [{"flag_agrees": (2, 3), "burn_record": {**dict.fromkeys(burn_groups.COUNT_KEYS, 0), "routine": 9, "response": 1}},
             {"flag_agrees": (5, 5), "burn_record": None}]
    whole = system_summary.whole("BeiDou-3", [{**system_summary.summary("NavIC", data.load("NavIC", 90)), **part}
                                              for part in parts])
    assert whole["flag_agrees"] == (7, 8)
    assert (whole["burn_record"]["decided"], whole["burn_record"]["irregular"]) == (10, 1)


def test_an_opened_card_goes_to_the_top_after_any_opened_before_it_and_a_closed_one_goes_back():
    from views import home
    script = home._CARDS_SCRIPT

    # the order a card takes: opened ones before every closed one (order 0), in the order they were opened
    assert 'item.style.order = card.open ? String(window.homeCardTurn - 1000000) : ""' in script
    assert "prefers-reduced-motion: reduce" in script and "motion.finish()" in script   # no motion asked: none
    assert "{   // its own block" in script   # beside the links script in one frame, without a clash


def test_the_bars_points_always_add_up_to_the_score_shown():
    from ui.three_measures import _whole_points
    assert _whole_points([("station", 49.4, 0.6), ("orbit", 49.4, 0.4)], 49) == [29, 20]   # 29.64 + 19.76
    tied = _whole_points([("clock", 100.0, 0.5), ("station", 600 / 7, 0.3), ("orbit", 200 / 7, 0.2)], 81)
    assert tied[0] == 50 and sum(tied) == 81   # station and orbit tie on what rounding lost: either takes the point
    for rates, score in (([("clock", 33.3, 0.4), ("orbit", 66.7, 0.35), ("station", 50.0, 0.25)], 49),):
        assert sum(_whole_points(rates, score)) == score


def test_a_constellation_of_two_parts_has_one_score_shown_alike_everywhere_with_each_parts_own_beside_it():
    from ui import system_summary, three_measures

    def sat(ok):
        return {"name": "x", "orbit": ok, "station": ok, "clock_steady": ok, "clock": None}

    def part(name, good, bad):
        sats = [sat(True)] * good + [sat(False)] * bad
        return {"name": name, "sats": sats, "checked": 0, "burn_record": None, "flag_agrees": (0, 0), "healthy": good,
                "total": good + bad, "settling": {}, "flagged_healthy": None,
                **system_summary._measures(sats, name)}

    high, medium = part("BeiDou-3", 6, 4), part("BeiDou-3 MEO", 20, 0)
    whole = system_summary.whole("BeiDou-3", [high, medium])
    assert whole["part_scores"] == [("IGSO & GEO", 60), ("MEO", 100)]
    assert 60 < whole["score"] < 100   # every satellite counted once: 26 of 30 pass
    shown = three_measures.part_scores(whole, "MEO")
    assert 'class="ps-box here ok"><small>MEO</small><b class="num">100</b>' in shown
    assert "BeiDou-3&#x27;s score counts every satellite of its parts once" in shown
    assert three_measures.part_scores(system_summary.whole("NavIC", [part("NavIC", 3, 1)])) == ""


def test_summary_counts_the_burn_record_over_the_satellites_it_judged():
    summary = system_summary.summary("NavIC", data.load("NavIC", 90))
    judged = [sat["care"] for sat in summary["sats"] if sat["care"] is not None]

    assert summary["care"] == (sum(judged), len(judged)) and len(judged) > 0
    assert summary["burn_record"] and all(sat["care"] is None for sat in summary["sats"] if sat["group"] == "set aside")


def test_a_constellation_without_a_burn_record_counts_three_measures_and_says_nothing_of_it():
    from ui import three_measures
    from views import home
    rates = [("clock", 100.0, .4), ("orbit", 90.0, .35), ("station", 80.0, .25)]
    system = {"name": "Galileo", "score": 94, "score_parts": rates, "burn_record": None}

    assert "not read" not in three_measures.score_sum(system) and "Burn" not in three_measures.score_sum(system)
    assert [key for key, _ in three_measures._read(system)] == ["orbit", "station", "clock"]
    tip = home._how_scored(system, 0)
    assert "3 measures" in tip and "Burn record" not in tip and "could not be read" not in tip and "Clock steady 40%" in tip
    # where burns are found but the burn record could not be read, it is counted as not read
    both = {**system, "burn_record": {**dict.fromkeys(burn_groups.COUNT_KEYS, 0), "routine": 9}}
    assert "1 not read today" in three_measures.score_sum(both) and "From 3 of 4 today" in home._how_scored(both, 0)


def test_a_set_aside_satellite_says_why_it_has_no_burn_record():
    from ui import three_measures
    assert three_measures._care({"group": "set aside", "care": None})["note"] == "set aside: not judged"
    assert "fewer than 3 judged burns" in three_measures._care({"group": "GEO", "care": None})["note"]


def test_a_new_satellite_is_a_small_chip_with_the_day_it_is_scored_from_and_its_stage_in_the_tooltip():
    from views import home
    chip = home._new_chip("NVS-03", "at its slot since 13 Nov 2026, scored from 13 Dec 2026", 0)
    assert "NVS-03 · new · scored from 13 Dec</span>" in chip and "at its slot since 13 Nov 2026" in chip
    assert "NVS-03 · new · not scored yet</span>" in home._new_chip("NVS-03", "on its way", 0)
