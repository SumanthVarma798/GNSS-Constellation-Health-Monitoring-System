"""Shared words for who set a source grade and the note parser for graded_by."""
import re

CONSOLE_GRADED_BY_FORMAT = "{who} (from the console)"
_GRADE_NOTE = re.compile(r"\(([^()]*)\)")


def graded_by_console(who):
    """The graded_by text written for a console grade change."""
    return CONSOLE_GRADED_BY_FORMAT.format(who=who)


def grade_note(graded_by):
    """The bracketed note part of graded_by, or "" when none is present."""
    return match.group(1).strip() if (match := _GRADE_NOTE.search(graded_by or "")) else ""
