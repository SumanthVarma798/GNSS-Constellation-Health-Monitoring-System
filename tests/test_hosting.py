"""Hosting diagram (ui/components/hosting.*): the picture and its words agree, and nothing from them is markup."""
import json
import re

from ui.components import hosting as host

PAGE = host.PAGE_FILE.read_text()


def test_every_box_in_the_picture_has_its_words_and_every_part_has_a_box():
    assert set(re.findall(r'data-n="([a-z]+)"', PAGE)) == set(host.PARTS)


def test_each_part_says_what_it_is_its_details_its_limits_and_where_it_lives():
    for key, (name, kind, simple, tech, limits, where) in host.PARTS.items():
        assert kind in ("built", "planned", "key") and name and simple and tech and limits and where, key


def test_text_cannot_break_out_of_the_page_and_is_put_in_as_text():
    page = host.hosting_html(":root{}", "sans-serif")
    data = page[page.index("const DATA = ") + len("const DATA = "):page.index(";\nconst $")]
    assert "</script>" not in data and json.loads(data)["parts"]["dns"]["name"]
    assert "innerHTML" not in page and "textContent" in page
