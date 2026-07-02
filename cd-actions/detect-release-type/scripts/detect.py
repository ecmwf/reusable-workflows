#!/usr/bin/env python3
"""Detect release type from a git ref using tag regex patterns."""

from __future__ import annotations

import os
import re


def detect_release_type(
    ref_name: str,
    deployment_regex: str,
    prerelease_regex: str,
    dry_run_input: str,
) -> dict[str, str]:
    """Classify a ref as release, prerelease or dry run."""
    print(f"Analyzing ref: {ref_name}")

    if re.match(deployment_regex, ref_name):
        print("Standard release detected")
        is_dry_run = "false"
        is_prerelease = "false"
    elif re.match(prerelease_regex, ref_name):
        print("Pre-release detected")
        is_dry_run = "false"
        is_prerelease = "true"
    else:
        print("Dry run detected")
        is_dry_run = "true"
        is_prerelease = "false"

    if dry_run_input == "true":
        print("Explicit dry_run input enabled - forcing dry run mode")
        is_dry_run = "true"

    return {
        "ref_name": ref_name,
        "is_dry_run": is_dry_run,
        "is_prerelease": is_prerelease,
    }


def main():
    outputs = detect_release_type(
        os.environ["INPUT_REF_NAME"],
        os.environ["DEPLOYMENT_REGEX"],
        os.environ["PRERELEASE_REGEX"],
        os.environ["INPUT_DRY_RUN"],
    )

    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        for key, value in outputs.items():
            f.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
