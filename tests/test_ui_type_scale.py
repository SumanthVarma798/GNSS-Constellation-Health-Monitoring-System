"""The type scale: every level reaches the shared :root, and each size runs from its phone size to its desktop size."""
import re

from ui import type_scale
from ui.theme import root_block


def test_root_block_carries_every_type_token():
    root = root_block()
    for level in type_scale.LEVELS:
        for kind in ("fs", "fw", "fc"):
            assert f"--{kind}-{level}:" in root, f"{kind}-{level}"


def test_sizes_run_from_phone_to_desktop():
    for phone, desktop, _, _ in type_scale.LEVELS.values():
        low, base, slope, high = map(float, re.fullmatch(
            r"clamp\(([\d.]+)rem, ([\d.]+)rem \+ ([\d.]+)vw, ([\d.]+)rem\)", type_scale.fluid(phone, desktop)).groups())
        assert (low * 16, high * 16) == (phone, desktop)
        for width, want in ((type_scale.PHONE_PX, phone), (type_scale.DESKTOP_PX, desktop)):
            assert abs(base * 16 + slope * width / 100 - want) < 0.05


def test_levels_differ_in_more_than_size():
    looks = {(weight, colour) for _, _, weight, colour in type_scale.LEVELS.values()}
    assert len(looks) >= 4   # title and section share a look; the rest each have their own
