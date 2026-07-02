"""Shared helpers for the hpc action's parse_config and generate_template steps."""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_ACTION_PATH = Path(os.environ.get("GITHUB_ACTION_PATH", Path(__file__).parent.parent))
sys.path.insert(0, str(_ACTION_PATH.parent / "lib"))

from cd_helpers import env_bool, load_yaml

__all__ = [
    "MODULE_TAG_RE",
    "env_bool",
    "load_hpc_config",
    "load_platform_map",
    "load_shared_defaults",
    "parse_stages",
    "resolve_module_name",
]

MODULE_TAG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def parse_stages(raw: str) -> list[Any]:
    """Parse the stages JSON input; empty or invalid input means no stages."""
    raw = raw.strip()
    stages: list[Any] = []
    if raw:
        with contextlib.suppress(json.JSONDecodeError):
            stages = json.loads(raw)
    return stages


def resolve_module_name(env_value: str, repository: str) -> str:
    """Module name input, falling back to the repository name."""
    return env_value.strip() or repository.split("/")[-1]


def load_shared_defaults(action_path: Path) -> dict[str, Any]:
    return load_yaml(action_path.parent / "defaults.yml")


def load_platform_map(action_path: Path) -> dict[str, Any]:
    return load_yaml(action_path / "config" / "platforms.yml")


def load_hpc_config(action_path: Path) -> dict[str, Any]:
    return load_yaml(action_path / "config" / "hpc.yml")
