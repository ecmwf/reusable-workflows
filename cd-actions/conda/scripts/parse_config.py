#!/usr/bin/env python3
"""Parse conda build configuration."""

import os
from pathlib import Path

import yaml


def main():
    # Load Nexus URLs from config
    action_path = Path(os.environ["GITHUB_ACTION_PATH"])
    config_dir = action_path / "config"
    with open(config_dir / "nexus.yml") as f:
        nexus_config = yaml.safe_load(f)

    conda_dir = os.environ.get("INPUT_CONDA_DIR", "./.cd/conda")
    channels_input = os.environ.get("INPUT_CHANNELS", "conda-forge")
    conda_build_args = os.environ.get("INPUT_CONDA_BUILD_ARGS", "")

    # Parse comma-separated channels
    channels_list = [c.strip() for c in channels_input.split(",") if c.strip()]
    channels = f"-c {' -c '.join(channels_list)}" if channels_list else ""

    # Determine Nexus URL based on prerelease flag
    test_nexus = os.environ.get("INPUT_TEST_NEXUS", "false") == "true"
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
    artifact_pattern = f"{output_folder}/**/*.tar.bz2"

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"meta_file={meta_file}\n")
        f.write(f"channels={channels}\n")
        f.write(f"output_folder={output_folder}\n")
        f.write(f"artifact_pattern={artifact_pattern}\n")
        f.write(f"conda_build_args={conda_build_args}\n")
        f.write(f"nexus_url={nexus_url}\n")
        f.write(f"nexus_token={nexus_token}\n")

    print(f"Conda dir: {conda_dir}")
    print(f"Meta file: {meta_file}")
    print(f"Channels: {channels}")
    print(f"Output folder: {output_folder}")
    print(f"Artifact pattern: {artifact_pattern}")
    print(f"Conda build args: {conda_build_args}")
    print(f"Nexus URL: {nexus_url}")


if __name__ == "__main__":
    main()
