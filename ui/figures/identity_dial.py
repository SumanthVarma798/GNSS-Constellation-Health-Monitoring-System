"""The identity dial: one master ID in the middle, every name it goes by around it.

Each identifier is a tile joined to the dial. The first half sits on the left,
the rest on the right. Below 860px wide everything stacks, dial first.
"""

from html import escape
from string import Template

from ui import palette
from ui.figures._themed import themed_all

STACK_BELOW_PX = 860
DIAL_PX = 190
DIAL_INNER_PX = 138
TILE_GAP_PX = 14
LINK_PX = 26
STATUSES = ("ok", "warn", "idle", "accent")
DEFAULT_STATUS = "idle"

_CSS = Template("""
.idial { display:grid; grid-template-columns:minmax(0,1fr) ${dial}px minmax(0,1fr); gap:0 ${link}px;
  align-items:center; color:$ink; font-family:${font}; }
.idial * { box-sizing:border-box; }
.idial-side { display:grid; gap:${tile_gap}px; min-width:0; }
.idial-tile { position:relative; min-width:0; border-radius:16px; box-shadow:$raised_sm;
  border:1px solid $edge; padding:10px 14px; background:$platform; }
.idial-scheme { font-size:12.5px; color:$muted; }
.idial-value { font-size:18px; font-weight:600; overflow-wrap:anywhere; }
.idial-chip { display:inline-flex; margin-top:4px; font-size:13px; font-weight:600; padding:3px 11px;
  border-radius:999px; box-shadow:$pressed; background:$well; }
.idial-ok { color:$ok; } .idial-warn { color:$warn; } .idial-idle { color:$idle; } .idial-accent { color:$accent; }
.idial-left .idial-tile::after, .idial-right .idial-tile::before { content:""; position:absolute; top:50%;
  width:${link}px; height:2px; background:linear-gradient(90deg,$sink,$lift); }
.idial-left .idial-tile::after { right:-${link_edge}px; }
.idial-right .idial-tile::before { left:-${link_edge}px; }
.idial-centre { display:grid; justify-items:center; gap:10px; }
.idial-dial { width:${dial}px; height:${dial}px; border-radius:50%; box-shadow:$raised;
  border:1px solid $edge; display:grid; place-items:center; background:$platform; }
.idial-dial > div { width:${inner}px; height:${inner}px; border-radius:50%; box-shadow:$pressed;
  background:$well; display:grid; place-items:center; text-align:center; padding:8px; }
.idial-mid { font-size:28px; font-weight:700; color:$accent; line-height:1; overflow-wrap:anywhere;
  font-family:${numbers}; }
.idial-cap { font-size:12px; color:$muted; margin-top:4px; }
.idial-name { font-size:14px; color:$muted; text-align:center; overflow-wrap:anywhere; }
@media (max-width:${stack}px) {
  .idial { grid-template-columns:minmax(0,1fr); gap:16px; }
  .idial-centre { order:-1; }
  .idial-side:empty { display:none; }
  .idial-tile::before, .idial-tile::after { display:none !important; }
}
""").substitute(
    themed_all(),
    dial=DIAL_PX, inner=DIAL_INNER_PX, tile_gap=TILE_GAP_PX, link=LINK_PX, link_edge=LINK_PX + 1,
    stack=STACK_BELOW_PX, font=palette.FONT, numbers=palette.FONT_NUMBERS,
)


def _tile(identifier):
    """One identifier as a tile: scheme in small text, value large, remark as a status chip."""
    status = identifier.get("status")
    status = status if status in STATUSES else DEFAULT_STATUS
    remark = identifier.get("remark", "")
    chip = f'<span class="idial-chip idial-{status}">{escape(remark)}</span>' if remark else ""
    return (
        '<div class="idial-tile">'
        f'<div class="idial-scheme">{escape(identifier["scheme"])}</div>'
        f'<div class="idial-value">{escape(identifier["value"])}</div>{chip}</div>'
    )


def _side(side, identifiers):
    """One column of tiles, side being left or right."""
    tiles = "".join(_tile(i) for i in identifiers)
    return f'<div class="idial-side idial-{side}">{tiles}</div>'


def identity_dial(master_id, name, identifiers):
    """Return HTML showing the master ID in a dial with every identifier as a tile around it."""
    split = (len(identifiers) + 1) // 2  # an odd one out goes left
    summary = f"Master ID {master_id}, {name}, with {len(identifiers)} identifiers"
    return (
        f"<style>{_CSS}</style>"
        f'<div class="idial" role="group" aria-label="{escape(summary)}">'
        f'{_side("left", identifiers[:split])}'
        '<div class="idial-centre"><div class="idial-dial"><div><div>'
        f'<div class="idial-mid">{escape(master_id)}</div><div class="idial-cap">master ID</div>'
        f'</div></div></div><div class="idial-name">{escape(name)}</div></div>'
        f'{_side("right", identifiers[split:])}'
        "</div>"
    )
