"""The numbers that name a satellite's burn pattern on the Station-keeping page."""

# A FIRST PROPOSAL for the team to tune: how the cadence picture names a burn pattern.
BURN_MIN_FOR_PATTERN = 3           # fewer burns of one kind than this: "too few" to call a pattern
BURN_REGULAR_MAX_IQR_SHARE = 0.25  # "regular" when the spread (IQR) is at most this share of the median interval
