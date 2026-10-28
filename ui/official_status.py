"""One small line to the operator's official status page, for the constellations that have one."""
from html import escape

from evidence.settings import OFFICIAL_STATUS_URLS


def line(constellation):
    """Markup for 'Official status: <link>', or "" for a constellation without a link."""
    url = OFFICIAL_STATUS_URLS.get(constellation)
    if not url:
        return ""
    return (f'<p class="small">Official status: '
            f'<a href="{escape(url)}" target="_blank" rel="noopener">{escape(url)}</a></p>')
