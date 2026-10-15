"""The master map canvas: the records it is built from, the safety of embedding them, and the page's rules."""
import json
import re

import pytest

from evidence.registry_tables import read_table
from evidence.settings import (COUNTRY_NAMES, COUNTRY_NOT_GIVEN, MAP_WARN, REGISTRY_CATALOGUE_FILE,
                               REGISTRY_SATELLITES_FILE, SCHEME_ORBIT_FEED)
from ui import palette
from ui.components.master_map import PAGE_FILE, master_map_html, master_map_records
from ui.pages_data import DATA_DIR
from evidence.master_map import orbit_feed_checked, orbit_feed_names
from evidence.settings import REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_SIGNAL_IDS_FILE

HOSTILE = "</script><script>alert(1)</script>"


@pytest.fixture(scope="module")
def real():
    return {"satellites": read_table(REGISTRY_SATELLITES_FILE), "catalogue": read_table(REGISTRY_CATALOGUE_FILE),
            "tracked": read_table(REGISTRY_DASHBOARD_SATELLITES_FILE),
            "signal_ids": read_table(REGISTRY_SIGNAL_IDS_FILE), "feed_names": orbit_feed_names(DATA_DIR),
            "feed_checked": orbit_feed_checked(DATA_DIR)}


@pytest.fixture(scope="module")
def records(real):
    return master_map_records(real)


def test_one_record_per_spacecraft(records, real):
    assert len(records) == len(real["satellites"]) == 294
    assert [r["svn"] for r in records] == [row["svn"] for row in real["satellites"]]


def test_c217_carries_the_out_of_date_orbit_feed_name(records):
    c217 = next(r for r in records if r["svn"] == "C217")
    feed = [i for i in c217["identifiers"] if i["scheme"] == SCHEME_ORBIT_FEED]
    assert len(feed) == 1 and feed[0]["status"] == MAP_WARN
    assert (feed[0]["issuer"], feed[0]["checked"]) == ("CelesTrak", "2026-10-04")
    assert len(c217["periods"]) >= 2


def test_a_record_carries_what_the_far_hover_card_says(records):
    found = {r["svn"]: r for r in records}
    assert (found["C217"]["signal_id"], found["C217"]["identity"]) == ("C04", "two sources agree")
    assert found["J008"]["identity"] == "one source only"


def test_countries_are_named_in_full(records, real):
    states = {row["svn"]: row["state"] for row in real["catalogue"]}
    for record in records:
        assert record["country"] == COUNTRY_NAMES.get(states[record["svn"]], COUNTRY_NOT_GIVEN)
    assert {r["country"] for r in records} >= {"India", "China", "United States", "Russia"}


def test_a_card_says_why_the_two_sources_disagree_and_is_silent_otherwise(records):
    said = {r["svn"]: r["disagreement"] for r in records}
    assert said["I004"] and said["I011"]        # the catalogue and the IGS file differ on whether they are in service
    assert said["J008"] == "" and said["C217"] == ""   # one source only is not a disagreement
    assert sum(bool(text) for text in said.values()) == 30


def test_every_constellation_on_the_map_has_a_colour(records):
    assert {r["constellation"] for r in records} <= set(palette.CONSTELLATION_COLOURS)


def test_a_hostile_name_cannot_break_out_of_the_script(real):
    hostile = {**real, "tracked": [{"svn": "C217", "dashboard_name": HOSTILE}]}
    page = master_map_html(hostile)
    assert HOSTILE not in page and "</script><script>" not in page
    assert page.count("<script") == 2 and page.count("</script>") == 2
    payload = re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1)
    assert any(r["name"] == HOSTILE for r in json.loads(payload)["records"])  # it survives, as text


def test_every_colour_placeholder_is_filled(real):
    page = master_map_html(real)
    assert not re.search(r"__[A-Z_]+__", page)
    assert "--platform:" in page and "--warn:" in page


def test_the_page_has_no_stock_dropdown_and_no_outside_address():
    source = PAGE_FILE.read_text(encoding="utf-8")
    assert "<select" not in source.lower() and 'role="listbox"' in source
    assert not re.search(r"https?://|//cdn|@import", source)
