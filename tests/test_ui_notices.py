"""The notices inbox: notices leave the page for the bell, the bell counts the unread, and marking one read lasts."""
from streamlit.testing.v1 import AppTest


def page_with_notices():
    from ui import notices, surfaces

    notices.clear()
    surfaces.show(surfaces.notice("<b>No orbit data</b>: IRNSS-1D", "warn"))
    surfaces.show(surfaces.notice("Work in progress", "idle"))
    surfaces.show(surfaces.notice("Work in progress", "idle"))   # said twice, listed once
    surfaces.show(surfaces.notice("Could not load", "bad", inline=True))
    notices.inbox()


def bodies(at):
    return [part.proto.body for part in at.get("html")]


def test_notices_go_to_the_inbox_with_an_unread_count_and_a_blocking_one_stays_inline():
    at = AppTest.from_function(page_with_notices).run()

    assert not at.exception
    html = bodies(at)
    assert sum('class="notice bad"' in body and "Could not load" in body for body in html) == 1
    assert not any('class="notice warn"' in body for body in html)
    assert sum("Work in progress" in body for body in html) == 1
    assert any("&lt;b&gt;No orbit data&lt;/b&gt;" in body for body in html)   # escaped
    assert any('class="nt-count num warn"' in body and ">2<" in body for body in html)   # the worst unread's colour
    assert [b.label for b in at.button] == ["Mark read", "Mark read"]


def test_marking_every_notice_read_leaves_the_bell_quiet():
    at = AppTest.from_function(page_with_notices).run()
    at.button[0].click().run()
    at.button[1].click().run()

    html = bodies(at)
    assert not any("nt-count" in body for body in html)
    assert any('class="nt-row read"' in body and "Work in progress" in body for body in html)
    assert [b.label for b in at.button] == ["Mark unread", "Mark unread"]   # read notices keep their place

    at.button[1].click().run()   # and can be marked unread again
    assert any('class="nt-count num idle"' in body and ">1<" in body for body in bodies(at))
