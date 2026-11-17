"""Words and mappings for the orbit-age section of the Overview."""

# Time-system correction codes from a RINEX header, in the order the orbit-age section reads them,
# with the plain words the dashboard shows. Values are stored as seconds and shown as nanoseconds.
TIME_CORRECTION_WORDS = {
    "GPUT": "GPS−UTC",
    "GAUT": "Galileo−UTC",
    "GAGP": "Galileo−GPS",
    "GLUT": "GLONASS−UTC",
    "BDUT": "BeiDou−UTC",
    "QZUT": "QZSS−UTC",
}
# QZSS broadcast health, IS-QZSS-PNT-005 section 4.1.2.3(4), Tables 4.1.2-5-1 and 4.1.2-5-2: six bits, one per
# signal, and a set bit means that signal must not be used. L1C/A and L1C/B are never sent at once, so one of the
# two is set on purpose when the other signal is sent.
QZSS_HEALTH_BITS = {32: "L1", 16: "L1C/A", 8: "L2C", 4: "L5", 2: "L1C", 1: "L1C/B"}
