"""Shared helpers for CD Python scripts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | os.PathLike[str]) -> Any:
    with open(path) as f:
        return yaml.safe_load(f)


def bool_to_str(value: Any, name: str) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, str):
        return "true" if value.lower() in ("true", "1", "yes") else "false"
    else:
        raise ValueError(f"{name} must be a bool, got {type(value)}")


def list_to_line_separated(value: Any, name: str) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    elif isinstance(value, str):
        return value
    else:
        raise ValueError(f"{name} must be a list, got {type(value)}")


def list_to_comma_separated(value: Any, name: str) -> str:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    elif isinstance(value, str):
        return value
    else:
        raise ValueError(f"{name} must be a list, got {type(value)}")


def dict_to_env_lines(value: Any, name: str) -> str:
    """Convert a dict to newline-separated KEY=VALUE lines."""
    if isinstance(value, dict):
        return "\n".join(
            f"{k}={v}" if v != "" else k for k, v in value.items()
        )
    elif isinstance(value, str):
        return value
    else:
        raise ValueError(f"{name} must be a dict, got {type(value)}")


def dict_to_cmake_args(value: Any, name: str) -> str:
    """Convert a dict to newline-separated -DKEY=VALUE CMake arguments."""
    if isinstance(value, dict):

        def format_cmake_option(k: str, v: Any) -> str:
            if isinstance(v, bool):
                v = "ON" if v else "OFF"
            if not k.startswith("-"):
                k = f"-D{k}"
            return f"{k}={v}" if v != "" else k

        return "\n".join(format_cmake_option(k, v) for k, v in value.items())
    elif isinstance(value, str):
        return value
    else:
        raise ValueError(f"{name} must be a dict, got {type(value)}")
