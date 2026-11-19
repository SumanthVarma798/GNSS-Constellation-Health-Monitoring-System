"""A labelled link to the operator's official status page, for the constellations that have one."""
from html import escape

from ui import icons
from ui.official_status_settings import OFFICIAL_STATUS_URLS


def line(constellation):
    """Markup for an "Official status" link with an outward-arrow icon, opening the operator's page in a new tab, or ""
    for a constellation without a link."""
    url = OFFICIAL_STATUS_URLS.get(constellation)
    if not url:
        return ""
    return (f'<a class="chip accent ext" href="{escape(url, quote=True)}" target="_blank" rel="noopener" '
            f'title="{escape(url, quote=True)}">Official status{icons.mask("external-link")}</a>')
