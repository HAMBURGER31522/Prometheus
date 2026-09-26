"""Pi timeout formula: 1800 + 600 * ceil(hours) (PLAN 2.1)."""

import pytest

from prometheus.report.timing import pi_timeout_seconds


@pytest.mark.parametrize(("duration_s", "expected"), [
    (0, 1800),
    (0.5 * 3600, 2400),
    (3 * 3600, 3600),
    (10 * 3600, 7800),
    (3601, 3000),
])
def test_timeout_formula(duration_s, expected):
    assert pi_timeout_seconds(duration_s) == expected
