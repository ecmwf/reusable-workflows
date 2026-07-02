"""Shared Conda platform parsing and matrix expansion helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

# Keep in sync with conda.platforms in cd-actions/config/defaults.yml.
DEFAULT_CONDA_PLATFORMS = ["linux-64"]


def load_conda_platforms_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Conda platform config must be a mapping: {path}")
    return config


def parse_conda_platforms(value: Any) -> list[str]:
    if value is None:
        raw_platforms: list[Any] = DEFAULT_CONDA_PLATFORMS.copy()
    elif isinstance(value, list):
        raw_platforms = value
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raw_platforms = DEFAULT_CONDA_PLATFORMS.copy()
        else:
            parsed: Any = None
            if stripped.startswith("[") or stripped.startswith("-"):
                try:
                    parsed = yaml.safe_load(stripped)
                except yaml.YAMLError:
                    parsed = None
            if isinstance(parsed, list):
                raw_platforms = parsed
            else:
                raw_platforms = stripped.splitlines()
    else:
        raise ValueError("Conda platforms must be a list or line-separated string")

    platforms: list[str] = []
    seen: set[str] = set()
    for item in raw_platforms:
        platform = str(item).strip()
        if not platform or platform in seen:
            continue
        platforms.append(platform)
        seen.add(platform)

    return platforms or DEFAULT_CONDA_PLATFORMS.copy()


def validate_conda_platforms(
    platforms: list[str], platform_config: dict[str, Any]
) -> list[str]:
    supported = list(platform_config.keys())
    for platform in platforms:
        if platform not in platform_config:
            raise ValueError(
                f"Unsupported Conda platform '{platform}'. Supported: {', '.join(supported)}"
            )
    return platforms


def resolve_conda_platforms(value: Any, platform_config: dict[str, Any]) -> list[str]:
    """Parse and validate a Conda platforms value."""
    return validate_conda_platforms(parse_conda_platforms(value), platform_config)


def conda_platform_matrix_entries(
    name: str,
    platforms: list[str],
    platform_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create matrix entries for a Conda build name and requested platforms."""
    multi_platform = len(platforms) > 1
    entries: list[dict[str, Any]] = []

    for platform in platforms:
        metadata = platform_config[platform]
        entries.append(
            {
                "name": f"{name}-{platform}" if multi_platform else name,
                "type": "conda",
                "conda_platform_key": platform,
                "conda_platform": metadata.get("conda_platform", platform),
                "runner": metadata["runner"],
                "setup_conda": metadata.get("setup_conda", True),
                "container": "",
            }
        )

    return entries


def matrix_for_conda_platforms(
    name: str,
    platforms_value: Any,
    platform_config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    platforms = resolve_conda_platforms(platforms_value, platform_config)
    return {"include": conda_platform_matrix_entries(name, platforms, platform_config)}


def matrix_summary_rows(matrix: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in matrix.get("include", []):
        rows.append(
            {
                "name": str(entry["name"]),
                "conda_platform_key": str(
                    entry.get("conda_platform_key", entry["conda_platform"])
                ),
                "conda_platform": str(entry["conda_platform"]),
                "runner": json.dumps(entry["runner"]),
                "artifact_name": f"<run-id>-{entry['name']}",
            }
        )
    return rows
