"""The look must stay readable: text and status colours against the platform they sit on."""
import pytest

from ui import palette


def luminance(colour):
    """Relative luminance of '#rrggbb', as the web accessibility guidelines (WCAG) define it."""
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one, other):
    lighter, darker = sorted((luminance(one), luminance(other)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("name", ["INK", "MUTED", "ACCENT", "OK", "WARN", "BAD", "IDLE"])
@pytest.mark.parametrize("surface", ["PLATFORM", "WELL"])
def test_text_and_status_colours_are_readable(name, surface):
    # 4.5 to 1 is the guideline's minimum for body text.
    assert contrast(getattr(palette, name), getattr(palette, surface)) >= 4.5, f"{name} on {surface}"


def test_every_slot_state_has_a_colour():
    assert set(palette.SLOT_COLOURS) == {palette.SLOT_IN, palette.SLOT_OFF, palette.SLOT_LEFT}
