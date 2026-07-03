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

from cd_config import (
    load_hpc_clusters as load_hpc_config,
    load_hpc_platforms as load_platform_map,
)
from cd_helpers import env_bool

__all__ = [
    "DEFAULT_NTASKS",
    "DEFAULT_PARALLEL",
    "DEFAULT_PYTHON_VERSION",
    "DEFAULT_QUEUE",
    "DEFAULT_SITE",
    "MODULE_TAG_RE",
    "env_bool",
    "load_hpc_config",
    "load_platform_map",
    "parse_stages",
    "resolve_module_name",
]

MODULE_TAG_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# Fallbacks for empty inputs — keep in sync with the input defaults in
# hpc/action.yml.
DEFAULT_SITE = "aa-batch"
DEFAULT_PARALLEL = "64"
DEFAULT_NTASKS = "1"
DEFAULT_QUEUE = "nf"
# Template-internal fallback (python_version has no action.yml default; empty
# input means "not a python build").
DEFAULT_PYTHON_VERSION = "3.12"


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
