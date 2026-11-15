"""The systems as a reader meets them, and the parts of one that the dashboard judges separately.

A part is a key of ui.data.SATELLITES: what `scope` holds and every page reads. Most systems are one part.
BeiDou-3 is two: its high-orbit satellites are judged by longitude slot, its medium-orbit ones by orbital plane.
The reader chooses a system first; a system with parts then offers them, one step deeper.
"""
from ui import data

# {system: {part: what the part is called beside the system's name}}. A system not listed is its own one part.
PARTS = {"BeiDou-3": {"BeiDou-3": "IGSO & GEO", "BeiDou-3 MEO": "MEO"}}


def _systems():
    """{system: (its parts)}, in the order of ui.data.SATELLITES."""
    found = {}
    for part in data.SATELLITES:
        system = next((name for name, parts in PARTS.items() if part in parts), part)
        found[system] = found.get(system, ()) + (part,)
    return found


SYSTEMS = _systems()


def system_of(part):
    """The system a part belongs to."""
    return next(system for system, parts in SYSTEMS.items() if part in parts)


def part_name(part):
    """'MEO' for a part of a system with several; '' for a system that is one part."""
    return PARTS.get(system_of(part), {}).get(part, "")
