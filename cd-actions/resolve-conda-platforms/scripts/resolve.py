#!/usr/bin/env python3
"""Resolve Conda platform workflow input into a matrix."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ACTION_PATH = Path(os.environ.get("GITHUB_ACTION_PATH", Path(__file__).parent.parent))
sys.path.insert(0, str(ACTION_PATH.parent / "lib"))

from cd_config import conda_platforms_path
from conda_platforms import (
    load_conda_platforms_config,
    matrix_for_conda_platforms,
    matrix_summary_rows,
)


def main() -> None:
    name = os.environ.get("INPUT_NAME", "conda") or "conda"
    platforms = os.environ.get("INPUT_PLATFORMS", "linux-64")
    platform_config = load_conda_platforms_config(conda_platforms_path())

    try:
        matrix = matrix_for_conda_platforms(name, platforms, platform_config)
    except ValueError as exc:
        print(f"::error::{exc}")
        raise SystemExit(1) from exc

    print("Conda platform build plan:")
    print("| Build name | Requested platform | Conda platform | Runner | Artifact name |")
    print("| --- | --- | --- | --- | --- |")
    for row in matrix_summary_rows(matrix):
        print(
            f"| `{row['name']}` | `{row['conda_platform_key']}` | "
            f"`{row['conda_platform']}` | `{row['runner']}` | "
            f"`{row['artifact_name']}` |"
        )

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"matrix={json.dumps(matrix)}\n")


if __name__ == "__main__":
    main()
