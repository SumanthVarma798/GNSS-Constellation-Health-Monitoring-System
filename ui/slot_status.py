"""Shared slot-state words for UI chips."""

from ui import palette

CHIP_STATUS = {
    palette.SLOT_IN: "ok",
    palette.SLOT_OFF: "warn",
    palette.SLOT_LEFT: "bad",
    palette.SLOT_UNKNOWN: "idle",
}
