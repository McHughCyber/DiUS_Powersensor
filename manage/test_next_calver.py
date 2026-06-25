"""Tests for CalVer version computation."""

from datetime import UTC
from datetime import datetime

from manage.next_calver import next_calver


def test_first_release_of_day():
    """Use .0 when no tags exist for today."""
    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    version, tag = next_calver([], now=now)
    assert version == "2026.06.25.0"
    assert tag == "v2026.06.25.0"


def test_same_day_increment():
    """Increment build suffix for same-day tags."""
    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    tags = ["v2026.06.25.0", "v2026.06.25.1"]
    version, tag = next_calver(tags, now=now)
    assert version == "2026.06.25.2"
    assert tag == "v2026.06.25.2"


def test_new_day_resets_build_suffix():
    """Start at .0 on a new UTC day regardless of prior tags."""
    now = datetime(2026, 6, 26, 0, 1, tzinfo=UTC)
    tags = ["v2026.06.25.0", "v2026.06.25.9"]
    version, tag = next_calver(tags, now=now)
    assert version == "2026.06.26.0"
    assert tag == "v2026.06.26.0"


def test_ignores_non_matching_tags():
    """Ignore semver and other-day CalVer tags."""
    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    tags = ["v1.2.3", "v2026.06.24.0", "v2026.06.25.0"]
    version, tag = next_calver(tags, now=now)
    assert version == "2026.06.25.1"
    assert tag == "v2026.06.25.1"


def test_handles_gaps_in_build_numbers():
    """Use max existing suffix + 1 even when numbers are non-contiguous."""
    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    tags = ["v2026.06.25.0", "v2026.06.25.5"]
    version, tag = next_calver(tags, now=now)
    assert version == "2026.06.25.6"
    assert tag == "v2026.06.25.6"
