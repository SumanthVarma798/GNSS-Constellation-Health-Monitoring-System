"""Puts the dashboard's look on a page.

Every colour comes from ui/palette.py, every text size from ui/type_scale.py. The rules that use them are in ui/theme.css.
The reader picks the theme in Settings (ui/shell.py): System follows the computer's own light or dark setting.
"""
import json
from pathlib import Path

from ui import icons, marks, palette, type_scale
from ui.tooltip import CARD_CSS

CSS_FILE = Path(__file__).with_name("theme.css")

# The faint light edge on raised things. Not a palette colour: it is white at low strength.
EDGE = "rgba(255,255,255,.06)"
LIGHT_EDGE = "rgba(255,255,255,.7)"

# The theme choice, kept in st.session_state[SCHEME_KEY] and in the address (?theme=), so a reload keeps it.
SCHEME_KEY = "theme"
SCHEMES = {"system": ":material/brightness_auto: System", "light": ":material/light_mode: Light",
           "dark": ":material/dark_mode: Dark"}

# CSS variable name -> value. The shadows are written in terms of the colour variables; the type scale follows.
VARIABLES = {
    "platform": palette.PLATFORM,
    "lift": palette.LIFT,
    "sink": palette.SINK,
    "well": palette.WELL,
    "track": palette.TRACK,
    "fill": palette.FILL,
    "ink": palette.INK,
    "muted": palette.MUTED,
    "accent": palette.ACCENT,
    "ok": palette.OK,
    "warn": palette.WARN,
    "bad": palette.BAD,
    "idle": palette.IDLE,
    "edge": EDGE,
    "raised": "-6px -6px 14px var(--lift), 7px 7px 16px var(--sink)",
    "raised-sm": "-3px -3px 8px var(--lift), 4px 4px 10px var(--sink)",
    "pressed": "inset -3px -3px 7px var(--lift), inset 4px 4px 9px var(--sink)",
    "r": f"{palette.RADIUS_PX}px",
    **type_scale.variables(),
    # Icons for CSS masks (ui/icons.py): --ic-bell and the rest.
    **{f"ic-{name}": icons.mask_url(name) for name in icons.MASKED},
    # Each constellation's mark for CSS masks (ui/marks.py): --mk-navic and the rest.
    **{f"mk-{key.lower()}": marks.mask_url(key) for key in marks.SHAPES},
}


LIGHT_VARIABLES = {**palette.LIGHT, "edge": LIGHT_EDGE}


def chosen_scheme():
    """The reader's theme: 'system', 'light' or 'dark'."""
    import streamlit as st

    choice = st.session_state.get(SCHEME_KEY)
    return choice if choice in SCHEMES else "system"


def _block(values, look, scheme):
    lines = "".join(f"  --{name}: {value};\n" for name, value in values.items())
    # --theme says which choice the page has drawn; the crossfade (FADE_JS) waits for it.
    # --look carries the scheme to the component frames (ui/theme.css), as Streamlit's wrappers say "dark" whatever this says.
    return f":root {{\n  color-scheme: {look};\n  --look: {look};\n  --theme: {scheme};\n{lines}}}\n"


def root_block(scheme=None):
    """The :root rules that define every variable, for `scheme` (by default the reader's choice). System gives the
    dark values, and the light ones when the computer is set to light. The canvas components take the same rules."""
    scheme = scheme or chosen_scheme()
    dark, light = _block(VARIABLES, "dark", scheme), _block(LIGHT_VARIABLES, "light", scheme)
    if scheme == "light":   # the light block holds only colours: everything else comes from the first
        return dark + light
    if scheme == "system":
        return dark + "@media (prefers-color-scheme: light) {\n" + light + "}\n"
    return dark


def figure_rules():
    """Plotly writes the dark palette's colours into its SVG as rgb(); each is put back as its variable, so a figure
    follows the theme (and the computer, under System) without being drawn again. The 3D figure is WebGL and keeps the
    dark colours."""
    rules = ""
    # Ours, then the text colours Streamlit's own Plotly template writes where a figure sets none (ticks, legend).
    for colour, name in [(VARIABLES[name], name) for name in palette.LIGHT] + [("#e6eaf1", "ink"), ("#fafafa", "ink")]:
        red, green, blue = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
        for part in ("fill", "stroke"):
            rules += (f'.js-plotly-plot [style*="{part}: rgb({red}, {green}, {blue})"] '
                      f"{{ {part}: var(--{name}) !important; }}\n")
    return rules


def font_rules():
    """Typefaces, taken from the palette so no font is named twice."""
    return (
        f'.stApp, [data-testid="stSidebar"], button, input, textarea {{ font-family: {palette.FONT}; }}\n'
        f'.num, .big, [data-testid="stMetricValue"] {{ font-family: {palette.FONT_NUMBERS}; }}\n'
    )


def theme_css():
    """The full stylesheet text: variables, typefaces, the tooltip's card (shared with the canvas components), the rules."""
    return root_block() + font_rules() + figure_rules() + CARD_CSS + CSS_FILE.read_text(encoding="utf-8")


# The change of theme as a crossfade. A click on the theme choice starts a view transition: the browser keeps showing
# the page as it was while the page is drawn again in the new theme (--theme reaches the choice, then the page is quiet
# for a moment), then fades one into the other. Browsers without view transitions, and readers who ask for less
# motion, get the change straight away. It runs in the page itself (put there once from an empty component frame), as
# a frame's own script stops when Streamlit removes the frame.
FADE_JS = """
document.addEventListener("click", (event) => {
  const button = event.target.closest(".st-key-theme button");
  if (!button || !document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const wanted = button.innerText.trim().split(/\\s+/).pop().toLowerCase();
  document.startViewTransition(() => new Promise((done) => {
    let quiet;
    const watch = new MutationObserver(() => { clearTimeout(quiet); quiet = setTimeout(stop, 200); });
    const stop = () => { watch.disconnect(); clearTimeout(quiet); clearTimeout(cap); clearInterval(look); done(); };
    const cap = setTimeout(stop, 2000);   // ponytail: a fixed wait; a slow rerun past it switches without the fade
    const look = setInterval(() => {
      if (getComputedStyle(document.documentElement).getPropertyValue("--theme").trim() !== wanted) return;
      clearInterval(look);
      watch.observe(document.body, {subtree: true, childList: true, attributes: true, characterData: true});
      quiet = setTimeout(stop, 200);
    }, 40);
  }));
}, true);
"""
FADE_FRAME = ("<script>const doc = window.parent.document; if (!doc.getElementById('theme-fade')) {"
              " const s = doc.createElement('script'); s.id = 'theme-fade';"
              f" s.textContent = {json.dumps(FADE_JS)}; doc.head.appendChild(s); }}</script>")


def apply_theme():
    """Put the stylesheet on the current page. Call once, near the top of the page."""
    import streamlit as st
    from streamlit.components.v1 import html

    if SCHEME_KEY not in st.session_state:
        # A page change drops the widget's own state; ui/shell.py segment keeps a copy. A new visit has only the address.
        asked = st.session_state.get(f"_{SCHEME_KEY}_was") or st.query_params.get(SCHEME_KEY)
        st.session_state[SCHEME_KEY] = asked if asked in SCHEMES else "system"
    scheme = chosen_scheme()
    if scheme == "system":
        st.query_params.pop(SCHEME_KEY, None)
    else:
        st.query_params[SCHEME_KEY] = scheme
    st.html(f"<style>{theme_css()}</style>")
    with st.container(key="theme_fade"):
        html(FADE_FRAME, height=0)
