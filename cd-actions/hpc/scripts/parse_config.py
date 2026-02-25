#!/usr/bin/env python3
"""Parse HPC build configuration and resolve platform/compiler settings."""

import contextlib
import json
import os
import re
import sys
from pathlib import Path

import yaml


def main():
    # Load platform map from config file
    action_path = Path(os.environ["GITHUB_ACTION_PATH"])
    config_dir = action_path / "config"
    with open(config_dir / "platforms.yml") as f:
        platform_map = yaml.safe_load(f)

    platform = os.environ["INPUT_PLATFORM"]
    if platform not in platform_map:
        print(f"::error::Unknown platform '{platform}'")
        print(f"Available platforms: {', '.join(platform_map.keys())}")
        sys.exit(1)

    compiler_info = platform_map[platform]

    # Check if staged build (parse JSON to check for actual stages)
    stages_input = os.environ.get("INPUT_STAGES", "").strip()
    stages_list = []
    if stages_input:
        with contextlib.suppress(json.JSONDecodeError):
            stages_list = json.loads(stages_input)
    use_staged = bool(stages_list)

    dry_run = os.environ.get("INPUT_DRY_RUN", "false") == "true"
    dry_run_install = os.environ.get("INPUT_DRY_RUN_INSTALL", "false") == "true"
    sync_module_input = os.environ.get("INPUT_SYNC_MODULE", "true") == "true"
    site = os.environ.get("INPUT_SITE", "hpc-batch")
    do_sync = not dry_run and sync_module_input and site != "ag-batch"

    install_prefix_input = os.environ.get("INPUT_INSTALL_PREFIX", "").strip()
    dry_run_install_prefix_input = os.environ.get("INPUT_DRY_RUN_INSTALL_PREFIX", "").strip()
    repository = os.environ["GITHUB_REPOSITORY"]
    module_name = os.environ.get("INPUT_MODULE_NAME", "").strip() or repository.split("/")[-1]
    ref_name = os.environ["INPUT_REF_NAME"]
    safe_ref_name = ref_name.replace("/", "-")  # Sanitize for use in paths
    prefix_compiler_specific = os.environ.get("INPUT_PREFIX_COMPILER_SPECIFIC", "false") == "true"

    if install_prefix_input:
        install_prefix = install_prefix_input
    else:
        install_prefix = f"/usr/local/apps/{module_name}/{safe_ref_name}"

    if dry_run and dry_run_install:
        if not module_name:
            print("::error::dry_run_install requires a non-empty module_name")
            sys.exit(1)
        if not safe_ref_name:
            print("::error::dry_run_install requires a non-empty ref_name")
            sys.exit(1)
        if dry_run_install_prefix_input:
            install_prefix = dry_run_install_prefix_input
        else:
            install_prefix = "${SCRATCH}" + f"/dry-run-install/{module_name}/{safe_ref_name}"

    if prefix_compiler_specific:
        base_install_prefix = install_prefix
        parts = platform.split("-", 1)
        family = parts[0].upper()
        version_parts = parts[1].split(".")
        version = ".".join(version_parts[:2])
        install_prefix = f"{install_prefix}/{family}/{version}"
    else:
        base_install_prefix = install_prefix

    # Sanitize any install path under /usr/local/apps/ — resolve '..' and
    # symlinks, then verify the resolved path is at least <app>/<version> deep.
    for label, path in [("install_prefix", install_prefix), ("base_install_prefix", base_install_prefix)]:
        if path.startswith("/usr/local/apps/"):
            resolved = os.path.realpath(path)
            if not re.match(r"^/usr/local/apps/[^/]+/.+$", resolved):
                print(
                    f"::error::{label}: resolved path '{resolved}' (from '{path}') "
                    "is not deep enough — must be at least /usr/local/apps/<app>/<version>"
                )
                sys.exit(1)
    install_prefix = (
        os.path.realpath(install_prefix) if install_prefix.startswith("/usr/local/apps/") else install_prefix
    )
    base_install_prefix = (
        os.path.realpath(base_install_prefix)
        if base_install_prefix.startswith("/usr/local/apps/")
        else base_install_prefix
    )

    # Write outputs
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"use_staged={'true' if use_staged else 'false'}\n")
        f.write(f"do_sync={'true' if do_sync else 'false'}\n")
        f.write(f"install_prefix={install_prefix}\n")
        f.write(f"base_install_prefix={base_install_prefix}\n")
        for key, value in compiler_info.items():
            f.write(f"{key}={value}\n")

    print(f"Platform: {platform}")
    print(f"Compiler: {compiler_info['compiler']}")
    print(f"Build mode: {'staged' if use_staged else 'standard'}")
    print(f"Install prefix: {install_prefix}")
    print(f"Do sync: {do_sync}")


if __name__ == "__main__":
    main()
