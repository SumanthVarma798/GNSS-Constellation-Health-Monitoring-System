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

A source named in a card (SOURCE_LINKS in evidence/settings.py) becomes a link to it, dotted underlined and solid on
hover. The card stays open while the pointer is on it, so the link can be clicked.
"""
import hashlib
import re
from html import escape

from evidence.settings import SOURCE_LINKS
from ui import icons, palette, type_scale

# A legend swatch may only be a hex colour or one of the theme variables, nothing that could carry other CSS.
_SWATCH = re.compile(r"#[0-9a-fA-F]{3,8}|var\(--[a-z-]+\)")
# A source's name as a whole word (longest names first); a hyphen or letter beside it makes it part of another word.
_SOURCE_NAME = re.compile(r"(?<![\w-])(" + "|".join(re.escape(name) for name in sorted(SOURCE_LINKS, key=len, reverse=True)) + r")(?![\w-])")
_TAG = re.compile(r"(<[^>]*>)")

CARD_CSS = """
.tt-card { display: block; width: max-content; max-width: min(360px, calc(100vw - 32px)); padding: 12px 16px;
  background: var(--platform); color: var(--ink); border: 1px solid var(--edge); border-radius: var(--r);
  box-shadow: var(--raised); font-size: var(--fs-small); line-height: 1.45; font-weight: 400; text-align: left; white-space: normal;
  letter-spacing: normal; text-transform: none; z-index: 1000; pointer-events: none;
  opacity: 0; visibility: hidden; transition: opacity 150ms ease, visibility 0s linear 150ms; }
.tt-card.on, .tt:hover > .tt-card, .tt-trigger:focus + .tt-card, .tt > .tt-card:focus-within {
  opacity: 1; visibility: visible; transition: opacity 150ms ease 200ms, visibility 0s linear 200ms; }
/* An open card takes the pointer, so a link in it can be clicked; its edge reaches 10px over the gap to the trigger, so
   crossing the gap does not close it. The canvases' cards follow the pointer and stay out of its way. */
.tt:hover > .tt-card, .tt > .tt-card:focus-within { pointer-events: auto; }
.tt > .tt-card::before { content: ""; position: absolute; inset: -10px 0; z-index: -1; }
.tt-card a.tt-src { color: inherit; text-decoration: underline dotted; text-decoration-thickness: 1px; text-underline-offset: 3px; }
.tt-card a.tt-src:is(:hover, :focus-visible) { color: var(--accent); text-decoration-style: solid; }
"""


def _id(*parts):
    """The same text always gets the same id, so a page's markup does not change between runs."""
    return "tt-" + hashlib.sha1("\0".join(parts).encode("utf-8")).hexdigest()[:10]


def link_sources(body_html):
    """body_html with each source named in its words made a link to that source's page. Only the words between tags
    are touched, and none inside a link already."""
    parts, inside = _TAG.split(body_html), 0
    for at, part in enumerate(parts):
        if at % 2:   # a tag
            inside += 1 if re.match(r"<a[\s>]", part, re.I) else -1 if part[:3].lower() == "</a" else 0
        elif not inside:
            parts[at] = _SOURCE_NAME.sub(lambda found: (
                f'<a class="tt-src" href="{escape(SOURCE_LINKS[found.group(1)], quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{found.group(1)}</a>'), part)
    return "".join(parts)


def tip_html(trigger_html, body_html, pill=False, key=""):
    """The trigger and the card it opens. Set pill for a stand-alone control (a raised pill with a label);
    without it the trigger is a word or heading with a dotted underline. key tells apart the same tip shown
    more than once on a page, so each card's id is unique."""
    card = _id(trigger_html, body_html, key)
    kind = "tt-trigger pill" if pill else "tt-trigger"
    return (f'<span class="tt"><span class="{kind}" tabindex="0" aria-describedby="{card}">{trigger_html}</span>'
            f'<span class="tt-card" role="tooltip" id="{card}">{link_sources(body_html)}</span></span>')


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
