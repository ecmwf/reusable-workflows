#!/usr/bin/env python3
"""Generate a GitHub Actions matrix from cd-config.yml."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


ACTION_PATH = Path(os.environ.get("GITHUB_ACTION_PATH", Path(__file__).parent.parent))
sys.path.insert(0, str(ACTION_PATH.parent / "lib"))

import yaml  # noqa: E402

from cd_config import (
    load_conda_platforms,
    load_defaults,
    load_runners,
    load_system_package_platforms,
)
from cd_helpers import (
    bool_to_str,
    dict_to_cmake_args,
    dict_to_env_lines,
    list_to_line_separated,
)
from conda_platforms import (
    conda_platform_matrix_entries,
    resolve_conda_platforms,
)
from system_package_platforms import (
    UnknownSystemPackagePlatform,
    resolve_system_package_platform,
)


def deep_merge(
    common: dict[str, Any],
    specific: dict[str, Any],
    overrides: list[str] | None = None,
    path: str = "",
) -> dict[str, Any]:
    """Merge two dictionaries with optional override paths."""
    if overrides is None:
        overrides = []
    if "*" in overrides:
        return specific.copy()
    result: dict[str, Any] = {}
    all_keys = set(common.keys()) | set(specific.keys())
    for key in all_keys:
        common_val = common.get(key)
        specific_val = specific.get(key)
        current_path = f"{path}.{key}" if path else key
        is_override = key in overrides or current_path in overrides
        if specific_val is None:
            result[key] = common_val
        elif common_val is None or is_override:
            result[key] = specific_val
        elif isinstance(common_val, dict) and isinstance(specific_val, dict):
            nested_overrides = [
                o
                for o in overrides
                if o.startswith(f"{key}.") or o.startswith(f"{current_path}.")
            ]
            result[key] = deep_merge(
                common_val, specific_val, nested_overrides, current_path
            )
        elif isinstance(common_val, list) and isinstance(specific_val, list):
            result[key] = common_val + specific_val
        else:
            result[key] = specific_val
    return result


def _json_dumps(value: Any, _name: str) -> str:
    return json.dumps(value)


def _str(value: Any, _name: str) -> str:
    return str(value)


def _hpc_dependency_cmake_options(value: Any, name: str) -> str:
    """Normalize dependency CMake options (lists become comma-separated) then format."""
    if not isinstance(value, dict):
        return dict_to_cmake_args(value, name)
    processed = {}
    for repo, opts in value.items():
        if isinstance(opts, list):
            processed[repo] = ",".join(str(o) for o in opts)
        else:
            processed[repo] = opts
    return dict_to_cmake_args(processed, name)


def _system_package_package_deps(value: Any, _name: str) -> str:
    """Convert package_deps list to comma-separated string."""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


@dataclass(frozen=True)
class Field:
    """Specification for a matrix field derived from build config."""

    name: str
    default_key: str | None = None
    fallback: Any = ""
    transform: Callable[[Any, str], str] | None = None


def _resolve_field(
    build_config: dict[str, Any],
    type_defaults: dict[str, Any],
    field_spec: Field,
) -> tuple[str, str]:
    """Return (field_name, rendered_value) for a single Field specification."""
    value = build_config.get(field_spec.name)
    if value is None and field_spec.default_key is not None:
        value = type_defaults.get(field_spec.default_key)
    if value is None:
        value = field_spec.fallback

    if field_spec.transform is not None:
        rendered = field_spec.transform(value, field_spec.name)
    else:
        rendered = str(value)

    return field_spec.name, rendered


# Field tables per build type. Defaults are read from cd-actions/config/defaults.yml
CONDA_FIELDS = [
    # The fallbacks below are dead backstops that only apply if
    # config/defaults.yml loses the key — keep them in sync with it.
    Field("conda_dir", default_key="conda_dir", fallback="./.cd/conda"),
    Field(
        "channels",
        default_key="channels",
        # TEMPORARY: forward prod nexus -> test nexus (revert me)
        fallback=["conda-forge", "https://nexus-test.ecmwf.int/repository/conda-ecmwf-public"],
        transform=list_to_line_separated,
    ),
    Field(
        "conda_build_args",
        default_key="conda_build_args",
        fallback=["--no-anaconda-upload"],
        transform=list_to_line_separated,
    ),
    Field(
        "skip_installation_test",
        default_key="skip_installation_test",
        fallback=False,
        transform=bool_to_str,
    ),
]

PYTHON_PYPI_FIELDS = [
    Field("working_directory", default_key="working_directory", fallback="./"),
    Field("buildargs", fallback=""),
    Field("env_vars", fallback={}, transform=dict_to_env_lines),
]

HPC_FIELDS = [
    Field("platform", default_key="platform", fallback="gnu-14.2.0"),
    Field("install_prefix", fallback=""),
    Field(
        "prefix_compiler_specific",
        default_key="prefix_compiler_specific",
        fallback=False,
        transform=bool_to_str,
    ),
    Field("cmake_options", fallback={}, transform=dict_to_cmake_args),
    Field("ctest_options", fallback=[], transform=list_to_line_separated),
    Field("self_test", default_key="self_test", fallback=True, transform=bool_to_str),
    Field("env_vars", fallback={}, transform=dict_to_env_lines),
    Field("parallel", fallback=""),
    Field("dependencies", fallback=[], transform=list_to_line_separated),
    Field(
        "dependency_cmake_options",
        fallback={},
        transform=_hpc_dependency_cmake_options,
    ),
    Field("python_dependencies", fallback=[], transform=list_to_line_separated),
    Field("python_version", fallback=""),
    Field("python_requirements", fallback=""),
    Field(
        "python_toml_opt_dep_sections",
        fallback=[],
        transform=list_to_line_separated,
    ),
    Field("conda_deps", fallback=[], transform=list_to_line_separated),
    Field("stages", fallback=[], transform=_json_dumps),
    Field("modules", fallback=[], transform=list_to_line_separated),
    Field("install_command", fallback=""),
    Field(
        "lock_permissions",
        default_key="lock_permissions",
        fallback=True,
        transform=bool_to_str,
    ),
    Field("module_name", fallback=""),
    Field("ntasks", fallback=""),
    Field("gpus", fallback=""),
    Field("queue", fallback=""),
    Field("post_script", fallback=""),
    Field(
        "clean_before_install",
        default_key="clean_before_install",
        fallback=False,
        transform=bool_to_str,
    ),
    Field(
        "dry_run_install",
        default_key="dry_run_install",
        fallback=False,
        transform=bool_to_str,
    ),
    Field("dry_run_install_prefix", fallback=""),
    Field("site", default_key="site", fallback="aa-batch"),
    Field(
        "sync_module", default_key="sync_module", fallback=True, transform=bool_to_str
    ),
    Field(
        "tag_module", default_key="tag_module", fallback=True, transform=bool_to_str
    ),
    Field("module_tag_name", default_key="module_tag_name", fallback=""),
    Field("use_ninja", default_key="use_ninja", fallback=True, transform=bool_to_str),
    Field(
        "force_build", default_key="force_build", fallback=False, transform=bool_to_str
    ),
    Field(
        "ecbundle", default_key="ecbundle", fallback=False, transform=bool_to_str
    ),
    Field("bundle_yml", fallback=""),
    Field("install_lib_dir", default_key="install_lib_dir", fallback="lib"),
    Field("mkdir", fallback=[], transform=list_to_line_separated),
    Field("pytest_cmd", fallback=""),
    Field("workdir", fallback=""),
    Field("output_dir", fallback=""),
]

TARBALL_FIELDS = [
    Field("ecbuild_version", fallback=""),
    Field("cmake_options", fallback={}, transform=dict_to_cmake_args),
    Field("confluence_space", fallback=""),
    Field(
        "confluence_page_title",
        default_key="confluence_page_title",
        fallback="Releases",
    ),
]

SYSTEM_PACKAGE_FIELDS = [
    Field(
        "skip_version_check",
        default_key="skip_version_check",
        fallback=False,
        transform=bool_to_str,
    ),
    Field("description", fallback=""),
    Field("license", fallback=""),
    Field(
        "maintainer", default_key="maintainer", fallback="software@ecmwf.int"
    ),
    Field("vendor", default_key="vendor", fallback="ECMWF"),
    Field("homepage_url", fallback=""),
    Field(
        "install_prefix", default_key="install_prefix", fallback="/opt/ecmwf"
    ),
    Field(
        "self_test", default_key="self_test", fallback=True, transform=bool_to_str
    ),
    Field(
        "install_test",
        default_key="install_test",
        fallback=False,
        transform=bool_to_str,
    ),
    Field("install_test_os_image", fallback=""),
    Field("install_test_command", fallback=""),
    Field("build_type", default_key="build_type", fallback="Release"),
    Field("env", fallback=""),
    Field("deb_section", fallback=""),
    Field("deb_priority", default_key="deb_priority", fallback="optional"),
    Field("rpm_group", fallback=""),
    Field("dependencies", fallback=[], transform=list_to_line_separated),
    Field("dependency_branch", fallback=""),
    Field("cmake_options", fallback={}, transform=dict_to_cmake_args),
    Field("ctest_options", fallback=[], transform=list_to_line_separated),
    Field(
        "dependency_cmake_options", fallback={}, transform=dict_to_cmake_args
    ),
    Field("cmake", default_key="cmake", fallback=False, transform=bool_to_str),
    Field(
        "ecbundle", default_key="ecbundle", fallback=False, transform=bool_to_str
    ),
    Field(
        "self_build", default_key="self_build", fallback=True, transform=bool_to_str
    ),
    Field("toolchain_file", fallback=""),
    Field(
        "parallelism_factor",
        default_key="parallelism_factor",
        fallback="2",
        transform=_str,
    ),
    Field("compiler_cc", default_key="compiler_cc", fallback="gcc"),
    Field("compiler_cxx", default_key="compiler_cxx", fallback="g++"),
    Field("compiler_fc", default_key="compiler_fc", fallback="gfortran"),
    Field("cache_suffix", fallback=""),
    Field(
        "save_cache", default_key="save_cache", fallback=True, transform=bool_to_str
    ),
    Field(
        "recreate_cache",
        default_key="recreate_cache",
        fallback=False,
        transform=bool_to_str,
    ),
]

TYPE_FIELDS: dict[str, list[Field]] = {
    "conda": CONDA_FIELDS,
    "python-pypi": PYTHON_PYPI_FIELDS,
    "hpc": HPC_FIELDS,
    "tarball": TARBALL_FIELDS,
    "system-package": SYSTEM_PACKAGE_FIELDS,
}


def _build_matrix_items(
    build: dict[str, Any],
    common_config: dict[str, Any],
    runners_config: dict[str, Any],
    shared_defaults: dict[str, Any],
    sp_platforms_config: dict[str, Any],
    conda_platforms_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate one or more matrix items from a build definition."""
    build_type = build["type"]
    if build_type not in TYPE_FIELDS:
        supported = ", ".join(sorted(TYPE_FIELDS.keys()))
        print(f"::error::Unsupported build type: {build_type}. Supported: {supported}")
        raise SystemExit(1)

    build_config_raw = build.get("config", {})
    overrides = build.get("common_config_overrides", [])
    type_common = common_config.get(build_type, {})
    build_config = deep_merge(type_common, build_config_raw, overrides)

    matrix_item: dict[str, Any] = {
        "name": build["name"],
        # The literal fallback is a dead backstop — keep in sync with the
        # default entry in config/runners.yml.
        "runner": runners_config.get(
            build_type, runners_config.get("default", ["self-hosted", "platform-builder"])
        ),
        "type": build_type,
        "container": "",
    }

    type_defaults = shared_defaults.get(build_type, {})

    if build_type == "system-package":
        try:
            platform_fields = resolve_system_package_platform(
                build_config.get("os", ""), sp_platforms_config
            )
        except UnknownSystemPackagePlatform as exc:
            print(f"::error::Unknown platform: {exc.os_alias}. Supported: {exc.supported}")
            raise SystemExit(1) from exc
        matrix_item.update(platform_fields)
        package_deps_value = build_config.get("package_deps", [])
        matrix_item["package_deps"] = _system_package_package_deps(
            package_deps_value, "package_deps"
        )

    for field_spec in TYPE_FIELDS[build_type]:
        name, rendered = _resolve_field(build_config, type_defaults, field_spec)
        matrix_item[name] = rendered

    if build_type == "conda":
        platforms_value = build_config.get("platforms", type_defaults.get("platforms"))
        try:
            platforms = resolve_conda_platforms(platforms_value, conda_platforms_config)
        except ValueError as exc:
            print(f"::error::{exc}")
            raise SystemExit(1) from exc

        return [
            {**matrix_item, **platform_item}
            for platform_item in conda_platform_matrix_entries(
                build["name"], platforms, conda_platforms_config
            )
        ]

    return [matrix_item]


def generate_matrix(config: dict[str, Any]) -> dict[str, Any]:
    """Generate the build matrix dictionary from the parsed cd-config."""
    shared_defaults = load_defaults()
    runners_config = load_runners()
    sp_platforms_config = load_system_package_platforms()
    conda_platforms_config = load_conda_platforms()

    common_config = config.get("common_config", {})
    matrix: dict[str, Any] = {"include": []}

    for build in config.get("builds", []):
        if not build.get("enabled", True):
            continue
        matrix_items = _build_matrix_items(
            build,
            common_config,
            runners_config,
            shared_defaults,
            sp_platforms_config,
            conda_platforms_config,
        )
        matrix["include"].extend(matrix_items)

    return matrix


def main() -> None:
    config_yaml = os.environ["STEP_LOAD_CONFIG"]
    config = yaml.safe_load(config_yaml)
    matrix = generate_matrix(config)
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"matrix={json.dumps(matrix)}\n")


if __name__ == "__main__":
    main()
