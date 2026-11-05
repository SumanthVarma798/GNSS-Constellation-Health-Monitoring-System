"""Icons drawn in the dashboard's own pages: Tabler Icons 3.19.0, outline set, copied path for path.

Tabler Icons is MIT-licensed: Copyright (c) 2020-2024 Pawel Kuna, https://tabler.io/icons. Each icon is drawn on a
24 x 24 grid with stroke="currentColor", stroke-width 2 (or less), no fill. Only the paths are kept here; the page
builds the <svg> around them. To add one, copy its <path d="..."> values from the same version, leaving out the
invisible "M0 0h24v24H0z" frame.
"""

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
}

# Each lifecycle step's icon (the Library's lifecycles); a step not listed has none.
LIFECYCLE_STEP_ICONS = {"built": "tool", "launch": "rocket", "separation": "arrows-split-2", "burn": "flame",
                        "gso": "satellite", "slot": "satellite", "payload": "broadcast", "service": "broadcast",
                        "end": "power", "disposal": "trash", "note": "info-circle"}
