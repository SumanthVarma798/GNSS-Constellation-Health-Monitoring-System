"""The Master map page around the map: a row per constellation with ways onward, the live orbit-feed names, and how
fresh each source is, said in words. No network."""
import json
import re
from datetime import datetime, timezone

from test_dashboard_shell import (celestrak_answers_with_nothing_new, htmls, run,  # noqa: F401 (fixtures)
                                  segmented_controls_rerun)
from evidence.settings import SCHEME_ORBIT_FEED, SCHEME_SIGNAL_ID
from ui import master_map_page as mm, systems
from ui.components.master_map import master_map_html
from ui.pages_data import load_master_map_data, with_live_feed

PAGE = "views/master_map.py"
NOW = datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)


def record(svn, constellation="GPS", signal="ok", disagreement="", sighting="", feed=None):
    identifiers = [{"scheme": SCHEME_SIGNAL_ID, "status": signal, "remark": ""}]
    if feed:
        identifiers.append({"scheme": SCHEME_ORBIT_FEED, "status": feed, "remark": "one signal ID out of date"})
    return {"svn": svn, "name": svn, "constellation": constellation, "disagreement": disagreement,
            "sighting": sighting, "signal_id": "G01", "identifiers": identifiers}


def open_page(setup=lambda at: None):
    def go(at):
        at.switch_page(PAGE)   # conftest opens the dashboard on the Overview
        setup(at)
    return run(go)


def test_a_dot_says_its_kind_and_a_disagreement_wins():
    assert mm.dot_kind(record("G1")) == "now"
    assert mm.dot_kind(record("G2", signal="idle")) == "past"
    assert mm.dot_kind(record("G3", signal="idle", sighting="seen")) == "seen"
    assert mm.dot_kind(record("G4", disagreement="the catalogue says it ended")) == "look"
    assert mm.dot_kind(record("G5", feed="warn")) == "look"


def test_each_row_counts_its_own_constellation_and_beidou_takes_both_of_its_parts():
    records = [record("G1"), record("G2", signal="idle"), record("G3", feed="warn"), record("C1", "BeiDou")]
    rows = mm.constellations(records, {"GPS": ("GPS",), "BeiDou-3": ("BeiDou-3", "BeiDou-3 MEO")},
                             {"GPS": 32, "BeiDou-3": 10, "BeiDou-3 MEO": 30})

    gps, beidou = rows
    assert (gps["total"], gps["now"], gps["look"], gps["tracked"]) == (3, 2, 1, 32)
    assert (beidou["total"], beidou["tracked"]) == (1, 40)   # the registry's BeiDou is the pages' BeiDou-3


def test_the_live_feed_names_every_tracked_satellite_and_wins_over_the_weekly_files():
    tables = {"feed_names": {1: "OLD (C01)", 2: "KEPT"}, "feed_checked": {1: "2026-11-08", 2: "2026-11-08"}}
    live = {"rows": {1: [{"OBJECT_NAME": "NEW (C02)"}], 3: [{"OBJECT_NAME": "GPS BIIF-1  (PRN 25)"}]},
            "copy_at": datetime(2026, 11, 15, 7, 48, tzinfo=timezone.utc), "fetched": None}

    merged = with_live_feed(tables, live)

    assert merged["feed_names"] == {1: "NEW (C02)", 2: "KEPT", 3: "GPS BIIF-1  (PRN 25)"}
    assert merged["feed_checked"] == {1: "2026-11-15", 2: "2026-11-08", 3: "2026-11-15"}
    assert with_live_feed(tables, {"rows": {}, "copy_at": None, "fetched": None}) is tables   # none read: files stand


def test_every_source_says_how_fresh_it_is_in_words_and_colour():
    tables = load_master_map_data()
    live = {"rows": {}, "copy_at": datetime(2026, 11, 15, 7, 48, tzinfo=timezone.utc), "fetched": None}

    facts = mm.freshness(tables, live, NOW)

    assert [f["source"] for f in facts] == ["IGS satellite file", "GCAT catalogue", "CelesTrak orbit feed",
                                           "our dashboard registry", "CelesTrak GNSS group"]
    assert all(f["when"] and f["how"] and f["status"] in ("ok", "warn", "bad", "idle") for f in facts)
    igs = facts[0]
    assert igs["when"].startswith("newest change it records: ") and "Sundays 01:00 UTC, next about 22 Nov" in igs["how"]
    assert facts[2] == {**facts[2], "when": "copy taken 15 Nov 2026 07:48 UTC", "status": "ok"}
    stale = mm.freshness(tables, {**live, "copy_at": datetime(2026, 11, 11, tzinfo=timezone.utc)}, NOW)[2]
    assert stale["status"] == "bad"
    missing = mm.freshness(tables, {"rows": {}, "copy_at": None, "fetched": None}, NOW)[2]
    assert missing["status"] == "warn" and missing["when"].startswith("weekly copy of ") and "only" in missing["how"]


def test_the_page_reads_in_the_dashboards_order_with_a_row_per_constellation():
    bodies = htmls(open_page())
    text = "\n".join(bodies)

    rows = [body for body in bodies if body.startswith('<div class="sys mm-sys"')]
    assert [re.search(r"<b>([^<]+)</b>", row).group(1) for row in rows] == list(systems.SYSTEMS)
    order = ["navigation spacecraft on record", '<div class="sys mm-sys"', "Every spacecraft under every name",
             "Where this comes from", "mm-sources"]
    assert [text.index(words) for words in order] == sorted(text.index(words) for words in order)
    legend = next(body for body in bodies if "What a dot means" in body)
    for words in ("round: has a signal ID today", "ring: seen in orbit", "diamond: our sources disagree"):
        assert words in legend
    for row in rows:   # state is said in words beside the dots, never by colour alone
        assert re.search(r'role="img" aria-label="\d+ has a signal ID today', row)
    mine = [body for body in bodies if ("mm-" in body or "navigation spacecraft" in body) and "<style" not in body]
    seen = re.sub(r"<[^>]+>", " ", "\n".join(mine))   # the words a reader sees: they say constellation, not system
    assert "constellations" in seen and not re.search(r"\bsystems?\b", seen, re.I)


def test_a_row_leads_to_its_part_of_the_map_and_to_each_parts_overview():
    at = open_page()
    labels = [button.label for button in at.button]
    assert "BeiDou-3 high orbit overview" in labels and "BeiDou-3 medium orbit overview" in labels
    assert labels.count("Show on the map") == len(systems.SYSTEMS)

    at.button(key="mm_map_1").click().run()   # QZSS
    assert at.session_state["master_map_focus"] == "QZSS"
    assert "showing QZSS" in "\n".join(htmls(at))
    assert any(button.label == "Show every constellation" for button in at.button)

    at.button(key="mm_ov_BeiDou-3 MEO").click().run()
    assert (at.session_state["scope"], at.session_state["page"]) == ("BeiDou-3 MEO", "Overview")


def test_the_map_opens_filtered_to_the_chosen_constellation_and_fits_its_frame():
    page = master_map_html(load_master_map_data(), focus="QZSS")
    payload = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))

    assert payload["focus"] == "QZSS"
    # the canvas's height follows the width within bounds, and the frame then takes its content's height
    assert "function fitFrame" in page and "html, body { margin: 0; }" in page and "height: clamp(" in page


def test_a_plain_wheel_scrolls_the_page_and_never_zooms_the_map():
    """The map sits inside a page: a reader scrolling past it must not zoom it out to a speck (it did, 15 Nov)."""
    page = master_map_html(load_master_map_data())
    wheel = page[page.index('canvas.addEventListener("wheel"'):]
    wheel = wheel[:wheel.index("}, { passive: false });")]

    plain = wheel.index("if (!(e.ctrlKey || e.metaKey))")
    assert plain < wheel.index("preventDefault") and "return;" in wheel[plain:wheel.index("preventDefault")]
    assert 'id="hint"' in page and "scroll to zoom" in page   # and it says how to zoom
