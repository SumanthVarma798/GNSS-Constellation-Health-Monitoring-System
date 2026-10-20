"""A satellite's score as a row of parts: one segment per part, filled to its score out of 100.

A part with no score is drawn as a hatched, empty segment, and the text under the bar
says which part is missing. Names and labels come from outside, so they are escaped.
The CSS is scoped with the prefix "sparts-" and falls back to palette colours when
the page has not defined the theme's variables.
"""
from html import escape

from ui import palette
from ui.tooltip import tip_html

_SHADOW_PRESSED = f"inset -3px -3px 7px {palette.LIFT}, inset 4px 4px 9px {palette.SINK}"

CSS = f"""
.sparts-card {{ font-family: {palette.FONT}; color: var(--ink, {palette.INK}); }}
.sparts-head {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 12px; margin: 0; font-size: 16px; }}
.sparts-score {{ font-family: {palette.FONT_NUMBERS}; font-size: 20px; font-weight: 700; }}
.sparts-status {{ font-size: 13px; font-weight: 600; padding: 3px 11px; border-radius: 999px;
  background: var(--well, {palette.WELL}); box-shadow: var(--pressed, {_SHADOW_PRESSED}); color: var(--muted, {palette.MUTED}); }}
.sparts-bar {{ display: flex; gap: 5px; height: 16px; margin: 8px 0 4px; }}
.sparts-bar > .tt, .sparts-bar .tt-trigger {{ flex: 1; display: flex; text-decoration: none; border-radius: 999px; }}
.sparts-seg {{ flex: 1; position: relative; overflow: hidden; border-radius: 999px;
  background: var(--well, {palette.WELL}); box-shadow: var(--pressed, {_SHADOW_PRESSED}); }}
.sparts-fill {{ position: absolute; inset: 0 auto 0 0; border-radius: 999px; background: var(--accent, {palette.ACCENT}); }}
.sparts-seg.sparts-missing {{ box-shadow: none; border: 1px dashed var(--idle, {palette.IDLE});
  background: repeating-linear-gradient(135deg, {palette.WELL} 0 5px, {palette.LIFT} 5px 10px); }}
.sparts-note {{ margin: 0; font-size: 14px; color: var(--muted, {palette.MUTED}); }}
"""


def _percent(score):
    return max(0.0, min(100.0, float(score)))


def _segment(label, score):
    if score is None:
        words = f"{label}: not scored"
        return tip_html('<span class="sparts-seg sparts-missing"></span>', escape(words)), words
    words = f"{label}: {score:g} out of 100"
    return tip_html(f'<span class="sparts-seg"><i class="sparts-fill" style="width:{_percent(score):g}%"></i></span>',
                    escape(words)), words


def score_parts(name, overall, status_text, parts):
    """HTML card: name, overall score, status in words, and one segment per part.

    parts is an ordered list of (label, score or None). overall may be None.
    """
    segments, words = zip(*(_segment(label, score) for label, score in parts)) if parts else ((), ())
    labels = ", ".join(label for label, _ in parts)
    missing = [label for label, score in parts if score is None]
    if missing:
        summary = f"{labels}. {len(parts) - len(missing)} of {len(parts)} parts scored. Not scored: {', '.join(missing)}."
    else:
        summary = f"{labels}. {len(parts)} parts."
    score_text = "no score" if overall is None else f"{overall:.1f}"
    return (
        f'<div class="sparts-card"><style>{CSS}</style>'
        f'<h3 class="sparts-head">{escape(name)} <span class="sparts-score">{escape(score_text)}</span> '
        f'<span class="sparts-status">{escape(status_text)}</span></h3>'
        f'<div class="sparts-bar" role="group" aria-label="{escape("; ".join(words))}">{"".join(segments)}</div>'
        f'<p class="sparts-note">{escape(summary)}</p></div>')
