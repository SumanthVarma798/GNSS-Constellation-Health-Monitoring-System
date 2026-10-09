"""Reading the IGS satellite metadata file (SINEX format).

The file is a set of blocks, each opened by '+SATELLITE/<NAME>' and closed by
'-SATELLITE/<NAME>'. Every data row starts with a space and the satellite's
SVN (space vehicle number), for example ' C217 '.
"""
import datetime
import re
from pathlib import Path

import requests

from evidence.settings import REQUEST_TIMEOUT_SECONDS
from evidence.sources import IGS_SATELLITE_METADATA_URL

OPEN_END = "0000:000:00000"  # the file's marker for "still valid"


def read_metadata(path=None):
    """The file's text: from a local copy if a path is given, otherwise downloaded."""
    if path:
        return Path(path).read_text()
    response = requests.get(IGS_SATELLITE_METADATA_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def block_rows(text, block):
    """The data rows of one block, for example block_rows(text, 'PRN')."""
    body = re.search(rf"^\+SATELLITE/{block}\s*$(.*?)^-SATELLITE/{block}", text, re.S | re.M)
    return [line for line in body.group(1).splitlines() if re.match(r" [A-Z]\d{3} ", line)]


def sinex_time(stamp):
    """'2026:090:46920' -> '2026-03-31T13:02:00Z'; the open-ended marker -> ''."""
    if stamp == OPEN_END:
        return ""
    year, day, seconds = map(int, stamp.split(":"))
    moment = datetime.datetime(year, 1, 1) + datetime.timedelta(days=day - 1, seconds=seconds)
    return moment.isoformat() + "Z"


def sinex_date(stamp):
    """'2026:111:43200' -> '2026-04-21'; the open-ended marker -> None."""
    return sinex_time(stamp)[:10] or None
