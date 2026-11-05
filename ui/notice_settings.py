"""The words of the notices inbox (ui/notices.py). Each status's icon is in ui/icons.py STATUS_ICONS."""

TITLE = "Notices"
EMPTY = "Nothing to read on this page."
MARK_READ = "Mark read"
MARK_UNREAD = "Mark unread"

# Said before each notice to a screen reader, which does not see the icon or its colour.
STATUS_WORDS = {"ok": "Fine", "warn": "Warning", "bad": "Problem", "idle": "Note", "accent": "New"}
# Worst first: the count on the bell takes the colour of the worst unread notice.
WORST_FIRST = ("bad", "warn", "accent", "idle", "ok")


def button_words(unread):
    """The bell's name for a screen reader: 'Notices, 3 unread', 'Notices, none unread'."""
    return f"{TITLE}, {unread or 'none'} unread"


def summary_words(unread, total):
    """The line under the panel's title: '2 unread of 5 on this page'."""
    return f"{unread} unread of {total} on this page"
