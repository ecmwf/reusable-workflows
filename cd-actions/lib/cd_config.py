"""Central access to the shared config files in cd-actions/config/."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cd_helpers import load_yaml


def config_dir() -> Path:
    """The cd-actions/config directory (override with CD_ACTIONS_CONFIG_DIR)."""
    override = os.environ.get("CD_ACTIONS_CONFIG_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "config"


def conda_platforms_path() -> Path:
    return config_dir() / "platforms-conda.yml"


def load_defaults() -> dict[str, Any]:
    """Per-build-type default field values."""
    return load_yaml(config_dir() / "defaults.yml")


def load_runners() -> dict[str, Any]:
    """Build type -> GitHub runner labels."""
    return load_yaml(config_dir() / "runners.yml")


def load_conda_platforms() -> dict[str, Any]:
    """Conda platform -> runner and setup metadata."""
    return load_yaml(conda_platforms_path())


def load_system_package_platforms() -> dict[str, Any]:
    """System-package OS alias -> container image and Nexus secret names."""
    return load_yaml(config_dir() / "platforms-system-package.yml")


def load_hpc_platforms() -> dict[str, Any]:
    """HPC compiler platform -> toolchain and modules."""
    return load_yaml(config_dir() / "platforms-hpc.yml")


def load_hpc_clusters() -> dict[str, Any]:
    """HPC site -> sync/tag cluster lists."""
    return load_yaml(config_dir() / "hpc-clusters.yml")


def load_conda_nexus() -> dict[str, Any]:
    """Conda Nexus repository URLs."""
    return load_yaml(config_dir() / "nexus-conda.yml")
