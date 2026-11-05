"""Icons drawn in the dashboard's own pages: Tabler Icons 3.19.0, outline set, copied path for path.

Tabler Icons is MIT-licensed: Copyright (c) 2020-2024 Pawel Kuna, https://tabler.io/icons. Each icon is drawn on a
24 x 24 grid with stroke="currentColor", stroke-width 2 (or less), no fill. Only the paths are kept here; the page
builds the <svg> around them. To add one, copy its <path d="..."> values from the same version, leaving out the
invisible "M0 0h24v24H0z" frame.
"""

TABLER = {
    "map": ['M3 7l6 -3l6 3l6 -3v13l-6 3l-6 -3l-6 3v-13', 'M9 4v13', 'M15 7v13'],
    "click": ['M3 12l3 0', 'M12 3l0 3', 'M7.8 7.8l-2.2 -2.2', 'M16.2 7.8l2.2 -2.2', 'M7.8 16.2l-2.2 2.2',
              'M12 12l9 3l-4 2l-2 4l-3 -9'],
    "radar": ['M21 12h-8a1 1 0 1 0 -1 1v8a9 9 0 0 0 9 -9', 'M16 9a5 5 0 1 0 -7 7', 'M20.486 9a9 9 0 1 0 -11.482 11.495'],
    "player-play": ['M7 4v16l13 -8z'],
    "planet": ['M18.816 13.58c2.292 2.138 3.546 4 3.092 4.9c-.745 1.46 -5.783 -.259 -11.255 -3.838c-5.47 -3.579 '
               '-9.304 -7.664 -8.56 -9.123c.464 -.91 2.926 -.444 5.803 .805', 'M12 12m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0'],
}


def svg(name):
    """One icon as inline <svg>, in the text's colour. Hidden from screen readers: the words beside it say it."""
    paths = "".join(f'<path d="{d}"/>' for d in TABLER[name])
    return ('<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths}</svg>')
