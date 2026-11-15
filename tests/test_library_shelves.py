"""The Library's shelves: every dataset says whose it is and how fresh, only files their owners let us pass on are
offered, the bundle carries each one's licence, and the page still draws when a published file cannot be read."""
import io
import json
import zipfile
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ButtonGroup

from ui import shelf
from ui.shelf_settings import DATASETS, FITTED, LATEST_GNSS, LICENCES, NEWS, ORBIT_GAP, SHELVES

ROOT = Path(__file__).resolve().parent.parent
NEWS_SAMPLE = {"generated_at": "2026-11-15T03:00:00Z", "rules": {}, "sources": {}, "invalid_items": 0, "items": [
    {"title": "NVS-03 reaches its slot", "address": "https://example.com/a", "source_id": "example.com",
     "category": "launch", "constellations": ["NavIC"], "published_at": "2026-11-14T10:00:00Z"}]}
FILES = {ORBIT_GAP: ({"day": "2026-11-13", "rows": []}, ""), FITTED: ({}, "it cannot be read right now"),
         NEWS: (NEWS_SAMPLE, ""), LATEST_GNSS: ({}, "")}


def test_only_files_their_owners_let_us_pass_on_are_offered():
    offered = {key for key, item in DATASETS.items() if item["offer"]}
    # NOTICE: orbit records keep Space-Track's and CelesTrak's terms; headlines belong to their publishers
    for key in ("news", "latest_gnss", "histories"):
        assert key not in offered and DATASETS[key]["why_not"]
    for key in offered:
        assert DATASETS[key]["licence"] not in ("spacetrack", "celestrak", "publishers"), key
    for item in DATASETS.values():
        assert item["licence"] in LICENCES and item["shelf"] in ("tables", "published", "others")
        assert item["what"] and item["how"] and item["left_out"]


def test_every_card_says_freshness_size_licence_and_credit():
    for key in DATASETS:
        content, size, fresh, problem = shelf.item_state(key, FILES)
        html = shelf.card_html(key, size, fresh, problem)
        for label in ("Fresh", "Size", "Licence", "Credit"):
            assert f"<i>{label}</i>" in html, (key, label)
        assert ("Not offered here" in html) != DATASETS[key]["offer"], key


def test_a_file_that_cannot_be_read_says_so_and_the_rest_still_show():
    _, _, _, problem = shelf.item_state("fitted", FILES)
    assert problem == "it cannot be read right now"
    assert "cannot be read right now" in shelf.card_html("fitted", None, "", problem)
    content, size, fresh, problem = shelf.item_state("orbit_gap", FILES)
    assert not problem and json.loads(content)["day"] == "2026-11-13" and fresh.startswith("made 13 Nov 2026 · the Orbit record check job")


def test_freshness_names_the_job_and_its_schedule():
    _, _, fresh, _ = shelf.item_state("counts", FILES)
    assert fresh.startswith("newest entry ") and "Registry update job, Sundays 01:00 UTC" in fresh
    assert "kept by hand" in shelf.item_state("lifecycles", FILES)[2]
    _, size, fresh, _ = shelf.item_state("histories", FILES)   # a large file not offered: its size, never its bytes
    assert size and fresh.startswith("made ") and "Update orbit data job" in fresh


def test_the_bundle_carries_each_file_with_its_licence_and_credit():
    offered = {}
    for key, item in DATASETS.items():
        content, _, fresh, _ = shelf.item_state(key, FILES)
        if item["offer"] and content is not None:
            offered[key] = (content, fresh)
    with zipfile.ZipFile(io.BytesIO(shelf.bundle(offered))) as archive:
        names = set(archive.namelist())
        readme = archive.read("README.txt").decode()
    assert {"NOTICE.txt", "LICENSE-DATA.txt", "catalogue.csv", "orbit_gap.json"} <= names
    assert "fitted_orbits.json" not in names   # it could not be read
    assert "latest_news.json" not in names and not any(name.endswith("_gp_history.json") for name in names)
    for key in offered:
        assert f"{shelf.file_name(key)}: {DATASETS[key]['name']}" in readme
        assert f"Credit: {LICENCES[DATASETS[key]['licence']][2]}" in readme


@pytest.fixture
def library_page(monkeypatch):
    """AppTest 1.45 reads a segmented control's single value as a list (as tests/test_dashboard_shell.py patches)."""
    def indices(self):
        chosen = self.value if isinstance(self.value, list) else [] if self.value is None else [self.value]
        return [self.options.index(self.format_func(v)) for v in chosen]
    monkeypatch.setattr(ButtonGroup, "indices", property(indices))

    def open_page(files):
        monkeypatch.setattr(shelf, "published", lambda: files)
        at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=600).run()
        at.switch_page("views/library.py").run()
        assert not at.exception, [e.value for e in at.exception]
        return at
    return open_page


def test_the_library_draws_every_shelf_with_its_downloads(library_page):
    at = library_page(FILES)
    page = "".join(part.proto.body for part in at.get("html"))
    for title, _, _ in SHELVES.values():
        assert f"<h2>{title} </h2>" in page
    labels = [button.proto.label for button in at.get("download_button")]
    assert "Download opengnss-library.zip" in labels and "Download orbit_gap.json" in labels
    assert "Download fitted_orbits.json" not in labels   # could not be read: said on its card instead
    assert "NVS-03 reaches its slot" in page
    assert any("Lifecycles" in box.label for box in at.checkbox)   # the lifecycle timelines are still on the page


def test_the_library_still_draws_when_the_news_cannot_be_read(library_page):
    at = library_page({**FILES, NEWS: ({}, "the news file could not be read")})
    page = "".join(part.proto.body for part in at.get("html"))
    assert "The stories cannot be read right now: the news file could not be read." in page
    assert "Download opengnss-library.zip" in [button.proto.label for button in at.get("download_button")]
