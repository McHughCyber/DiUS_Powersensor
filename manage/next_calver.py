"""Compute the next CalVer release version (YYYY.MM.DD.N) from existing git tags."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import UTC
from datetime import datetime


def next_calver(
    tags: list[str],
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Return (version, tag) for the next CalVer release.

    Version format: YYYY.MM.DD.N (UTC date, build suffix starting at 0).
    Tag format: v{version}
    """
    moment = now or datetime.now(UTC)
    date_prefix = moment.strftime("%Y.%m.%d")
    pattern = re.compile(rf"^v{re.escape(date_prefix)}\.(\d+)$")

    build_numbers: list[int] = []
    for tag in tags:
        match = pattern.match(tag.strip())
        if match:
            build_numbers.append(int(match.group(1)))

    next_build = max(build_numbers, default=-1) + 1
    version = f"{date_prefix}.{next_build}"
    return version, f"v{version}"


def list_git_tags() -> list[str]:
    """Return all git tags from the current repository."""
    result = subprocess.run(
        ["git", "tag", "-l", "v*"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    """Print version and tag for the next CalVer release."""
    parser = argparse.ArgumentParser(description="Compute next CalVer release version.")
    parser.add_argument(
        "--format",
        choices=("version", "tag", "both"),
        default="both",
        help="Output version only, tag only, or both (default: both).",
    )
    args = parser.parse_args()

    version, tag = next_calver(list_git_tags())

    if args.format == "version":
        print(version)
    elif args.format == "tag":
        print(tag)
    else:
        print(f"version={version}")
        print(f"tag={tag}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
