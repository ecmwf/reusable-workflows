#!/usr/bin/env python3
"""Generate HPC build template from Jinja2 templates and configuration."""

import contextlib
import hashlib
import json
import os
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader


def cmake_value(v):
    if isinstance(v, bool):
        return "ON" if v else "OFF"
    return v


def cache_key(name, ref, compiler, cmake_opts):
    key_data = f"{name}:{ref}:{compiler}:{':'.join(cmake_opts or [])}"
    return f"{name}-{hashlib.sha256(key_data.encode()).hexdigest()[:12]}"


def main():
    # Load HPC defaults from config
    action_dir = Path(os.environ["GITHUB_ACTION_PATH"])
    config_dir = action_dir / "config"
    with open(config_dir / "hpc.yml") as f:
        hpc_config = yaml.safe_load(f)
    defaults = hpc_config["defaults"]
    sync_clusters_map = hpc_config["sync_clusters"]

    # Load Jinja templates
    template_dir = action_dir / "templates"
    jinja_env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Check if staged build (parse JSON to check for actual stages)
    stages_input = os.environ.get("INPUT_STAGES", "").strip()
    stages = []
    if stages_input:
        with contextlib.suppress(json.JSONDecodeError):
            stages = json.loads(stages_input)
    use_staged = bool(stages)

    # Parse inputs from environment variables
    cmake_options_input = os.environ.get("INPUT_CMAKE_OPTIONS", "").strip()
    ctest_options_input = os.environ.get("INPUT_CTEST_OPTIONS", "").strip()
    dependencies_input = os.environ.get("INPUT_DEPENDENCIES", "").strip()
    dep_cmake_options_input = os.environ.get("INPUT_DEPENDENCY_CMAKE_OPTIONS", "").strip()
    python_deps_input = os.environ.get("INPUT_PYTHON_DEPENDENCIES", "").strip()
    modules_input = os.environ.get("INPUT_MODULES", "").strip()
    env_vars_input = os.environ.get("INPUT_ENV_VARS", "").strip()
    install_lib_dir = os.environ.get("INPUT_INSTALL_LIB_DIR", "").strip()

    repository = os.environ["GITHUB_REPOSITORY"]
    repo_owner, repo_name = repository.split("/")
    ref_name = os.environ["INPUT_REF_NAME"]
    sha = os.environ.get("INPUT_SHA", "")
    compiler = os.environ["STEP_CONFIG_COMPILER"]
    compiler_modules = os.environ["STEP_CONFIG_COMPILER_MODULES"]
    install_prefix = os.environ["STEP_CONFIG_INSTALL_PREFIX"]
    base_install_prefix = os.environ["STEP_CONFIG_BASE_INSTALL_PREFIX"]
    module_name = os.environ.get("INPUT_MODULE_NAME", "").strip() or repo_name
    parallel = os.environ.get("INPUT_PARALLEL", "").strip() or str(defaults["parallel"])
    ntasks = os.environ.get("INPUT_NTASKS", "").strip() or str(defaults["ntasks"])
    gpus = os.environ.get("INPUT_GPUS", "").strip()
    queue = os.environ.get("INPUT_QUEUE", "").strip() or defaults["queue"]
    site = os.environ.get("INPUT_SITE", "hpc-batch")
    sync_clusters = sync_clusters_map.get(site, sync_clusters_map.get("aa-batch", []))
    do_sync = os.environ.get("STEP_CONFIG_DO_SYNC", "false") == "true"
    if not sync_clusters:
        do_sync = False
    lock_permissions = os.environ.get("INPUT_LOCK_PERMISSIONS", "true") == "true"
    use_ninja = os.environ.get("INPUT_USE_NINJA", "true") == "true"
    self_test = os.environ.get("INPUT_SELF_TEST", "true") == "true"
    force_build = os.environ.get("INPUT_FORCE_BUILD", "false") == "true"
    ecbundle = os.environ.get("INPUT_ECBUNDLE", "false") == "true"
    clean_before_install = os.environ.get("INPUT_CLEAN_BEFORE_INSTALL", "false") == "true"
    python_version = os.environ.get("INPUT_PYTHON_VERSION", "").strip()
    requirements_path = os.environ.get("INPUT_PYTHON_REQUIREMENTS", "").strip() or "requirements.txt"
    toml_opt_dep_sections_raw = os.environ.get("INPUT_PYTHON_TOML_OPT_DEP_SECTIONS", "").strip()
    toml_opt_dep_sections_list = [s.strip() for s in toml_opt_dep_sections_raw.splitlines() if s.strip()]
    toml_opt_dep_sections = ",".join(toml_opt_dep_sections_list)
    conda_deps_raw = os.environ.get("INPUT_CONDA_DEPS", "").strip()
    conda_deps_list = [d.strip() for d in conda_deps_raw.splitlines() if d.strip()]
    conda_deps = " ".join(conda_deps_list)
    post_script = os.environ.get("INPUT_POST_SCRIPT", "").strip() or None
    bundle_yml_input = os.environ.get("INPUT_BUNDLE_YML", "").strip()
    install_command = os.environ.get("INPUT_INSTALL_COMMAND", "").strip()
    mkdir_input = os.environ.get("INPUT_MKDIR", "").strip()
    pytest_cmd_input = os.environ.get("INPUT_PYTEST_CMD", "").strip()

    # Parse mkdir (line-separated)
    mkdir_list = [d.strip() for d in mkdir_input.splitlines() if d.strip()]

    # Build generic modules list (compiler + ninja if enabled)
    generic_modules = compiler_modules.split(",")
    if use_ninja:
        generic_modules.append("ninja")

    # === BUILD COMMON CONTEXT ===

    # Parse cmake options (line-separated KEY=VALUE pairs)
    cmake_options = [opt.strip() for opt in cmake_options_input.splitlines() if opt.strip()]

    # Parse ctest options (line-separated, fully formed options e.g. --output-on-failure)
    ctest_options = [opt.strip() for opt in ctest_options_input.splitlines() if opt.strip()]

    # Add install lib dir if specified
    if install_lib_dir:
        cmake_options.insert(0, f"INSTALL_LIB_DIR={install_lib_dir}")

    # Parse dependency cmake options (line-separated repo=opts pairs)
    dep_cmake_map = {}
    for line in dep_cmake_options_input.splitlines():
        line = line.strip()
        if not line:
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            dep_cmake_map[key.strip()] = value.strip()

    # Parse modules (line-separated)
    package_modules = [m.strip() for m in modules_input.splitlines() if m.strip()]

    # Parse environment variables (line-separated KEY=VALUE pairs)
    env_list = [v.strip() for v in env_vars_input.splitlines() if v.strip()]

    # Auto-detect bundle.yml
    use_ecbundle = False
    bundle_yml_path = None

    if bundle_yml_input:
        if os.path.exists(bundle_yml_input):
            bundle_yml_path = bundle_yml_input
            use_ecbundle = True
    elif os.path.exists("bundle.yml"):
        bundle_yml_path = "bundle.yml"
        use_ecbundle = True

    if use_ecbundle:
        print(f"Detected bundle.yml at: {bundle_yml_path} - using ecbundle")

    # Build packages list
    packages = []

    # Use ecbundle workflow if bundle.yml detected
    if use_ecbundle:
        packages = [
            {
                "name": repo_name,
                "owner": repo_owner,
                "repo": repo_name,
                "ref": sha if sha else ref_name,
                "type": "ecbundle",
                "prefix": install_prefix,
                "cmake_options": cmake_options,
                "ctest_options": ctest_options,
                "modules": package_modules,
                "cache_key": cache_key(repo_name, ref_name, compiler, cmake_options),
                "subdir": "",
            }
        ]
    else:
        # Parse dependencies
        for dep in dependencies_input.splitlines():
            dep = dep.strip()
            if not dep:
                continue
            if "@" in dep:
                dep_repo, dep_ref = dep.rsplit("@", 1)
            else:
                dep_repo, dep_ref = dep, "main"

            if "/" in dep_repo:
                dep_owner, dep_name = dep_repo.split("/", 1)
            else:
                dep_owner, dep_name = "ecmwf", dep_repo

            # Get dependency-specific cmake options
            dep_cmake = dep_cmake_map.get(dep_repo, "")
            dep_cmake_list = [opt.strip() for opt in dep_cmake.split(",") if opt.strip()] if dep_cmake else []

            # Dependency prefix is in workdir deps area
            dep_prefix = "${TMPDIR}" + f"/deps/{dep_name}"

            packages.append(
                {
                    "name": dep_name,
                    "owner": dep_owner,
                    "repo": dep_name,
                    "ref": dep_ref,
                    "type": "dependency",
                    "prefix": dep_prefix,
                    "cmake_options": dep_cmake_list,
                    "ctest_options": [],
                    "modules": [],
                    "cache_key": cache_key(dep_name, dep_ref, compiler, dep_cmake_list),
                    "subdir": "",
                }
            )

        # Add main package (CMake) - always add for staged builds, or when no python_version
        if use_staged or not python_version:
            packages.append(
                {
                    "name": repo_name,
                    "owner": repo_owner,
                    "repo": repo_name,
                    "ref": sha if sha else ref_name,
                    "type": "main",
                    "prefix": install_prefix,
                    "cmake_options": cmake_options,
                    "ctest_options": ctest_options,
                    "modules": package_modules,
                    "cache_key": cache_key(repo_name, ref_name, compiler, cmake_options),
                    "subdir": "",
                    "install_command": install_command,
                }
            )

        # Parse Python dependencies
        for dep in python_deps_input.splitlines():
            dep = dep.strip()
            if not dep:
                continue
            if "@" in dep:
                dep_repo, dep_ref = dep.rsplit("@", 1)
            else:
                dep_repo, dep_ref = dep, "main"

            if "/" in dep_repo:
                dep_owner, dep_name = dep_repo.split("/", 1)
            else:
                dep_owner, dep_name = "ecmwf", dep_repo

            packages.append(
                {
                    "name": dep_name,
                    "owner": dep_owner,
                    "repo": dep_name,
                    "ref": dep_ref,
                    "type": "dependency-python",
                    "prefix": "",
                    "cmake_options": [],
                    "ctest_options": [],
                    "modules": [],
                    "cache_key": "",
                    "subdir": "",
                }
            )

        # Add main Python package
        if python_version:
            packages.append(
                {
                    "name": repo_name,
                    "owner": repo_owner,
                    "repo": repo_name,
                    "ref": sha if sha else ref_name,
                    "type": "main-python",
                    "prefix": install_prefix,
                    "cmake_options": [],
                    "ctest_options": [],
                    "modules": package_modules,
                    "cache_key": "",
                    "subdir": "",
                }
            )

    # Build name for logging
    build_name = os.environ.get("INPUT_NAME", "").strip()

    dry_run = os.environ.get("INPUT_DRY_RUN", "false") == "true"
    dry_run_install = os.environ.get("INPUT_DRY_RUN_INSTALL", "false") == "true"
    # Build ci_options dict
    ci_options = {
        "build_name": build_name,
        "parallel": int(parallel),
        "cpus_per_task": int(parallel),
        "ntasks": int(ntasks),
        "gpus": int(gpus) if gpus else 0,
        "self_test": self_test,
        "force_build": force_build,
        "dry_run": dry_run,
        "dry_run_install": dry_run_install,
        "skip_install": dry_run and not dry_run_install,
        "workdir": "${TMPDIR}",
        "output_path": "",  # Set by generic.jinja wrapper
        "python_version": python_version or defaults["python_version"],
        "requirements_path": requirements_path,
        "toml_opt_dep_sections": toml_opt_dep_sections,
        "conda_deps": conda_deps,
        "post_script": post_script,
        "main_package_name": repo_name,
        "compiler": compiler,
        "mkdir": mkdir_list,
        "ecbundle": ecbundle,
        "use_ecbundle": use_ecbundle,
        "pytest_cmd": pytest_cmd_input or None,
        "prefix_compiler_specific": os.environ.get("INPUT_PREFIX_COMPILER_SPECIFIC", "false") == "true",
        "clean_before_install": clean_before_install,
        "install_prefix": install_prefix,
        "base_install_prefix": base_install_prefix,
        "sync_clusters": sync_clusters,
        "sync_module": do_sync,
        "module_name": module_name,
        "queue": queue,
        "hpc": "lumi" if site == "lumi" else "atos",
        "hpc_config": {"enable_cache": True},
        "lock_permissions": lock_permissions,
    }

    # Build github dict (with template placeholders for secrets)
    github = {
        "user": "{{ github_user }}",
        "token": "{{ github_token }}",
    }

    # === RENDER TEMPLATE ===
    template = jinja_env.get_template("build-job.jinja")

    # Normalize stages to ensure required fields
    for i, stage in enumerate(stages):
        stage.setdefault("name", f"stage-{i}")
        stage.setdefault("modules", [])
        stage_cmake = stage.get("cmake_options", {})
        if isinstance(stage_cmake, dict):
            stage["cmake_options"] = [f"{k}={cmake_value(v)}" for k, v in stage_cmake.items()]
        else:
            stage["cmake_options"] = []
        stage.setdefault("build_command", "")
        stage.setdefault("test_command", "")
        stage.setdefault("install_command", "")

    # Render template (stages list is empty for standard builds)
    rendered = template.render(
        packages=packages,
        ci_options=ci_options,
        generic_modules=generic_modules,
        env=env_list,
        github=github,
        stages=stages,
    )

    # Generate sbatch options using the macro from sbatch.jinja
    sbatch_template = jinja_env.from_string(
        "{% from 'sbatch.jinja' import sbatch_options with context %}{{ sbatch_options() }}"
    )
    sbatch = sbatch_template.render(
        site=site,
        queue=queue,
        ntasks=ntasks,
        parallel=parallel,
        gpus=gpus,
    ).strip()

    # Write outputs
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write("template<<EOF\n")
        f.write(rendered)
        f.write("\nEOF\n")
        f.write("sbatch_options<<SBATCH_EOF\n")
        f.write(sbatch)
        f.write("\nSBATCH_EOF\n")

    print("Generated template:")
    print(rendered[:2000])
    if len(rendered) > 2000:
        print(f"\n... ({len(rendered) - 2000} more characters)")
    print("\nSBATCH options:")
    print(sbatch)


if __name__ == "__main__":
    main()
