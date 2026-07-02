#!/usr/bin/env python3
"""Parse conda build configuration."""

import os
import shlex
from pathlib import Path

import yaml


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() == "true"


def main():
    # Load Nexus URLs from config
    action_path = Path(os.environ["GITHUB_ACTION_PATH"])
    config_dir = action_path / "config"
    with open(config_dir / "nexus.yml") as f:
        nexus_config = yaml.safe_load(f)

    conda_dir = os.environ.get("INPUT_CONDA_DIR", "./.cd/conda")
    channels_input = os.environ.get(
        "INPUT_CHANNELS",
        # TEMPORARY: forward prod nexus -> test nexus (revert me)
        "conda-forge\nhttps://nexus-test.ecmwf.int/repository/conda-ecmwf-public",
    )
    platform = os.environ.get("INPUT_PLATFORM", "linux-64") or "linux-64"
    conda_build_args_input = os.environ.get("INPUT_CONDA_BUILD_ARGS", "")
    conda_build_args_list: list[str] = []
    for line in conda_build_args_input.splitlines():
        stripped = line.strip()
        if stripped:
            conda_build_args_list.extend(shlex.split(stripped))
    conda_build_args_list = [a for a in conda_build_args_list if a != "--no-anaconda-upload"]
    conda_build_args_list.append("--no-anaconda-upload")
    conda_build_args = " ".join(conda_build_args_list)

    # Parse line-separated channels
    channels_list = [c.strip() for c in channels_input.splitlines() if c.strip()]
    channels = f"-c {' -c '.join(channels_list)}" if channels_list else ""
    channels_csv = ",".join(channels_list)

    # Determine Nexus URL based on prerelease flag
    test_nexus = _bool_env("INPUT_TEST_NEXUS")
    if test_nexus:
        nexus_url = nexus_config["test"]["url"]
        nexus_token = os.environ.get("INPUT_NEXUS_TEST_TOKEN", "")
        print("Using test Nexus repository for pre-release")
    else:
        nexus_url = nexus_config["production"]["url"]
        nexus_token = os.environ.get("INPUT_NEXUS_TOKEN", "")
        print("Using production Nexus repository for standard release")

    meta_file = f"{conda_dir}/meta.yaml"
    output_folder = f"{conda_dir}/build"
    artifact_patterns = [f"{output_folder}/**/*.tar.bz2", f"{output_folder}/**/*.conda"]
    artifact_pattern = "\n".join(artifact_patterns)

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"meta_file={meta_file}\n")
        f.write(f"channels={channels}\n")
        f.write(f"channels_csv={channels_csv}\n")
        f.write(f"output_folder={output_folder}\n")
        f.write("artifact_pattern<<ARTIFACT_PATTERN_EOF\n")
        f.write(f"{artifact_pattern}\n")
        f.write("ARTIFACT_PATTERN_EOF\n")
        f.write(f"conda_build_args={conda_build_args}\n")
        f.write(f"platform={platform}\n")
        f.write(f"nexus_url={nexus_url}\n")
        f.write(f"nexus_token={nexus_token}\n")

    print(f"Conda dir: {conda_dir}")
    print(f"Meta file: {meta_file}")
    print(f"Channels: {channels}")
    print(f"Output folder: {output_folder}")
    print(f"Artifact pattern: {artifact_pattern}")
    print(f"Conda build args: {conda_build_args}")
    print(f"Target platform: {platform}")
    print(f"Nexus URL: {nexus_url}")


if __name__ == "__main__":
    main()
