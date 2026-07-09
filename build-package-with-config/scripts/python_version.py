"""Resolve the Python version used by build-package-with-config."""

import yaml


def _as_version(value):
    """Return a version string while preserving the existing scalar behaviour."""
    return "" if value is None else str(value)


def parse_python_version_overrides(value, source):
    """Validate and normalize an OS-to-Python-version mapping."""
    if not value:
        return {}

    overrides = yaml.safe_load(value) if isinstance(value, str) else value
    if overrides is None:
        return {}
    if not isinstance(overrides, dict):
        raise ValueError("%s must be a YAML mapping of matrix.os to Python versions" % source)

    normalized = {}
    for os_name, version in overrides.items():
        if not isinstance(os_name, str) or not os_name:
            raise ValueError("%s keys must be non-empty matrix.os strings" % source)
        if not isinstance(version, str) or not version.strip():
            raise ValueError(
                "%s values must be non-empty quoted Python version strings" % source
            )
        normalized[os_name] = version.strip()

    return normalized


def resolve_python_version(
    matrix_os,
    input_python_version,
    input_python_version_overrides,
    config_python_version,
    config_python_version_overrides,
):
    """Select a Python version, preferring all action inputs over config values."""
    input_overrides = parse_python_version_overrides(
        input_python_version_overrides,
        "python_version_overrides action input",
    )
    input_python_version = _as_version(input_python_version)

    if input_python_version or input_python_version_overrides.strip():
        return input_overrides.get(matrix_os, input_python_version)

    config_overrides = parse_python_version_overrides(
        config_python_version_overrides,
        "python_version_overrides in build config",
    )
    return config_overrides.get(matrix_os, _as_version(config_python_version))
