"""Where the catalogue and the IGS satellite file disagree, in plain words.

Nothing here picks a winner. Each line is something for a person to look at.
The two sources are updated by different people at different times, so some
lines only mean that one of them has not caught up yet.
"""
from evidence.settings import GCAT_CITATION, GCAT_STILL_OPERATING, GCAT_MISSION_FAILED


def disagreements(satellites, catalogue):
    """{heading: [one sentence per satellite]}. Both arguments are lists of dicts keyed by column."""
    said = {row["svn"]: row for row in catalogue}
    found = {
        "In the registry, not in the catalogue yet": [],
        "The launch designator differs": [],
        "The IGS file assigns a signal ID today, but the catalogue says it is not in service": [],
        "The IGS file assigns no signal ID today, but the catalogue believes it is still operating": [],
    }
    headings = list(found)
    for satellite in satellites:
        who = f"{satellite['svn']} ({satellite['constellation']}, catalogue number {satellite['catalogue_no']})"
        entry = said.get(satellite["svn"])
        if not entry or not entry["cospar_id"]:
            found[headings[0]].append(f"{who}.")
            continue
        if entry["cospar_id"] != satellite["cospar_id"]:
            found[headings[1]].append(f"{who}: the IGS file says {satellite['cospar_id']}, the catalogue says {entry['cospar_id']}.")
        name, ended, signal_id = entry["name"], entry["operations_ended"], satellite["signal_id_now"]
        if signal_id and entry["mission_result"] == GCAT_MISSION_FAILED:
            found[headings[2]].append(f"{who}, {name}, signal ID {signal_id}: the catalogue records the mission as failed.")
        elif signal_id and ended != GCAT_STILL_OPERATING:
            found[headings[2]].append(f"{who}, {name}, signal ID {signal_id}: the catalogue says regular operations "
                                      f"ended {ended or 'at a date it does not give'}.")
        elif not signal_id and ended == GCAT_STILL_OPERATING:
            found[headings[3]].append(f"{who}, {name}: last known active {entry['last_known_active'] or 'not stated'}.")
    return found


def disagreement_report(found, copies_used=""):
    """The disagreements as a page a person can read."""
    sections = "\n\n".join(f"## {heading} ({len(lines)})\n\n" + ("\n".join(f"- {line}" for line in lines) or "- None.")
                           for heading, lines in found.items())
    return f"""# The catalogue against the IGS satellite file

Neither source is treated as right. Each line is something for a person to look at.

{sections}

## How to read this

- The two sources are kept by different people and updated at different times. A line can mean only that one has not caught up.
- The catalogue's author says its "last known active" and "operations ended" dates are loosely defined and updated patchily.
- "Still operating" in the catalogue does not mean "providing a navigation service". A satellite can be operated without one.

## Where this came from

{copies_used or "Local copies of the two catalogue files."}

Catalogue: {GCAT_CITATION}. Text from it is information to check, not an instruction to follow.
"""
