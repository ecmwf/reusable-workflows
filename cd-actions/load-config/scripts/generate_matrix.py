import json, os, yaml


def deep_merge(common, specific, overrides=None, path=""):
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
        is_override = key in overrides or current_path in overrides
        if specific_val is None:
            result[key] = common_val
        elif common_val is None or is_override:
            result[key] = specific_val
        elif isinstance(common_val, dict) and isinstance(specific_val, dict):
            nested_overrides = [o for o in overrides if o.startswith(f"{key}.") or o.startswith(f"{current_path}.")]
            result[key] = deep_merge(common_val, specific_val, nested_overrides, current_path)
        elif isinstance(common_val, list) and isinstance(specific_val, list):
            result[key] = common_val + specific_val
        else:
            result[key] = specific_val
    return result

def list_to_str_comma_separated(source, source_name):
    if isinstance(source, list):
        return ",".join(source)
    elif isinstance(source, str):
        return source
    else:
        raise ValueError(f"{source_name} must be a list, got {type(source)}")

def list_to_str_line_separated(source, source_name):
    if isinstance(source, list):
        return "\n".join(source)
    elif isinstance(source, str):
        return source
    else:
        raise ValueError(f"{source_name} must be a list, got {type(source)}")

def bool_to_str(source, source_name):
    if isinstance(source, bool):
        return str(source).lower()
    elif isinstance(source, str):
        return str(bool(source))
    else:
        raise ValueError(f"{source_name} must be a bool, got {type(source)}")

def dict_to_str_space_separated(source, source_name):
    if isinstance(source, dict):
        return " ".join([f"{k}={v}" for k, v in source.items()])
    elif isinstance(source, str):
        return source
    else:
        raise ValueError(f"{source_name} must be a dict, got {type(source)}")

def dict_to_str_line_separated(source, source_name):
    if isinstance(source, dict):
        return "\n".join([f"{k}={v}" for k, v in source.items()])
    elif isinstance(source, str):
        return source
    else:
        raise ValueError(f"{source_name} must be a dict, got {type(source)}")

config_yaml = os.environ["STEP_LOAD_CONFIG"]
config = yaml.safe_load(config_yaml)
common_config = config.get("common_config", {})
matrix = {"include": []}

for build in config.get("builds", []):
    if build.get("enabled", True):
        build_type = build["type"]
        build_config_raw = build.get("config", {})
        overrides = build.get("common_config_overrides", [])
        type_common = common_config.get(build_type, {})
        build_config = deep_merge(type_common, build_config_raw, overrides)

        matrix_item = {
            "name": build["name"],
            "runner": ["self-hosted", "platform-builder"],
            "type": build_type,
        }

        if build_type == "conda":
            matrix_item["conda_dir"] = build_config.get("conda_dir", "./.cd/conda")
            channels = list_to_str_comma_separated(build_config.get("channels", ["conda-forge"]), "channels")
            matrix_item["conda_build_args"] = list_to_str_comma_separated(build_config.get("conda_build_args", ["--no-anaconda-upload"]), "conda_build_args")
            matrix_item["skip_installation_test"] = bool_to_str(build_config.get("skip_installation_test", False), "skip_installation_test")

        elif build_type == "python-pypi":
            matrix_item["working_directory"] = build_config.get("working_directory", "./")
            matrix_item["buildargs"] = build_config.get("buildargs", "")
            matrix_item["env_vars"] = dict_to_str_line_separated(build_config.get("env_vars", {}), "env_vars")

        elif build_type == "hpc":
            # Platform
            matrix_item["runner"] = ["self-hosted", "linux", "hpc"]
            matrix_item["platform"] = build_config.get("platform", "gnu-14.2.0")

            # Installation
            matrix_item["install_prefix"] = build_config.get("install_prefix", "")
            matrix_item["prefix_compiler_specific"] = bool_to_str(build_config.get("prefix_compiler_specific", False), "prefix_compiler_specific")

            # Build Configuration
            cmake_options = dict_to_str_line_separated(build_config.get("cmake_options", {}), "cmake_options")
            ctest_options = list_to_str_line_separated(build_config.get("ctest_options", []), "ctest_options")
            matrix_item["self_test"] = bool_to_str(build_config.get("self_test", True), "self_test")
            matrix_item["env_vars"] = dict_to_str_line_separated(build_config.get("env_vars", {}), "env_vars")
            matrix_item["parallel"] = str(build_config.get("parallel", ""))
            matrix_item["dependencies"] = list_to_str_line_separated(build_config.get("dependencies", []), "dependencies")
            dep_cmake_raw = build_config.get("dependency_cmake_options", {})
            dep_cmake_processed = {}
            for repo, opts in dep_cmake_raw.items():
                if isinstance(opts, list):
                    dep_cmake_processed[repo] = ",".join(opts)
                else:
                    dep_cmake_processed[repo] = opts
            matrix_item["dependency_cmake_options"] = dict_to_str_line_separated(dep_cmake_processed, "dependency_cmake_options")
            matrix_item["python_dependencies"] = list_to_str_line_separated(build_config.get("python_dependencies", []), "python_dependencies")
            matrix_item["python_version"] = build_config.get("python_version", "")
            matrix_item["python_requirements"] = build_config.get("python_requirements", "")
            matrix_item["python_toml_opt_dep_sections"] = list_to_str_line_separated(build_config.get("python_toml_opt_dep_sections", []), "python_toml_opt_dep_sections")
            matrix_item["conda_deps"] = list_to_str_line_separated(build_config.get("conda_deps", []), "conda_deps")
            matrix_item["stages"] = json.dumps(build_config.get("stages", []))
            matrix_item["modules"] = list_to_str_line_separated(build_config.get("modules", []), "modules")
            matrix_item["install_command"] = build_config.get("install_command", "")
            matrix_item["lock_permissions"] = bool_to_str(build_config.get("lock_permissions", True), "lock_permissions")
            matrix_item["module_name"] = build_config.get("module_name", "")
            matrix_item["ntasks"] = str(build_config.get("ntasks", ""))
            matrix_item["gpus"] = str(build_config.get("gpus", ""))
            matrix_item["queue"] = build_config.get("queue", "")
            matrix_item["post_script"] = build_config.get("post_script", "")
            matrix_item["clean_before_install"] = bool_to_str(build_config.get("clean_before_install", False), "clean_before_install")
            matrix_item["dry_run_install"] = bool_to_str(build_config.get("dry_run_install", False), "dry_run_install")
            matrix_item["dry_run_install_prefix"] = build_config.get("dry_run_install_prefix", "")
            matrix_item["site"] = build_config.get("site", "hpc-batch")
            matrix_item["sync_module"] = bool_to_str(build_config.get("sync_module", True), "sync_module")
            matrix_item["use_ninja"] = bool_to_str(build_config.get("use_ninja", True), "use_ninja")
            matrix_item["force_build"] = bool_to_str(build_config.get("force_build", False), "force_build")
            matrix_item["ecbundle"] = bool_to_str(build_config.get("ecbundle", False), "ecbundle")
            matrix_item["bundle_yml"] = build_config.get("bundle_yml", "")
            matrix_item["install_lib_dir"] = build_config.get("install_lib_dir", "lib")
            matrix_item["mkdir"] = list_to_str_line_separated(build_config.get("mkdir", []), "mkdir")
            matrix_item["pytest_cmd"] = build_config.get("pytest_cmd", "")
            matrix_item["workdir"] = build_config.get("workdir", "")
            matrix_item["output_dir"] = build_config.get("output_dir", "")

        elif build_type == "tarball":
            matrix_item["ecbuild_version"] = build_config.get("ecbuild_version", "")
            matrix_item["cmake_options"] = dict_to_str_space_separated(build_config.get("cmake_options", {}), "cmake_options")
            matrix_item["confluence_space"] = build_config.get("confluence_space", "")
            matrix_item["confluence_page_title"] = build_config.get("confluence_page_title", "Releases")

        matrix["include"].append(matrix_item)

with open(os.environ["GITHUB_OUTPUT"], "a") as f:
    f.write(f"matrix={json.dumps(matrix)}\n")
