"""The Library's shelves: only the project's own data is offered, each with how to get, use and cite it; others' data
is credited and linked; a jump opens a shelf; and the page still draws when a published file cannot be read."""
import json
from html import escape
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ButtonGroup

import ui.components.lifecycle as lifecycle_component
from ui import reveal, shelf
from ui.shelf_settings import COLLEAGUES, FITTED, ORBIT_GAP, OTHERS, OURS, SHELVES

ROOT = Path(__file__).resolve().parent.parent
NEWS_SAMPLE = {"generated_at": "2026-11-15T03:00:00Z", "rules": {}, "sources": {}, "invalid_items": 0, "items": [
    {"title": "NVS-03 reaches its slot", "address": "https://example.com/a", "source_id": "example.com",
     "category": "launch", "constellations": ["NavIC"], "published_at": "2026-11-14T10:00:00Z"},
    {"title": "Galileo L14 launched", "address": "https://example.com/b", "source_id": "example.com",
     "category": "launch", "constellations": ["Galileo"], "published_at": "2026-11-13T10:00:00Z"}]}
FILES = {ORBIT_GAP: ({"day": "2026-11-13", "satellites": []}, ""), FITTED: ({}, "it cannot be read right now"),
         "news": (NEWS_SAMPLE, "")}


def test_every_dataset_of_ours_says_how_to_get_use_and_cite_it():
    for key, item in OURS.items():
        content, fresh, problem = shelf.item_state(key, FILES)
        html = shelf.card_html(key, content, fresh, problem)
        for words in ("<i>Fresh</i>", "<i>Address</i>", "CC BY 4.0", "How to use it", "<b>Example</b>", "<b>Not for</b>",
                      "<b>Cite</b>", item["address"]):
            assert words in html, (key, words)
        assert item["address"].startswith("https://raw.githubusercontent.com/")


def test_dataset_citations_have_short_and_long_forms_with_the_key_fields():
    content = b"at_utc,satellite\n2026-11-13T00:00:00Z,NVS-03\n"
    words = shelf.dataset_citations("lifecycles", content)
    assert "OpenGNSS (" in words["short"] and "Satellite lifecycles" in words["short"]
    assert OURS["lifecycles"]["address"] in words["short"]
    for needed in ("Version/date:", "2026-11-13", "Licence: CC BY 4.0", "Accessed "):
        assert needed in words["long"]


def test_only_our_own_files_are_offered_and_others_are_linked_to_their_owners():
    # NOTICE: orbit records keep Space-Track's and CelesTrak's terms, GCAT and the IGS files are their owners', and
    # headlines belong to their publishers. None of those is a dataset of ours.
    files = {path for item in OURS.values() for kind, path in [item["file"]] if kind == "repo"}
    assert not files & {"registry/catalogue.csv", "registry/satellites.csv", "registry/signal_ids.csv"}
    assert not any(path.startswith("data/") for path in files)
    html = shelf.others_html(OTHERS)
    for name, _, link, _, _ in OTHERS:
        assert escape(name) in html and (not link or link in html)
    assert "indianspaceflight.in" in shelf.colleagues_html(COLLEAGUES)


def test_a_file_that_cannot_be_read_says_so_and_freshness_says_when_we_update_it():
    content, fresh, problem = shelf.item_state("fitted", FILES)
    assert content is None and "cannot be read right now" in shelf.card_html("fitted", content, fresh, problem)
    content, fresh, problem = shelf.item_state("orbit_gap", FILES)
    assert not problem and json.loads(content)["day"] == "2026-11-13"
    assert fresh.startswith("made 13 Nov 2026 · updated by us daily 06:00 UTC")
    assert "updated by us Sundays 02:00 UTC" in shelf.item_state("sources", FILES)[1]
    assert "counts" not in OURS   # launched, lost and kept: published widely, so not offered as ours
    assert "kept by hand" in shelf.item_state("lifecycles", FILES)[1]


@pytest.fixture
def library_page(monkeypatch):
    """AppTest 1.45 reads a segmented control's single value as a list (as tests/test_dashboard_shell.py patches).
    Returns open_page(files, jump=None) and the constellations the lifecycle timelines were asked to show first."""
    def indices(self):
        chosen = self.value if isinstance(self.value, list) else [] if self.value is None else [self.value]
        return [self.options.index(self.format_func(v)) for v in chosen]
    monkeypatch.setattr(ButtonGroup, "indices", property(indices))
    shown = []
    monkeypatch.setattr(lifecycle_component, "lifecycle_frame", lambda *args: shown.append(args[3] if len(args) > 3 else None))

    def open_page(files, jump=None):
        monkeypatch.setattr(shelf, "published", lambda: files)
        at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=600).run()
        if jump:
            at.session_state["library_jump"] = jump
        at.switch_page("views/library.py").run()
        assert not at.exception, [e.value for e in at.exception]
        return at
    return open_page, shown


def page_html(at):
    return "".join(part.proto.body for part in at.get("html"))


def test_the_library_draws_every_shelf_with_a_tile_each_and_no_page_blurb(library_page):
    open_page, _ = library_page
    at = open_page(FILES)
    page = page_html(at)
    for title, _, _ in SHELVES.values():
        assert f"<h2>{title}</h2>" in page
    assert sorted(button.key for button in at.button if button.key.startswith("tile_")) == sorted(f"tile_{k}" for k in SHELVES)
    labels = [button.proto.label for button in at.get("download_button")]
    assert "Download orbit_gap.json" in labels and "Download lifecycle_events.csv" in labels
    assert "Download fitted_orbits.json" not in labels   # could not be read: said on its card instead
    assert not any(label.endswith(".zip") for label in labels)
    assert "Everything the dashboard knows" not in page and "NVS-03 reaches its slot" in page
    assert any("Lifecycles" in box.label for box in at.checkbox)


def test_a_tile_opens_its_shelf(library_page):
    open_page, _ = library_page
    at = open_page(FILES)
    assert not at.session_state[reveal.MEMORY].get("library_cite")
    next(button for button in at.button if button.key == "tile_cite").click().run()
    assert at.session_state[reveal.MEMORY]["library_cite"] is True and "library_jump" not in at.session_state


def test_a_jump_from_another_page_opens_the_lifecycles_with_its_constellation(library_page):
    open_page, shown = library_page
    at = open_page(FILES, {"shelf": "satellites", "constellation": "BeiDou-3"})
    assert at.session_state[reveal.MEMORY]["library_lifecycles"] is True
    assert "library_jump" not in at.session_state
    assert shown[-1] == "BeiDou"   # the timelines' own name for BeiDou-3's satellites


def test_a_jump_to_stories_for_one_constellation_shows_only_its_stories(library_page):
    open_page, _ = library_page
    page = page_html(open_page(FILES, {"shelf": "stories", "constellation": "Galileo"}))
    assert "Galileo L14 launched" in page and "NVS-03 reaches its slot" not in page


def test_the_library_still_draws_when_the_news_cannot_be_read(library_page):
    open_page, _ = library_page
    at = open_page({**FILES, "news": ({}, "the news file could not be read")})
    assert "The stories cannot be read right now: the news file could not be read." in page_html(at)
    assert "Download orbit_gap.json" in [button.proto.label for button in at.get("download_button")]


def test_the_library_has_its_own_contact_shelf_and_the_footer_leaves_its_copy_out_there(library_page, monkeypatch):
    monkeypatch.setenv("CONTACT_FORM_URL", "http://127.0.0.1:9/contact")
    monkeypatch.setenv("CONTACT_FORM_TOKEN", "test-token")
    open_page, _ = library_page
    at = open_page(FILES)
    keys = [box.key for box in at.text_input]
    assert "contact_library_address" in keys and "contact_footer_address" not in keys
    assert "<h2>Contact us</h2>" in page_html(at)


def test_the_dashboard_citation_frame_is_filled_and_left_live_for_the_browser():
    from ui.components.citation import citation_html

    page = citation_html()
    assert "OpenGNSS GNSS Health Monitor" in page and "CC BY 4.0" in page
    assert "{accessed}" in page and "{year}" in page   # filled in the browser at the moment of copying
    assert "__ROOT__" not in page and "__FONT__" not in page and "__DATA__" not in page
