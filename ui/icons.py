"""Icons drawn in the dashboard's own pages: Tabler Icons 3.19.0, outline set, copied path for path.

Tabler Icons is MIT-licensed: Copyright (c) 2020-2024 Pawel Kuna, https://tabler.io/icons. Each icon is drawn on a
24 x 24 grid with stroke="currentColor", stroke-width 2 (or less), no fill. Only the paths are kept here; the page
builds the <svg> around them. To add one, copy its <path d="..."> values from the same version, leaving out the
invisible "M0 0h24v24H0z" frame.

st.html drops inline <svg>, so the pages draw an icon as a mask instead: ui/theme.py puts each icon in MASKED on
the page as a CSS variable, --ic-<name>, and tag() is the span that shows one in its status colour.
"""
import base64

TABLER = {
    "tool": ['M7 10h3v-3l-3.5 -3.5a6 6 0 0 1 8 8l6 6a2 2 0 0 1 -3 3l-6 -6a6 6 0 0 1 -8 -8l3.5 3.5'],
    "rocket": ['M4 13a8 8 0 0 1 7 7a6 6 0 0 0 3 -5a9 9 0 0 0 6 -8a3 3 0 0 0 -3 -3a9 9 0 0 0 -8 6a6 6 0 0 0 -5 3', 'M7 14a6 6 0 0 0 -3 6a6 6 0 0 0 6 -3', 'M15 9m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0'],
    "arrows-split-2": ['M21 17h-5.397a5 5 0 0 1 -4.096 -2.133l-.514 -.734a5 5 0 0 0 -4.096 -2.133h-3.897', 'M21 7h-5.395a5 5 0 0 0 -4.098 2.135l-.51 .73a5 5 0 0 1 -4.097 2.135h-3.9', 'M18 10l3 -3l-3 -3', 'M18 20l3 -3l-3 -3'],
    "flame": ['M12 12c2 -2.96 0 -7 -1 -8c0 3.038 -1.773 4.741 -3 6c-1.226 1.26 -2 3.24 -2 5a6 6 0 1 0 12 0c0 -1.532 -1.056 -3.94 -2 -5c-1.786 3 -2.791 3 -4 2z'],
    "satellite": ['M3.707 6.293l2.586 -2.586a1 1 0 0 1 1.414 0l5.586 5.586a1 1 0 0 1 0 1.414l-2.586 2.586a1 1 0 0 1 -1.414 0l-5.586 -5.586a1 1 0 0 1 0 -1.414z', 'M6 10l-3 3l3 3l3 -3', 'M10 6l3 -3l3 3l-3 3', 'M12 12l1.5 1.5', 'M14.5 17a2.5 2.5 0 0 0 2.5 -2.5', 'M15 21a6 6 0 0 0 6 -6'],
    "broadcast": ['M18.364 19.364a9 9 0 1 0 -12.728 0', 'M15.536 16.536a5 5 0 1 0 -7.072 0', 'M12 13m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0'],
    "power": ['M7 6a7.75 7.75 0 1 0 10 0', 'M12 4l0 8'],
    "trash": ['M4 7l16 0', 'M10 11l0 6', 'M14 11l0 6', 'M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12', 'M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3'],
    "info-circle": ['M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0', 'M12 9h.01', 'M11 12h1v4h1'],
    "maximize": ['M4 8v-2a2 2 0 0 1 2 -2h2', 'M4 16v2a2 2 0 0 0 2 2h2', 'M16 4h2a2 2 0 0 1 2 2v2', 'M16 20h2a2 2 0 0 0 2 -2v-2'],
    "chevron-down": ['M6 9l6 6l6 -6'],
    "chevron-up": ['M6 15l6 -6l6 6'],
    "search": ['M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0', 'M21 21l-6 -6'],
    "map": ['M3 7l6 -3l6 3l6 -3v13l-6 3l-6 -3l-6 3v-13', 'M9 4v13', 'M15 7v13'],
    "click": ['M3 12l3 0', 'M12 3l0 3', 'M7.8 7.8l-2.2 -2.2', 'M16.2 7.8l2.2 -2.2', 'M7.8 16.2l-2.2 2.2',
              'M12 12l9 3l-4 2l-2 4l-3 -9'],
    "radar": ['M21 12h-8a1 1 0 1 0 -1 1v8a9 9 0 0 0 9 -9', 'M16 9a5 5 0 1 0 -7 7', 'M20.486 9a9 9 0 1 0 -11.482 11.495'],
    "player-play": ['M7 4v16l13 -8z'],
    "planet": ['M18.816 13.58c2.292 2.138 3.546 4 3.092 4.9c-.745 1.46 -5.783 -.259 -11.255 -3.838c-5.47 -3.579 '
               '-9.304 -7.664 -8.56 -9.123c.464 -.91 2.926 -.444 5.803 .805', 'M12 12m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0'],
    "bell": ['M10 5a2 2 0 1 1 4 0a7 7 0 0 1 4 6v3a4 4 0 0 0 2 3h-16a4 4 0 0 0 2 -3v-3a7 7 0 0 1 4 -6', 'M9 17v1a3 3 0 0 0 6 0v-1'],
    "alert-triangle": ['M12 9v4', 'M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z', 'M12 16h.01'],
    "alert-circle": ['M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0', 'M12 8v4', 'M12 16h.01'],
    "circle-check": ['M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0', 'M9 12l2 2l4 -4'],
    "check": ['M5 12l5 5l10 -10'],
    "calculator": ['M4 3m0 2a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v14a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2z', 'M8 7m0 1a1 1 0 0 1 1 -1h6a1 1 0 0 1 1 1v1a1 1 0 0 1 -1 1h-6a1 1 0 0 1 -1 -1z', 'M8 14l0 .01', 'M12 14l0 .01', 'M16 14l0 .01', 'M8 17l0 .01', 'M12 17l0 .01', 'M16 17l0 .01'],
    "hourglass": ['M6.5 7h11', 'M6.5 17h11', 'M6 20v-2a6 6 0 1 1 12 0v2a1 1 0 0 1 -1 1h-10a1 1 0 0 1 -1 -1z', 'M6 4v2a6 6 0 1 0 12 0v-2a1 1 0 0 0 -1 -1h-10a1 1 0 0 0 -1 1z'],
    "coin": ['M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0', 'M14.8 9a2 2 0 0 0 -1.8 -1h-2a2 2 0 1 0 0 4h2a2 2 0 1 1 0 4h-2a2 2 0 0 1 -1.8 -1', 'M12 7v10'],
    "database": ['M12 6m-8 0a8 3 0 1 0 16 0a8 3 0 1 0 -16 0', 'M4 6v6a8 3 0 0 0 16 0v-6', 'M4 12v6a8 3 0 0 0 16 0v-6'],
}

# Each lifecycle step's icon (the Library's lifecycles); a step not listed has none.
LIFECYCLE_STEP_ICONS = {"built": "tool", "launch": "rocket", "separation": "arrows-split-2", "burn": "flame",
                        "gso": "satellite", "slot": "satellite", "payload": "broadcast", "service": "broadcast",
                        "end": "power", "disposal": "trash", "note": "info-circle"}


# Each status's icon (ui/surfaces.py STATUSES), in the notices inbox and in what the checks found.
STATUS_ICONS = {"ok": "circle-check", "warn": "alert-triangle", "bad": "alert-circle", "idle": "info-circle",
                "accent": "info-circle"}
# The icons the stylesheet carries as --ic-<name>: the inbox's bell, its "mark read" tick, the status icons, and the
# Sky and ground card's (ui/geometry_settings.py SKY_GROUND_KEY), the Library's. An icon a page shows must be here.
MASKED = ("bell", "check", *dict.fromkeys(STATUS_ICONS.values()), "map", "click", "radar", "player-play", "planet",
          # the Library's column help (evidence/library_settings.py LIBRARY_COLUMN_HELP)
          "rocket", "power", "broadcast", "calculator", "hourglass", "coin", "database")


def mask_url(name):
    """The icon as a CSS url() of an SVG data URI, for a mask. Base64, so the style block holds no angle bracket."""
    paths = "".join(f'<path d="{d}"/>' for d in TABLER[name])
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2" '
           f'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')
    return f'url("data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode("ascii")}")'


def mask(name, cls=""):
    """One icon in MASKED as a span in the text's colour. Hidden from screen readers: the words beside it say it."""
    return f'<span class="ic{" " + cls if cls else ""}" style="--ic: var(--ic-{name})" aria-hidden="true"></span>'


def tag(status):
    """A status's icon as a span in the status's colour. Hidden from screen readers: say the status in words too."""
    return mask(STATUS_ICONS[status], status)
