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
"""

import sys
from pathlib import Path

WHITELIST = Path(".github/synced-files-whitelist.txt")
SYNC_FILES_URL = "https://github.com/ecmwf/reusable-workflows/tree/main/sync-files"
SYNC_CONFIG_URL = "https://github.com/ecmwf/reusable-workflows/blob/main/sync-files/sync.yml"


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


def main(filenames: list[str]) -> int:
    """Report staged synced files that are not whitelisted.

    Parameters
    ----------
    filenames : list[str]
        Paths passed by pre-commit.

    Returns
    -------
    int
        Exit code, 1 if a protected file was modified.
    """
    whitelist = read_whitelist(WHITELIST)
    protected = sorted({Path(name).as_posix() for name in filenames} - whitelist)
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
