#!/usr/bin/env python3
"""Parse the release section of a cd-config for the GitHub release step."""

from __future__ import annotations

import os

import yaml


def parse_release_config(config_yaml: str, ref_name: str) -> dict[str, str]:
    config = yaml.safe_load(config_yaml)

    release_config = config.get('release', {}).get('config', {})

    return {
        "release_name": release_config.get('name', f'Release {ref_name}'),
        "release_body": release_config.get('body', '## Changes\nSee the changelog for details.'),
        "prerelease": str(release_config.get('prerelease', False)).lower(),
        "draft": str(release_config.get('draft', False)).lower(),
        # Historical quirk kept as-is: an explicit YAML boolean renders as
        # Python's "True"/"False", while the default is the string "true".
        "make_latest": release_config.get('make_latest', 'true'),
    }


def main():
    outputs = parse_release_config(
        os.environ["INPUT_CONFIG"], os.environ["INPUT_REF_NAME"]
    )

    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f"release_name={outputs['release_name']}\n")
        f.write(f"prerelease={outputs['prerelease']}\n")
        f.write(f"draft={outputs['draft']}\n")
        f.write(f"make_latest={outputs['make_latest']}\n")
        # Handle multiline body
        f.write("release_body<<EOF\n")
        f.write(f"{outputs['release_body']}\n")
        f.write("EOF\n")

    print(f"Release name: {outputs['release_name']}")
    print(f"Prerelease: {outputs['prerelease']}")
    print(f"Draft: {outputs['draft']}")
    print(f"Make latest: {outputs['make_latest']}")


if __name__ == "__main__":
    main()
