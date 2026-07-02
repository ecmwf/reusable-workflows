#!/usr/bin/env python3
"""Check that the git tag matches the project version (VERSION or CMakeLists.txt)."""

from __future__ import annotations

import os
import re
import sys


def check_version():
    file_name = "VERSION"
    if os.path.isfile(file_name):
        with open(file_name, 'r') as f:
            version = f.read().strip()
            return version
    else:
        print(f"::warning::{file_name} file not found! Using {file_name} is the preferred method.")
        return


def check_cmakelists():
    file_name = "CMakeLists.txt"
    if os.path.isfile(file_name):
        with open(file_name, 'r') as f:
            content = f.read()
            pattern = r"project\([\s\w]+VERSION\s+((?:\d+)(?:.\d+){0,3})"

            hit = re.search(pattern, content)
            version = hit.group(1)
            return version
    else:
        print(f"::warning::{file_name} file not found!")
        return


def main():
    tag = os.environ["INPUT_REF_NAME"]

    version = check_version() or check_cmakelists()

    if not version:
        print("::error::Version not found!")
        sys.exit(1)

    if version != tag:
        print(f"::error::Git tag ({tag}) and project version ({version}) do not match!")
        sys.exit(1)

    print("OK: Git tag and project versions match.")


if __name__ == "__main__":
    main()
