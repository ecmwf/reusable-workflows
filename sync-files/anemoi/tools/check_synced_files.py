# (C) Copyright 2026 Anemoi contributors.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
#
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.

"""Reject changes to files synced from ecmwf/reusable-workflows, unless whitelisted.

Changed means: between --from-ref and --to-ref if given, otherwise relative to HEAD.
"""

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

WHITELIST: Final[Path] = Path(".github/synced-files-whitelist")
SYNC_FILES_URL: Final[str] = "https://github.com/ecmwf/reusable-workflows/tree/main/sync-files"
SYNC_CONFIG_URL: Final[str] = "https://github.com/ecmwf/reusable-workflows/blob/main/sync-files/sync.yml"


def git_lines(*args: str) -> list[str]:
    """Return the non-empty output lines of a git command."""
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line]


def changed_files() -> set[str]:
    """Return the paths changed in the pre-commit ref range, or relative to HEAD incl. untracked files."""
    from_ref = os.environ.get("PRE_COMMIT_FROM_REF")
    to_ref = os.environ.get("PRE_COMMIT_TO_REF")
    if from_ref and to_ref:
        return set(git_lines("diff", "--name-only", f"{from_ref}...{to_ref}"))
    return {*git_lines("diff", "--name-only", "HEAD"), *git_lines("ls-files", "--others", "--exclude-standard")}


def read_whitelist() -> set[str]:
    """Return the whitelisted paths, one per line, `#` starts a comment."""
    if not WHITELIST.is_file():
        return set()
    entries = (line.split("#", 1)[0].strip() for line in WHITELIST.read_text().splitlines())
    return {Path(entry).as_posix() for entry in entries if entry}


def main(filenames: Sequence[str]) -> int:
    """Report changed, not whitelisted synced files."""
    protected = sorted(set(filenames) & changed_files() - read_whitelist())
    if not protected:
        return 0

    listing = "\n".join(f"  - {name}" for name in protected)
    sys.stderr.write(f"""\
The following files are managed by {SYNC_FILES_URL}
and local changes to them are overwritten by the next sync:
{listing}

Either
  1. apply the change in sync-files of ecmwf/reusable-workflows, so it becomes global
     for all anemoi repositories, or
  2. if this repository needs its own version of the file, BOTH
     - add the path to {WHITELIST} in this repository, AND
     - exclude it for this repository in {SYNC_CONFIG_URL}
""")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
