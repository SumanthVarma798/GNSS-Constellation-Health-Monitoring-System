"""The three map pictures: identity dial, succession lanes, agreement strip.

Each takes plain rows and returns HTML, so each is tested without a page.
"""

import re
from datetime import date

import pytest

from ui import palette
from ui.figures.agreement_strip import agreement_legend, agreement_strip
from ui.figures.identity_dial import identity_dial
from ui.figures.succession import MIN_BAR_WIDTH, date_to_x, succession_lanes, year_ticks

TODAY = "2026-10-12"
NASTY = "<script>alert(1)</script> & co"


def ident(n, status="ok"):
    return {"scheme": f"Scheme{n}", "value": f"Value{n}", "status": status, "remark": f"Remark{n}"}


# --- identity dial ---------------------------------------------------------

def test_dial_escapes_untrusted_text():
    html = identity_dial(NASTY, NASTY, [{"scheme": NASTY, "value": NASTY, "status": "ok", "remark": NASTY}])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp; co" in html


def test_dial_shows_master_id_and_every_field():
    items = [ident(n) for n in range(5)]
    html = identity_dial("C217", "BeiDou-3 G1", items)
    assert "C217" in html and "BeiDou-3 G1" in html
    for item in items:
        for key in ("scheme", "value", "remark"):
            assert item[key] in html


@pytest.mark.parametrize("count, left, right", [(1, 1, 0), (2, 1, 1), (3, 2, 1), (6, 3, 3), (7, 4, 3), (8, 4, 4)])
def test_dial_splits_first_half_left_rest_right(count, left, right):
    html = identity_dial("C1", "n", [ident(n) for n in range(count)])
    left_html, rest = html.split('<div class="idial-centre">')
    assert left_html.count('class="idial-tile"') == left
    assert rest.count('class="idial-tile"') == right
    assert "Scheme0" in left_html  # the first one is on the left


def test_dial_chip_status_is_a_class_and_words():
    html = identity_dial("C1", "n", [ident(0, "warn"), ident(1, "nonsense")])
    assert 'idial-chip idial-warn">Remark0' in html
    assert 'idial-chip idial-idle">Remark1' in html  # unknown status falls back to idle


def test_dial_stacks_on_narrow_screens_with_dial_first():
    html = identity_dial("C1", "n", [ident(0)])
    assert "@media (max-width:860px)" in html
    assert ".idial-centre { order:-1; }" in html


def test_dial_colours_come_from_the_palette_as_fallbacks():
    html = identity_dial("C1", "n", [ident(0)])
    assert f"var(--accent, {palette.ACCENT})" in html
    assert f"var(--ok, {palette.OK})" in html
    assert re.findall(r"var\(--[a-z-]+\)", html) == []  # every variable carries a fallback


# --- succession lanes ------------------------------------------------------

C01 = [
    {"label": "C003, BeiDou-2 G1", "start": "2010-01-16", "end": "2020-03-31", "current": False},
    {"label": "C020, BeiDou-2 G8", "start": "2020-03-31", "end": "2026-04-20", "current": False},
    {"label": "C231, BeiDou-3 G4", "start": "2026-04-20", "end": "", "current": True},
]
C217 = [
    {"label": "C59", "start": "2018-11-01", "end": "2026-03-31", "current": False},
    {"label": "C62", "start": "2026-03-31", "end": "2026-04-21", "current": False},
    {"label": "C04", "start": "2026-04-21", "end": "", "current": True},
]


def bars(html):
    """(x, width, fill) for each bar in the picture."""
    found = re.findall(r'<rect x="([\d.]+)" y="\d+" width="([\d.]+)" height="\d+" rx="[\d.]+" fill="(#\w+)"', html)
    return [(float(x), float(w), fill) for x, w, fill in found]


def test_date_to_x_is_proportional():
    first, last = date(2020, 1, 1), date(2022, 1, 1)
    assert date_to_x(first, first, last, 0, 100) == 0
    assert date_to_x(last, first, last, 0, 100) == 100
    assert date_to_x(date(2021, 1, 1), first, last, 0, 100) == pytest.approx(50, abs=0.2)


def test_half_the_span_is_about_half_the_axis():
    # Whole years, so the axis is exactly 2000-01-01 to 2002-01-01.
    periods = [{"label": "A", "start": "2000-01-01", "end": "2001-01-01", "current": False},
               {"label": "B", "start": "2001-01-01", "end": "2002-01-01", "current": False}]
    (x0, w0, _), (x1, w1, _) = bars(succession_lanes(periods, TODAY))
    assert w0 == pytest.approx(w1, rel=0.01)
    assert w0 == pytest.approx((500 - 20) / 2, rel=0.01)
    assert x1 == pytest.approx(x0 + w0, abs=0.2)


def test_open_ended_period_ends_at_today():
    html = succession_lanes([{"label": "A", "start": "2020-01-01", "end": "", "current": True}], TODAY)
    ((x, w, _),) = bars(html)
    # The axis runs to 1 Jan 2027, so today must be short of the right edge, in proportion.
    first, last = date(2020, 1, 1), date(2027, 1, 1)
    assert x + w == pytest.approx(date_to_x(date.fromisoformat(TODAY), first, last), abs=0.2)


def test_short_period_is_warn_and_at_least_five_wide():
    html = succession_lanes(C217, TODAY)
    _, (x, w, fill), _ = bars(html)
    assert fill == palette.WARN
    assert w >= MIN_BAR_WIDTH
    assert "C62, 21 days" in html  # said in words as well as colour


def test_current_is_accent_and_others_neutral():
    fills = [fill for _, _, fill in bars(succession_lanes(C01, TODAY))]
    assert fills == [palette.FILL, palette.FILL, palette.ACCENT]


def test_bars_alternate_rows():
    rows = re.findall(r'<rect x="[\d.]+" y="(\d+)"', succession_lanes(C01, TODAY))
    assert rows[0] == rows[2] != rows[1]


def test_narrow_bar_gets_its_label_outside_and_inside_the_picture():
    html = succession_lanes(C217, TODAY)
    outside = re.findall(r'<text x="([\d.]+)" y="\d+" fill="#\w+" font-size="13" text-anchor="end">([^<]+)', html)
    assert {t for _, t in outside} == {"C62, 21 days", "C04, since 21 Apr 2026"}
    for x, _ in outside:
        assert 0 < float(x) <= 520


def test_label_never_starts_left_of_the_axis():
    periods = [{"label": "A very long label indeed for a tiny bar", "start": "2000-01-01", "end": "2000-01-03",
                "current": False}, {"label": "B", "start": "2000-01-03", "end": "2020-01-01", "current": False}]
    html = succession_lanes(periods, TODAY)
    x, text = re.search(r'<text x="([\d.]+)"[^>]*text-anchor="end">([^<]+)', html).groups()
    assert float(x) - len(text) * 7.4 >= 20 - 0.1


def test_aria_label_names_every_period():
    html = succession_lanes(C01, TODAY)
    label = re.search(r'<svg[^>]*aria-label="([^"]+)"', html).group(1)
    assert 'role="img"' in html
    for text in ("C003, BeiDou-2 G1", "C020, BeiDou-2 G8", "C231, BeiDou-3 G4",
                 "16 Jan 2010", "31 Mar 2020", "20 Apr 2026", "current"):
        assert text in label


def test_ticks_are_four_to_nine_for_the_real_examples():
    for periods in (C01, C217):
        html = succession_lanes(periods, TODAY)
        years = re.findall(r'text-anchor="middle">(\d{4})<', html)
        assert 4 <= len(years) <= 9


def test_year_ticks_step_widens_with_the_span():
    assert year_ticks(date(2020, 1, 1), date(2025, 1, 1)) == [2020, 2021, 2022, 2023, 2024, 2025]
    assert len(year_ticks(date(1970, 1, 1), date(2027, 1, 1))) <= 9


def test_lanes_escape_untrusted_text_and_caption():
    html = succession_lanes([{"label": NASTY, "start": "2020-01-01", "end": "", "current": True}], TODAY, NASTY)
    assert "<script>" not in html
    assert html.count("&lt;script&gt;") >= 3  # aria-label, hover text, drawn label, caption


def test_lanes_use_palette_colours_only():
    html = succession_lanes(C217, TODAY)
    colours = set(re.findall(r'(?:fill|stroke)="(#\w+)"', html))
    allowed = {palette.ACCENT, palette.WARN, palette.FILL, palette.INK, palette.MUTED, palette.TRACK, palette.PLATFORM}
    assert colours <= allowed


def test_lanes_with_no_periods_say_so():
    assert "No periods" in succession_lanes([], TODAY)


# --- agreement strip -------------------------------------------------------

def strip_rows():
    rows = []
    for i in range(12):
        rows.append({"svn": f"C{i:03}", "constellation": "BeiDou", "identity": "confirmed",
                     "service": "agree" if i % 3 else "disagree", "remark": ""})
    for i in range(5):
        rows.append({"svn": f"G{i:03}", "constellation": "GPS", "identity": "confirmed",
                     "service": "not in the catalogue yet", "remark": "new"})
    rows.insert(3, {"svn": "G099", "constellation": "GPS", "identity": "", "service": "agree", "remark": ""})
    return rows


def test_strip_has_one_cell_per_row():
    rows = strip_rows()
    assert agreement_strip(rows).count('class="astrip-cell ') == len(rows)


def test_strip_groups_by_constellation_with_name_and_count():
    html = agreement_strip(strip_rows())
    assert html.count('class="astrip-group"') == 2
    assert "BeiDou, 12, 4 disagree" in html
    assert "GPS, 6" in html
    assert html.index("BeiDou, 12") < html.index("GPS, 6")  # order of first appearance
    # The out-of-order GPS row sits inside the GPS group, after the BeiDou group.
    assert html.index("G099") > html.index("GPS, 6")


def test_strip_colours_by_service_and_titles_say_it_in_words():
    html = agreement_strip(strip_rows())
    assert 'astrip-warn" title="C000 (BeiDou): sources disagree' in html
    assert 'astrip-ok" title="C001 (BeiDou): sources agree' in html
    assert 'astrip-idle" title="G000 (GPS): not in the catalogue yet. Identity: confirmed. new' in html
    assert f"var(--ok, {palette.OK})" in html


def test_strip_disagree_is_not_mistaken_for_agree():
    html = agreement_strip([{"svn": "X", "constellation": "C", "identity": "", "service": "Disagree: names", "remark": ""}])
    assert "astrip-warn" in html and "astrip-ok" not in html.split("</style>")[1]


def test_strip_escapes_untrusted_text():
    row = {"svn": NASTY, "constellation": NASTY, "identity": NASTY, "service": NASTY, "remark": NASTY}
    html = agreement_strip([row])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_legend_colours_come_from_the_palette():
    legend = agreement_legend()
    assert legend == [(palette.OK, "sources agree"), (palette.WARN, "sources disagree"),
                      (palette.IDLE, "not in the catalogue yet")]
