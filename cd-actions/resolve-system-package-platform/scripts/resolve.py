#!/usr/bin/env python3
"""Resolve a system-package OS alias to platform metadata."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ACTION_PATH = Path(os.environ.get("GITHUB_ACTION_PATH", Path(__file__).parent.parent))
sys.path.insert(0, str(ACTION_PATH.parent / "lib"))

from cd_config import load_system_package_platforms
from system_package_platforms import (
    UnknownSystemPackagePlatform,
    resolve_system_package_platform,
)

OUTPUT_KEYS = (
    "os",
    "container",
    "nexus_token_secret_prod",
    "nexus_url_secret_prod",
    "nexus_token_secret_test",
    "nexus_url_secret_test",
)


def main() -> None:
    platforms = load_system_package_platforms()

    os_input = os.environ["INPUT_OS"]
    try:
        resolved = resolve_system_package_platform(os_input, platforms)
    except UnknownSystemPackagePlatform as exc:
        print(f"::error::Unknown OS: {exc.os_alias}. Supported: {exc.supported}")
        sys.exit(1)

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        for key in OUTPUT_KEYS:
            f.write(f"{key}={resolved[key]}\n")

    print(f"Resolved OS '{os_input}' to '{resolved['os']}'")
    print(f"Container: {resolved['container']}")


if __name__ == "__main__":
    main()
