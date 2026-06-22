#!/usr/bin/env python3
"""Resolve a system-package OS alias to platform metadata."""

import os
import sys
from pathlib import Path

import yaml


def main() -> None:
    action_path = Path(os.environ["GITHUB_ACTION_PATH"])
    platforms_path = action_path.parent / "load-config" / "config" / "platforms-system-package.yml"

    with open(platforms_path) as f:
        platforms = yaml.safe_load(f)

    os_input = os.environ["INPUT_OS"]
    if os_input not in platforms:
        supported = ", ".join(sorted(platforms.keys()))
        print(f"::error::Unknown OS: {os_input}. Supported: {supported}")
        sys.exit(1)

    platform = platforms[os_input]
    os_id = platform["os"]
    container = f"eccr.ecmwf.int/platform-builder/platform-builder:{os_id}"

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"os={os_id}\n")
        f.write(f"container={container}\n")
        f.write(f"nexus_token_secret_prod={platform.get('nexus_token_secret_prod', '')}\n")
        f.write(f"nexus_url_secret_prod={platform.get('nexus_url_secret_prod', '')}\n")
        f.write(f"nexus_token_secret_test={platform['nexus_token_secret_test']}\n")
        f.write(f"nexus_url_secret_test={platform['nexus_url_secret_test']}\n")

    print(f"Resolved OS '{os_input}' to '{os_id}'")
    print(f"Container: {container}")


if __name__ == "__main__":
    main()
