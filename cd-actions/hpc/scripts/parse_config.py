#!/usr/bin/env python3
"""Parse HPC build configuration and resolve platform/compiler settings."""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Mapping

from hpc_common import (
    DEFAULT_SITE,
    MODULE_TAG_RE,
    env_bool,
    load_platform_map,
    parse_stages,
    resolve_module_name,
)


def parse_hpc_config(
    env: Mapping[str, str],
    platform_map: dict[str, Any],
) -> dict[str, str]:
    """Compute the config step outputs from the INPUT_* environment."""
    platform = env["INPUT_PLATFORM"]
    if platform not in platform_map:
        print(f"::error::Unknown platform '{platform}'")
        print(f"Available platforms: {', '.join(platform_map.keys())}")
        sys.exit(1)

    compiler_info = platform_map[platform]

    use_staged = bool(parse_stages(env.get("INPUT_STAGES", "")))

    dry_run = env_bool("INPUT_DRY_RUN", env=env)
    dry_run_install = env_bool("INPUT_DRY_RUN_INSTALL", env=env)
    sync_module_input = env_bool("INPUT_SYNC_MODULE", True, env=env)
    site = env.get("INPUT_SITE", DEFAULT_SITE)
    do_sync = not dry_run and sync_module_input and site != "ag-batch"

    install_prefix_input = env.get("INPUT_INSTALL_PREFIX", "").strip()
    dry_run_install_prefix_input = env.get("INPUT_DRY_RUN_INSTALL_PREFIX", "").strip()
    # Validate and normalize module_tag_name
    raw_tag_name = env.get("INPUT_MODULE_TAG_NAME", "new").strip()
    if not raw_tag_name:
        module_tag_name = "new"
    elif MODULE_TAG_RE.match(raw_tag_name):
        module_tag_name = raw_tag_name
    else:
        print(f"::error::module_tag_name '{raw_tag_name}' contains invalid characters. Allowed: [A-Za-z0-9._-]")
        sys.exit(1)

    module_name = resolve_module_name(
        env.get("INPUT_MODULE_NAME", ""), env["GITHUB_REPOSITORY"]
    )
    ref_name = env["INPUT_REF_NAME"]
    safe_ref_name = ref_name.replace("/", "-")  # Sanitize for use in paths
    prefix_compiler_specific = env_bool("INPUT_PREFIX_COMPILER_SPECIFIC", env=env)

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

    return {
        "use_staged": "true" if use_staged else "false",
        "do_sync": "true" if do_sync else "false",
        "install_prefix": install_prefix,
        "base_install_prefix": base_install_prefix,
        "module_tag_name": module_tag_name,
        **{key: str(value) for key, value in compiler_info.items()},
    }


def main():
    platform_map = load_platform_map()

    outputs = parse_hpc_config(os.environ, platform_map)

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        for key, value in outputs.items():
            f.write(f"{key}={value}\n")

    print(f"Platform: {os.environ['INPUT_PLATFORM']}")
    print(f"Compiler: {outputs['compiler']}")
    print(f"Build mode: {'staged' if outputs['use_staged'] == 'true' else 'standard'}")
    print(f"Install prefix: {outputs['install_prefix']}")
    print(f"Module tag name: {outputs['module_tag_name']}")
    print(f"Do sync: {outputs['do_sync'] == 'true'}")


if __name__ == "__main__":
    main()
