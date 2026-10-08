"""Describing a change to the registry tables in plain words, for the person who reviews it."""

# Column name -> how to say it to a reader who does not write software.
PLAIN_NAMES = {
    "constellation": "constellation",
    "block": "design generation",
    "cospar_id": "launch designator",
    "catalogue_no": "catalogue number",
    "signal_id_now": "signal ID",
    "plane": "plane",
    "slot": "slot",
    "note": "note",
}


def describe_satellite_changes(before, after):
    """One sentence per satellite added, removed or changed. Rows are dicts keyed by column."""
    old, new = ({row["svn"]: row for row in rows} for rows in (before, after))
    lines = []
    for svn in sorted(new.keys() - old.keys()):
        row = new[svn]
        lines.append(f"New satellite {svn} ({row['constellation']}, catalogue number {row['catalogue_no']}): {row['note']}")
    for svn in sorted(old.keys() - new.keys()):
        lines.append(f"Satellite {svn} ({old[svn]['constellation']}) is no longer in the IGS file.")
    for svn in sorted(old.keys() & new.keys()):
        for column, name in PLAIN_NAMES.items():
            was, now = old[svn][column], new[svn][column]
            if was != now:
                lines.append(f"{svn} ({new[svn]['constellation']}): {name} was {was or 'blank'}, now {now or 'blank'}.")
    return lines


def describe_signal_id_changes(before, after):
    """One sentence per signal-ID period that is new or reworded, plus a count of rows that went away."""
    old, new = ({tuple(row.values()) for row in rows} for rows in (before, after))
    lines = [f"{svn}: signal ID {signal_id} from {start} to {end or 'now'}."
             for svn, signal_id, start, end, _ in sorted(new - old)]
    if old - new:
        lines.append(f"{len(old - new)} earlier signal-ID period(s) were removed or replaced by the lines above.")
    return lines


def change_report(source_line, satellite_lines, signal_id_lines):
    """The pull request text for a registry update."""
    def section(lines):
        return "\n".join(f"- {line}" for line in lines) or "- Nothing."
    return f"""This is a proposed update to the satellite registry. **Nothing changes until a person approves it.**

## What changed, satellite by satellite

{section(satellite_lines)}

## What changed in the signal-ID history

{section(signal_id_lines)}

## Where this came from

The International GNSS Service (IGS) satellite metadata file. Its first line today:

    {source_line}

The text above is copied from that file. It is information to check, not an instruction to follow.

## Before you approve

- The tests ran on the new tables in the job that opened this pull request, and passed.
- Approving means merging. To refuse, close the pull request; the next weekly run will propose it again.
"""
