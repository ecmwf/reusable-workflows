#!/usr/bin/env python3
"""Generate CD build matrix from configuration file."""

import json
import os

import yaml


def deep_merge(common, specific, overrides=None, path=""):
    """
    Merge common config into specific config with override support.

    Overrides:
    - Wildcard '*' to skip all common config
    - Dot notation for nested overrides (e.g., 'dependency_cmake_options.ecmwf/atlas')
    """
    if overrides is None:
        overrides = []
    if "*" in overrides:
        return specific.copy()

    result = {}
    all_keys = set(common.keys()) | set(specific.keys())

    for key in all_keys:
        common_val = common.get(key)
        specific_val = specific.get(key)
        current_path = f"{path}.{key}" if path else key

        # Check if this key or path should be overridden
        is_override = key in overrides or current_path in overrides

        if specific_val is None:
            result[key] = common_val
        elif common_val is None or is_override:
            result[key] = specific_val
        elif isinstance(common_val, dict) and isinstance(specific_val, dict):
            # Filter overrides for nested keys
            nested_overrides = [o for o in overrides if o.startswith(f"{key}.") or o.startswith(f"{current_path}.")]
            result[key] = deep_merge(common_val, specific_val, nested_overrides, current_path)
        elif isinstance(common_val, list) and isinstance(specific_val, list):
            result[key] = common_val + specific_val
        else:
            result[key] = specific_val

    return result


def main():
    config_yaml = os.environ["STEP_LOAD_CONFIG"]
    config = yaml.safe_load(config_yaml)

    common_config = config.get("common_config", {})
    matrix = {"include": []}
    for build in config.get("builds", []):
        if build.get("enabled", True):
            build_type = build["type"]
            build_config_raw = build.get("config", {})
            overrides = build.get("common_config_overrides", [])

            # Get type-specific common config and merge
            type_common = common_config.get(build_type, {})
            build_config = deep_merge(type_common, build_config_raw, overrides)

            matrix_item = {
                "name": build["name"],
                "runner": ["self-hosted", "platform-builder"],
                "type": build_type,
            }

            # Add type-specific config fields as individual matrix values
            if build_type == "conda":
                matrix_item["conda_dir"] = build_config.get("conda_dir", "./.cd/conda")
                # Convert channels list to comma-separated string
                channels = build_config.get("channels", ["conda-forge"])
                if isinstance(channels, list):
                    matrix_item["channels"] = ",".join(channels)
                else:
                    matrix_item["channels"] = str(channels)
                matrix_item["conda_build_args"] = build_config.get("conda_build_args", "--no-anaconda-upload")

            elif build_type == "python-pypi":
                matrix_item["working_directory"] = build_config.get("working_directory", "./")
                matrix_item["buildargs"] = build_config.get("buildargs", "")
                # Keep env_vars as JSON string
                matrix_item["env_vars"] = json.dumps(build_config.get("env_vars", {}))

            elif build_type == "hpc":
                matrix_item["runner"] = ["self-hosted", "linux", "hpc"]
                matrix_item["platform"] = build_config.get("platform", "gnu-12.2.0")
                matrix_item["install_type"] = build_config.get("install_type", "module")
                matrix_item["install_prefix"] = build_config.get("install_prefix", "")
                matrix_item["prefix_compiler_specific"] = str(
                    build_config.get("prefix_compiler_specific", False)
                ).lower()
                cmake_options = build_config.get("cmake_options", {})
                if not isinstance(cmake_options, dict):
                    raise ValueError(f"cmake_options must be a dict, got {type(cmake_options).__name__}")
                matrix_item["cmake_options"] = json.dumps(cmake_options) if cmake_options else ""

                ctest_options = build_config.get("ctest_options", {})
                if not isinstance(ctest_options, dict):
                    raise ValueError(f"ctest_options must be a dict, got {type(ctest_options).__name__}")
                matrix_item["ctest_options"] = json.dumps(ctest_options) if ctest_options else ""
                matrix_item["self_test"] = str(build_config.get("self_test", True)).lower()
                matrix_item["env_vars"] = json.dumps(build_config.get("env_vars", {}))
                matrix_item["parallel"] = str(build_config.get("parallel", ""))
                matrix_item["dependencies"] = build_config.get("dependencies", "")
                dep_cmake_raw = build_config.get("dependency_cmake_options", {})
                if not isinstance(dep_cmake_raw, dict):
                    raise ValueError(f"dependency_cmake_options must be a dict, got {type(dep_cmake_raw).__name__}")
                dep_cmake_converted = {}
                for repo, opts in dep_cmake_raw.items():
                    if not isinstance(opts, list):
                        raise ValueError(
                            f"dependency_cmake_options['{repo}'] must be a list, got {type(opts).__name__}"
                        )
                    dep_cmake_converted[repo] = ",".join(opts)
                matrix_item["dependency_cmake_options"] = (
                    yaml.dump(dep_cmake_converted, default_flow_style=False) if dep_cmake_converted else ""
                )
                matrix_item["python_dependencies"] = build_config.get("python_dependencies", "")
                matrix_item["python_version"] = build_config.get("python_version", "")
                matrix_item["python_requirements"] = build_config.get("python_requirements", "")
                matrix_item["python_toml_opt_dep_sections"] = build_config.get("python_toml_opt_dep_sections", "")
                matrix_item["conda_deps"] = build_config.get("conda_deps", "")
                matrix_item["stages"] = json.dumps(build_config.get("stages", []))
                matrix_item["modules"] = json.dumps(build_config.get("modules", []))
                matrix_item["install_command"] = build_config.get("install_command", "")
                matrix_item["lock_permissions"] = str(build_config.get("lock_permissions", True)).lower()
                matrix_item["module_name"] = build_config.get("module_name", "")
                matrix_item["ntasks"] = str(build_config.get("ntasks", ""))
                matrix_item["gpus"] = str(build_config.get("gpus", ""))
                matrix_item["queue"] = build_config.get("queue", "")
                matrix_item["post_script"] = build_config.get("post_script", "")
                matrix_item["clean_before_install"] = str(build_config.get("clean_before_install", False)).lower()
                matrix_item["dry_run_install"] = str(build_config.get("dry_run_install", False)).lower()
                matrix_item["site"] = build_config.get("site", "hpc-batch")
                matrix_item["sync_module"] = str(build_config.get("sync_module", True)).lower()

            elif build_type == "tarball":
                matrix_item["ecbuild_version"] = build_config.get("ecbuild_version", "")
                matrix_item["cmake_options"] = build_config.get("cmake_options", "")

                matrix_item["confluence_space"] = build_config.get("confluence_space", "")
                matrix_item["confluence_page_title"] = build_config.get("confluence_page_title", "Releases")

            matrix["include"].append(matrix_item)

    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"matrix={json.dumps(matrix)}\n")


if __name__ == "__main__":
    main()
