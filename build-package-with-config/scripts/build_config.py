"""Helpers for merging the build-package-with-config build configuration."""


def apply_os_overrides(config, matrix_os):
    """Shallow-merge the ``overrides`` section matching matrix_os into config.

    Mutates and returns config. The ``overrides`` key is always removed so it
    is never forwarded to build-package.
    """
    overrides = config.pop("overrides", None)
    if overrides is None:
        return config
    if not isinstance(overrides, dict):
        raise ValueError(
            "`overrides` in build config must be a mapping of matrix.os names to config mappings"
        )
    for os_name, section in overrides.items():
        if not isinstance(os_name, str) or not os_name:
            raise ValueError(
                "`overrides` keys in build config must be non-empty matrix.os strings"
            )
        if section is None:
            continue
        if not isinstance(section, dict):
            raise ValueError(
                "`overrides` section for %r in build config must be a mapping of config keys"
                % os_name
            )
        if "overrides" in section:
            raise ValueError("nested `overrides` are not supported in build config")
    section = overrides.get(matrix_os) if matrix_os else None
    if section:
        config.update(section)
    return config


def pop_python_version(config):
    """Pop python_version from config, requiring a quoted string value."""
    value = config.pop("python_version", "")
    if value is None or value == "":
        return ""
    if not isinstance(value, str):
        raise ValueError(
            'python_version in build config must be a quoted string, e.g. "3.10" (got %r)'
            % value
        )
    return value.strip()
