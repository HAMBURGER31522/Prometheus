"""Pi timeout formula (PLAN 2.1): 1800 + 600 * ceil(duration hours)."""

from math import ceil


def pi_timeout_seconds(duration_s: float) -> int:
    return 1800 + 600 * ceil(max(duration_s, 0.0) / 3600)
