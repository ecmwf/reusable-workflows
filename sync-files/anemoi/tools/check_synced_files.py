# (C) Copyright 2026 Anemoi contributors.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
#
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.

"""Pre-commit hook that rejects changes to files synced from ecmwf/reusable-workflows.

This file is itself synced from https://github.com/ecmwf/reusable-workflows/tree/main/sync-files
The paths it guards are selected by the ``files`` regex of the ``protect-synced-files`` hook
in ``.pre-commit-config.yaml``. Paths listed in the whitelist are owned by this repository.

Only files that are actually changed are reported, so ``pre-commit run --all-files`` passes on a clean tree:

- with ``pre-commit run --from-ref A --to-ref B``: files changed between ``A`` and ``B``,
- otherwise: files with staged, unstaged or untracked changes relative to ``HEAD``.
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
    """Run a git command and return its non-empty output lines.

    Parameters
    ----------
    *args : str
        Arguments passed to ``git``.

    Returns
    -------
    list[str]
        Non-empty lines of stdout.
    """
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line]


def changed_files() -> set[str] | None:
    """Collect the files changed in the range or working tree that pre-commit checks.

    Returns
    -------
    set[str] | None
        Changed repository-relative paths, or ``None`` if they cannot be determined
        (e.g. no commit yet), in which case all passed files count as changed.
    """
    from_ref = os.environ.get("PRE_COMMIT_FROM_REF")
    to_ref = os.environ.get("PRE_COMMIT_TO_REF")
    try:
        if from_ref and to_ref:
            return set(git_lines("diff", "--name-only", f"{from_ref}...{to_ref}"))
        tracked = git_lines("diff", "--name-only", "HEAD")
        untracked = git_lines("ls-files", "--others", "--exclude-standard")
    except subprocess.CalledProcessError:
        return None
    return {*tracked, *untracked}


def read_whitelist(path: Path) -> set[str]:
    """Read the repository specific whitelist.

    Parameters
    ----------
    path : Path
        Whitelist file with one repository-relative path per line, ``#`` starts a comment.

    Returns
    -------
    set[str]
        Whitelisted paths, empty if the file does not exist.
    """
    if not path.is_file():
        return set()
    entries = (line.split("#", 1)[0].strip() for line in path.read_text().splitlines())
    return {Path(entry).as_posix() for entry in entries if entry}


def main(filenames: Sequence[str]) -> int:
    """Report changed synced files that are not whitelisted.

    Parameters
    ----------
    filenames : Sequence[str]
        Paths of synced files passed by pre-commit.

    Returns
    -------
    int
        Exit code, 1 if a protected file was modified.
    """
    candidates = {Path(name).as_posix() for name in filenames}
    changed = changed_files()
    if changed is not None:
        candidates &= changed
    protected = sorted(candidates - read_whitelist(WHITELIST))
    if not protected:
        return 0

    listing = "\n".join(f"  - {name}" for name in protected)
    message = f"""\
The following files are managed by {SYNC_FILES_URL}
and local changes to them are overwritten by the next sync:
{listing}

Either
  1. apply the change in sync-files of ecmwf/reusable-workflows, so it becomes global
     for all anemoi repositories, or
  2. if this repository needs its own version of the file, BOTH
     - add the path to {WHITELIST} in this repository, AND
     - exclude it for this repository in {SYNC_CONFIG_URL}
"""
    sys.stderr.write(message)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
