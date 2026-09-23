"""Nightly versions for CD builds.

Kept Python 3.6 compatible for the system-package build containers.
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

FORMATS = {
    # "~" sorts before the plain version in dpkg and rpm
    "system": "{next}~nightly.{stamp}.g{sha}",
    # PyPI rejects local versions, so no SHA
    "python": "{next}.dev{stamp}",
    "conda": "{next}.dev{stamp}",
}


def next_version(version: str) -> str:
    """Bump the last number of the release part: 2.49.0 -> 2.49.1, v6.0.0.0 -> 6.0.0.1."""
    match = re.match(r"v?(\d+(?:\.\d+)*)", version.strip())
    if not match:
        raise ValueError(f"Cannot derive a nightly version from '{version}'")
    parts = match.group(1).split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def current_version(repo: str = ".") -> str:
    """The VERSION file, or the nearest git tag."""
    path = os.path.join(repo, "VERSION")
    if os.path.isfile(path):
        with open(path) as f:
            version = f.read().strip()
        if version:
            return version
    return _git(repo, "describe", "--tags", "--abbrev=0")


def commit_stamp(repo: str = "."):
    """(YYYYMMDDHHMMSS commit time in UTC, short SHA) of HEAD."""
    commit_time, sha = _git(repo, "log", "-1", "--abbrev=7", "--format=%ct %h").split()
    stamp = datetime.fromtimestamp(int(commit_time), timezone.utc).strftime("%Y%m%d%H%M%S")
    return stamp, sha


def nightly_version(current: str, stamp: str, sha: str, style: str) -> str:
    return FORMATS[style].format(next=next_version(current), stamp=stamp, sha=sha)


def _git(repo: str, *args: str) -> str:
    # The checkout is owned by another user in job containers
    command = ("git", "-c", "safe.directory=*", "-C", repo) + args
    return subprocess.check_output(command, universal_newlines=True).strip()


def main():
    parser = argparse.ArgumentParser(description="Print the nightly version of the checked out commit")
    parser.add_argument("--style", choices=sorted(FORMATS), required=True)
    args = parser.parse_args()

    try:
        current = current_version()
        stamp, sha = commit_stamp()
        print(nightly_version(current, stamp, sha, args.style))
    except (ValueError, subprocess.CalledProcessError) as e:
        print(f"::error::Cannot determine the nightly version: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
