#!/usr/bin/env python3
"""Generate HPC build template from Jinja2 templates and configuration."""

from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, FileSystemLoader

from hpc_common import (
    MODULE_TAG_RE,
    env_bool,
    load_hpc_config,
    load_shared_defaults,
    parse_stages,
    resolve_module_name,
)


def cmake_value(v):
    if isinstance(v, bool):
        return "ON" if v else "OFF"
    return v


def cache_key(name, ref, compiler, cmake_opts):
    key_data = f"{name}:{ref}:{compiler}:{':'.join(cmake_opts or [])}"
    return f"{name}-{hashlib.sha256(key_data.encode()).hexdigest()[:12]}"


def _lines(raw: str) -> list[str]:
    """Split a line-separated input into stripped, non-empty items."""
    return [item.strip() for item in raw.splitlines() if item.strip()]


def split_repo_ref(dep: str) -> tuple[str, str, str]:
    """Split "owner/repo@ref" into (owner, name, ref); owner defaults to ecmwf, ref to main."""
    if "@" in dep:
        dep_repo, dep_ref = dep.rsplit("@", 1)
    else:
        dep_repo, dep_ref = dep, "main"
    if "/" in dep_repo:
        dep_owner, dep_name = dep_repo.split("/", 1)
    else:
        dep_owner, dep_name = "ecmwf", dep_repo
    return dep_owner, dep_name, dep_ref


@dataclass
class Inputs:
    """Everything the rendering needs, read from the environment in one place."""

    stages: list[Any]
    use_staged: bool
    cmake_options: list[str]
    ctest_options: list[str]
    dependencies_raw: str
    dep_cmake_map: dict[str, str]
    python_dependencies_raw: str
    package_modules: list[str]
    env_list: list[str]
    repo_owner: str
    repo_name: str
    ref_name: str
    sha: str
    compiler: str
    compiler_modules: str
    install_prefix: str
    base_install_prefix: str
    module_name: str
    parallel: str
    ntasks: str
    gpus: str
    queue: str
    site: str
    do_sync: bool
    tag_module: bool
    is_prerelease: bool
    dry_run: bool
    lock_permissions: bool
    use_ninja: bool
    self_test: bool
    force_build: bool
    ecbundle: bool
    clean_before_install: bool
    python_version: str
    requirements_path: str
    toml_opt_dep_sections: str
    conda_deps: str
    post_script: str | None
    bundle_yml_input: str
    install_command: str
    mkdir_list: list[str]
    pytest_cmd: str
    module_tag_name: str
    build_name: str
    dry_run_install: bool
    prefix_compiler_specific: bool


def read_inputs(env: Mapping[str, str], defaults: dict[str, Any]) -> Inputs:
    stages = parse_stages(env.get("INPUT_STAGES", ""))
    repository = env["GITHUB_REPOSITORY"]
    repo_owner, repo_name = repository.split("/")

    # Parse dependency cmake options (line-separated repo=opts pairs)
    dep_cmake_map: dict[str, str] = {}
    for line in env.get("INPUT_DEPENDENCY_CMAKE_OPTIONS", "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            dep_cmake_map[key.strip()] = value.strip()

    # Parse cmake options (line-separated KEY=VALUE pairs)
    cmake_options = _lines(env.get("INPUT_CMAKE_OPTIONS", ""))
    install_lib_dir = env.get("INPUT_INSTALL_LIB_DIR", "").strip()
    if install_lib_dir:
        cmake_options.insert(0, f"-DINSTALL_LIB_DIR={install_lib_dir}")

    return Inputs(
        stages=stages,
        use_staged=bool(stages),
        cmake_options=cmake_options,
        ctest_options=_lines(env.get("INPUT_CTEST_OPTIONS", "")),
        dependencies_raw=env.get("INPUT_DEPENDENCIES", "").strip(),
        dep_cmake_map=dep_cmake_map,
        python_dependencies_raw=env.get("INPUT_PYTHON_DEPENDENCIES", "").strip(),
        package_modules=_lines(env.get("INPUT_MODULES", "")),
        env_list=_lines(env.get("INPUT_ENV_VARS", "")),
        repo_owner=repo_owner,
        repo_name=repo_name,
        ref_name=env["INPUT_REF_NAME"],
        sha=env.get("INPUT_SHA", ""),
        compiler=env["STEP_CONFIG_COMPILER"],
        compiler_modules=env["STEP_CONFIG_COMPILER_MODULES"],
        install_prefix=env["STEP_CONFIG_INSTALL_PREFIX"],
        base_install_prefix=env["STEP_CONFIG_BASE_INSTALL_PREFIX"],
        module_name=resolve_module_name(env.get("INPUT_MODULE_NAME", ""), repository),
        parallel=env.get("INPUT_PARALLEL", "").strip() or str(defaults["parallel"]),
        ntasks=env.get("INPUT_NTASKS", "").strip() or str(defaults["ntasks"]),
        gpus=env.get("INPUT_GPUS", "").strip(),
        queue=env.get("INPUT_QUEUE", "").strip() or defaults["queue"],
        site=env.get("INPUT_SITE", defaults["site"]),
        do_sync=env.get("STEP_CONFIG_DO_SYNC", "false") == "true",
        tag_module=env_bool("INPUT_TAG_MODULE", True, env=env),
        is_prerelease=env_bool("INPUT_IS_PRERELEASE", env=env),
        dry_run=env_bool("INPUT_DRY_RUN", env=env),
        lock_permissions=env_bool("INPUT_LOCK_PERMISSIONS", True, env=env),
        use_ninja=env_bool("INPUT_USE_NINJA", True, env=env),
        self_test=env_bool("INPUT_SELF_TEST", True, env=env),
        force_build=env_bool("INPUT_FORCE_BUILD", env=env),
        ecbundle=env_bool("INPUT_ECBUNDLE", env=env),
        clean_before_install=env_bool("INPUT_CLEAN_BEFORE_INSTALL", env=env),
        python_version=env.get("INPUT_PYTHON_VERSION", "").strip(),
        requirements_path=env.get("INPUT_PYTHON_REQUIREMENTS", "").strip() or "requirements.txt",
        toml_opt_dep_sections=",".join(_lines(env.get("INPUT_PYTHON_TOML_OPT_DEP_SECTIONS", ""))),
        conda_deps=" ".join(_lines(env.get("INPUT_CONDA_DEPS", ""))),
        post_script=env.get("INPUT_POST_SCRIPT", "").strip() or None,
        bundle_yml_input=env.get("INPUT_BUNDLE_YML", "").strip(),
        install_command=env.get("INPUT_INSTALL_COMMAND", "").strip(),
        mkdir_list=_lines(env.get("INPUT_MKDIR", "")),
        pytest_cmd=env.get("INPUT_PYTEST_CMD", "").strip(),
        module_tag_name=env.get("INPUT_MODULE_TAG_NAME", "new").strip() or "new",
        build_name=env.get("INPUT_NAME", "").strip(),
        dry_run_install=env_bool("INPUT_DRY_RUN_INSTALL", env=env),
        prefix_compiler_specific=env_bool("INPUT_PREFIX_COMPILER_SPECIFIC", env=env),
    )


def detect_bundle(bundle_yml_input: str) -> tuple[bool, str | None]:
    """Auto-detect a bundle.yml (explicit input path first, then the cwd)."""
    if bundle_yml_input:
        if os.path.exists(bundle_yml_input):
            return True, bundle_yml_input
    elif os.path.exists("bundle.yml"):
        return True, "bundle.yml"
    return False, None


def build_packages(inputs: Inputs, use_ecbundle: bool) -> list[dict[str, Any]]:
    """Build the ordered package list: ecbundle, or deps + main + python packages."""
    if use_ecbundle:
        return [
            {
                "name": inputs.repo_name,
                "owner": inputs.repo_owner,
                "repo": inputs.repo_name,
                "ref": inputs.sha if inputs.sha else inputs.ref_name,
                "type": "ecbundle",
                "prefix": inputs.install_prefix,
                "cmake_options": inputs.cmake_options,
                "ctest_options": inputs.ctest_options,
                "modules": inputs.package_modules,
                "cache_key": cache_key(
                    inputs.repo_name, inputs.ref_name, inputs.compiler, inputs.cmake_options
                ),
                "subdir": "",
            }
        ]

    packages = []

    for dep in _lines(inputs.dependencies_raw):
        dep_owner, dep_name, dep_ref = split_repo_ref(dep)

        # Dependency-specific cmake options are keyed by the repo part of the
        # dependency spec ("owner/repo" or bare "repo"), without the @ref.
        dep_repo = dep.rsplit("@", 1)[0] if "@" in dep else dep
        dep_cmake = inputs.dep_cmake_map.get(dep_repo, "")
        dep_cmake_list = [opt.strip() for opt in dep_cmake.split(",") if opt.strip()] if dep_cmake else []

        packages.append(
            {
                "name": dep_name,
                "owner": dep_owner,
                "repo": dep_name,
                "ref": dep_ref,
                "type": "dependency",
                # Dependency prefix is in workdir deps area
                "prefix": "${TMPDIR}" + f"/deps/{dep_name}",
                "cmake_options": dep_cmake_list,
                "ctest_options": [],
                "modules": [],
                "cache_key": cache_key(dep_name, dep_ref, inputs.compiler, dep_cmake_list),
                "subdir": "",
            }
        )

    # Add main package (CMake) - always add for staged builds, or when no python_version
    if inputs.use_staged or not inputs.python_version:
        packages.append(
            {
                "name": inputs.repo_name,
                "owner": inputs.repo_owner,
                "repo": inputs.repo_name,
                "ref": inputs.sha if inputs.sha else inputs.ref_name,
                "type": "main",
                "prefix": inputs.install_prefix,
                "cmake_options": inputs.cmake_options,
                "ctest_options": inputs.ctest_options,
                "modules": inputs.package_modules,
                "cache_key": cache_key(
                    inputs.repo_name, inputs.ref_name, inputs.compiler, inputs.cmake_options
                ),
                "subdir": "",
                "install_command": inputs.install_command,
            }
        )

    for dep in _lines(inputs.python_dependencies_raw):
        dep_owner, dep_name, dep_ref = split_repo_ref(dep)
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
    if inputs.python_version:
        packages.append(
            {
                "name": inputs.repo_name,
                "owner": inputs.repo_owner,
                "repo": inputs.repo_name,
                "ref": inputs.sha if inputs.sha else inputs.ref_name,
                "type": "main-python",
                "prefix": inputs.install_prefix,
                "cmake_options": [],
                "ctest_options": [],
                "modules": inputs.package_modules,
                "cache_key": "",
                "subdir": "",
            }
        )

    return packages


def compute_tagging(
    inputs: Inputs,
    tag_clusters: list[str] | None,
    sync_clusters: list[str],
    do_sync: bool,
) -> tuple[bool, list[str]]:
    """Decide whether to tag the module, validating names when tagging."""
    if inputs.tag_module and tag_clusters is None:
        print(f"::error::Site '{inputs.site}' not found in tag_clusters in hpc.yml. Cannot tag.")
        sys.exit(1)

    if tag_clusters and not do_sync:
        tag_clusters = [c for c in tag_clusters if c not in sync_clusters]

    release_allowed = not inputs.dry_run and not inputs.is_prerelease
    do_tag = inputs.tag_module and release_allowed and bool(tag_clusters)

    if do_tag:
        if "/" in inputs.ref_name:
            print(f"::error::ref_name '{inputs.ref_name}' contains '/' which is not allowed for module tagging")
            sys.exit(1)
        if not MODULE_TAG_RE.match(inputs.ref_name):
            print(f"::error::ref_name '{inputs.ref_name}' contains invalid characters for module tagging. Allowed: [A-Za-z0-9._-]")
            sys.exit(1)
        if not re.match(r"^[A-Za-z0-9._+/-]+$", inputs.module_name):
            print(f"::error::module_name '{inputs.module_name}' contains invalid characters for tagging. Allowed: [A-Za-z0-9._+/-]")
            sys.exit(1)

    return do_tag, tag_clusters or []


def build_ci_options(
    inputs: Inputs,
    defaults: dict[str, Any],
    use_ecbundle: bool,
    sync_clusters: list[str],
    do_sync: bool,
    do_tag: bool,
    tag_clusters: list[str],
) -> dict[str, Any]:
    return {
        "build_name": inputs.build_name,
        "parallel": int(inputs.parallel),
        "cpus_per_task": int(inputs.parallel),
        "ntasks": int(inputs.ntasks),
        "gpus": int(inputs.gpus) if inputs.gpus else 0,
        "self_test": inputs.self_test,
        "force_build": inputs.force_build,
        "dry_run": inputs.dry_run,
        "dry_run_install": inputs.dry_run_install,
        "skip_install": inputs.dry_run and not inputs.dry_run_install,
        "workdir": "${TMPDIR}",
        "output_path": "",  # Set by generic.jinja wrapper
        "python_version": inputs.python_version or defaults["python_version"],
        "requirements_path": inputs.requirements_path,
        "toml_opt_dep_sections": inputs.toml_opt_dep_sections,
        "conda_deps": inputs.conda_deps,
        "post_script": inputs.post_script,
        "main_package_name": inputs.repo_name,
        "compiler": inputs.compiler,
        "mkdir": inputs.mkdir_list,
        "ecbundle": inputs.ecbundle,
        "use_ecbundle": use_ecbundle,
        "pytest_cmd": inputs.pytest_cmd or None,
        "prefix_compiler_specific": inputs.prefix_compiler_specific,
        "clean_before_install": inputs.clean_before_install,
        "install_prefix": inputs.install_prefix,
        "base_install_prefix": inputs.base_install_prefix,
        "sync_clusters": sync_clusters,
        "sync_module": do_sync,
        "do_tag": do_tag,
        "tag_clusters": tag_clusters,
        "ref_name": inputs.ref_name,
        "module_tag_name": inputs.module_tag_name,
        "module_name": inputs.module_name,
        "queue": inputs.queue,
        "hpc": "lumi" if inputs.site == "lumi" else "atos",
        "hpc_config": {"enable_cache": True},
        "lock_permissions": inputs.lock_permissions,
    }


def normalize_stages(stages: list[Any]) -> None:
    """Ensure required stage fields; render cmake_options dicts to -D args."""
    for i, stage in enumerate(stages):
        stage.setdefault("name", f"stage-{i}")
        stage.setdefault("modules", [])
        stage_cmake = stage.get("cmake_options", {})
        if isinstance(stage_cmake, dict):
            stage["cmake_options"] = [
                f"{'' if k.startswith('-') else '-D'}{k}={cmake_value(v)}"
                for k, v in stage_cmake.items()
            ]
        else:
            stage["cmake_options"] = []
        stage.setdefault("build_command", "")
        stage.setdefault("test_command", "")
        stage.setdefault("install_command", "")


def make_jinja_env(template_dir: Path) -> Environment:
    jinja_env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # ecbundle-build adds its own -D prefix, so we need to strip ours
    jinja_env.filters["strip_d_prefix"] = lambda s: s[2:] if s.startswith("-D") else s
    return jinja_env


def render_sbatch(jinja_env: Environment, inputs: Inputs) -> str:
    sbatch_template = jinja_env.from_string(
        "{% from 'sbatch.jinja' import sbatch_options with context %}{{ sbatch_options() }}"
    )
    return sbatch_template.render(
        site=inputs.site,
        queue=inputs.queue,
        ntasks=inputs.ntasks,
        parallel=inputs.parallel,
        gpus=inputs.gpus,
    ).strip()


def main():
    action_dir = Path(os.environ["GITHUB_ACTION_PATH"])
    shared_defaults = load_shared_defaults(action_dir)
    defaults = shared_defaults["hpc"]
    hpc_config = load_hpc_config(action_dir)

    jinja_env = make_jinja_env(action_dir / "templates")

    inputs = read_inputs(os.environ, defaults)

    use_ecbundle, bundle_yml_path = detect_bundle(inputs.bundle_yml_input)
    if use_ecbundle:
        print(f"Detected bundle.yml at: {bundle_yml_path} - using ecbundle")

    sync_clusters_map = hpc_config["sync_clusters"]
    sync_clusters = sync_clusters_map.get(inputs.site, sync_clusters_map.get("aa-batch", []))
    do_sync = inputs.do_sync and bool(sync_clusters)

    do_tag, tag_clusters = compute_tagging(
        inputs,
        hpc_config.get("tag_clusters", {}).get(inputs.site, None),
        sync_clusters,
        do_sync,
    )

    packages = build_packages(inputs, use_ecbundle)
    ci_options = build_ci_options(
        inputs, defaults, use_ecbundle, sync_clusters, do_sync, do_tag, tag_clusters
    )

    # Build generic modules list (compiler + ninja if enabled)
    generic_modules = inputs.compiler_modules.split(",")
    if inputs.use_ninja:
        generic_modules.append("ninja")

    # Github dict with template placeholders; the secrets are substituted by
    # the ci-hpc-generic wrapper, not here.
    github = {
        "user": "{{ github_user }}",
        "token": "{{ github_token }}",
    }

    normalize_stages(inputs.stages)

    # Render template (stages list is empty for standard builds)
    rendered = jinja_env.get_template("build-job.jinja").render(
        packages=packages,
        ci_options=ci_options,
        generic_modules=generic_modules,
        env=inputs.env_list,
        github=github,
        stages=inputs.stages,
    )
    sbatch = render_sbatch(jinja_env, inputs)

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write("template<<EOF\n")
        f.write(rendered)
        f.write("\nEOF\n")
        f.write("sbatch_options<<SBATCH_EOF\n")
        f.write(sbatch)
        f.write("\nSBATCH_EOF\n")

    print(f"Site: {inputs.site}")
    print("Generated template:")
    print(rendered[:2000])
    if len(rendered) > 2000:
        print(f"\n... ({len(rendered) - 2000} more characters)")
    print("\nSBATCH options:")
    print(sbatch)


if __name__ == "__main__":
    main()
