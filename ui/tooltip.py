"""The one tooltip: a raised card that opens over a word, a heading or a pill, on every page.

It opens on hover (after a short delay), on keyboard focus, and on a tap (the tap focuses the trigger; a tap
elsewhere takes the focus away and closes it). The trigger points at the card with aria-describedby, so a screen
reader reads the card as the trigger's description. Placement is one rule, in ui/theme.css: under the trigger,
centred on it, slid along to stay inside the screen and flipped above it when there is no room below.

CARD_CSS is the card's look and its open and closed states. ui/theme.py puts it on every page and the two canvas
components (ui/components/master_map.html, orbit_view.html) put it in their own frames, so all three match:
their script adds the class "on" where the page uses hover and focus.

Text passed in is escaped; only parameters whose names end in _html are trusted to be markup already. Keep the
card's markup to spans when the tip sits inside a <p>: a <p>, <div> or <ul> there would end the paragraph early.
"""
import hashlib
import re
from html import escape

from ui import icons, palette, type_scale

# A legend swatch may only be a hex colour or one of the theme variables, nothing that could carry other CSS.
_SWATCH = re.compile(r"#[0-9a-fA-F]{3,8}|var\(--[a-z-]+\)")

CARD_CSS = """
.tt-card { display: block; width: max-content; max-width: min(360px, calc(100vw - 32px)); padding: 12px 16px;
  background: var(--platform); color: var(--ink); border: 1px solid var(--edge); border-radius: var(--r);
  box-shadow: var(--raised); font-size: var(--fs-small); line-height: 1.45; font-weight: 400; text-align: left; white-space: normal;
  letter-spacing: normal; text-transform: none; z-index: 1000; pointer-events: none;
  opacity: 0; visibility: hidden; transition: opacity 150ms ease, visibility 0s linear 150ms; }
.tt-card.on, .tt-trigger:hover + .tt-card, .tt-trigger:focus + .tt-card {
  opacity: 1; visibility: visible; transition: opacity 150ms ease 200ms, visibility 0s linear 200ms; }
"""


def _id(*parts):
    """The same text always gets the same id, so a page's markup does not change between runs."""
    return "tt-" + hashlib.sha1("\0".join(parts).encode("utf-8")).hexdigest()[:10]


def tip_html(trigger_html, body_html, pill=False, key=""):
    """The trigger and the card it opens. Set pill for a stand-alone control (a raised pill with a label);
    without it the trigger is a word or heading with a dotted underline. key tells apart the same tip shown
    more than once on a page, so each card's id is unique."""
    card = _id(trigger_html, body_html, key)
    kind = "tt-trigger pill" if pill else "tt-trigger"
    return (f'<span class="tt"><span class="{kind}" tabindex="0" aria-describedby="{card}">{trigger_html}</span>'
            f'<span class="tt-card" role="tooltip" id="{card}">{body_html}</span></span>')


def tip(trigger, text, pill=False, key=""):
    """A tip from plain words: both are escaped."""
    return tip_html(escape(trigger), escape(text), pill, key)


def glance(lead, items, note=""):
    """A card body read at a glance, for tip_html: a bold lead line, then one short line per item led by its key
    term in the accent colour, with an icon (ui/icons.py) before it where one is named, then an optional muted note.
    items: (icon name or "", key term, words). All text is escaped; spans only, so it can sit inside a <p>."""
    lines = "".join(f'<span class="tt-item">{icons.mask(icon) if icon else "<span></span>"}'
                    f'<span><b>{escape(term)}</b> {escape(words)}</span></span>' for icon, term, words in items)
    return (f'<span class="tt-lead">{escape(lead)}</span><span class="tt-items">{lines}</span>'
            + (f'<span class="tt-note">{escape(note)}</span>' if note else ""))


def legend(entries, label="Legend"):
    """A pill that opens a list of colours and what each means. entries: (colour, meaning) pairs."""
    rows = ""
    for colour, text in entries:
        if not _SWATCH.fullmatch(colour):
            raise ValueError(f"legend colour {colour!r} must be a hex colour or a var(--name)")
        rows += f'<li><span class="swatch" style="background:{colour}"></span>{escape(text)}</li>'
    return tip_html(escape(label), f'<ul class="tt-list">{rows}</ul>', pill=True)


# Plotly draws its own hover labels as SVG, so the card's look reaches them in three parts: PLOTLY_HOVER (every
# figure's layout.hoverlabel) sets the card's colours, typeface and size; plotly_card and plotly_line write the text in
# the card's order; ui/theme.css (".hoverlayer") adds the raised shadow, the padding and the rounded corners.
PLOTLY_HOVER = {"bgcolor": palette.PLATFORM, "bordercolor": palette.PLATFORM, "align": "left",
                "font": {"color": palette.INK, "family": palette.FONT, "size": type_scale.LEVELS["small"][1]}}


def plotly_line(label, value):
    """One "label value" line of a Plotly hover, the label muted. Escaped, as Plotly reads it as markup; Plotly's own
    placeholders (%{y:.2f}) pass through untouched."""
    return f'<span style="color:{palette.MUTED}">{escape(label)}</span>  {escape(value)}'


def plotly_card(title, *lines):
    """A Plotly hover in the card's order: the title in bold, then one plotly_line per (label, value)."""
    return "<br>".join([f"<b>{escape(title)}</b>", *(plotly_line(*line) for line in lines)])


def plotly_template(title, *lines):
    """plotly_card as a trace's hovertemplate, without Plotly's box for the trace's name."""
    return plotly_card(title, *lines) + "<extra></extra>"
