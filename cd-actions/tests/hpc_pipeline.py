"""Drive the hpc action's scripts exactly as the CD pipeline wires them.

Replicates two mapping layers:
  1. .github/workflows/main-cd.yml "Build with HPC" — matrix.<key> -> action
     inputs, plus release context (ref_name/sha/dry_run/is_prerelease) and the
     ``matrix.module_tag_name || vars.HPC_MODULE_TAG_NAME || 'new'`` expression.
  2. cd-actions/hpc/action.yml — inputs -> INPUT_* env vars per step. Note the
     chaining: the template step's INPUT_MODULE_TAG_NAME and STEP_CONFIG_* come
     from the config step's GITHUB_OUTPUT, not from the raw inputs.

Scripts run in a subprocess with a controlled env, mirroring how composite
action steps execute.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from conftest import CD_ACTIONS_DIR, parse_github_output

HPC_ACTION_DIR = CD_ACTIONS_DIR / "hpc"

# Matrix keys forwarded verbatim to same-named action inputs by main-cd.yml.
MATRIX_FORWARDED_INPUTS = [
    "platform",
    "install_prefix",
    "prefix_compiler_specific",
    "cmake_options",
    "ctest_options",
    "self_test",
    "env_vars",
    "parallel",
    "dependencies",
    "dependency_cmake_options",
    "python_dependencies",
    "python_version",
    "python_requirements",
    "python_toml_opt_dep_sections",
    "conda_deps",
    "stages",
    "modules",
    "install_command",
    "lock_permissions",
    "sync_module",
    "module_name",
    "ntasks",
    "gpus",
    "queue",
    "post_script",
    "clean_before_install",
    "dry_run_install",
    "dry_run_install_prefix",
    "site",
    "tag_module",
    "use_ninja",
    "force_build",
    "ecbundle",
    "bundle_yml",
    "install_lib_dir",
    "mkdir",
    "pytest_cmd",
    "workdir",
    "output_dir",
]


def action_inputs_from_matrix(
    item: dict,
    *,
    ref_name: str,
    sha: str,
    dry_run: str,
    is_prerelease: str,
    hpc_module_tag_name_var: str = "",
) -> dict[str, str]:
    """Build the hpc action's effective inputs for one matrix item."""
    inputs = {key: item[key] for key in MATRIX_FORWARDED_INPUTS}
    inputs["name"] = item["name"]
    inputs["ref_name"] = ref_name
    inputs["sha"] = sha
    inputs["dry_run"] = dry_run
    inputs["is_prerelease"] = is_prerelease
    # GHA `||` falls through on empty strings.
    inputs["module_tag_name"] = (
        item["module_tag_name"] or hpc_module_tag_name_var or "new"
    )
    return inputs


def parse_config_env(inputs: dict[str, str]) -> dict[str, str]:
    """Env for hpc/scripts/parse_config.py (action.yml step id: config)."""
    return {
        "INPUT_PLATFORM": inputs["platform"],
        "INPUT_STAGES": inputs["stages"],
        "INPUT_DRY_RUN": inputs["dry_run"],
        "INPUT_DRY_RUN_INSTALL": inputs["dry_run_install"],
        "INPUT_DRY_RUN_INSTALL_PREFIX": inputs["dry_run_install_prefix"],
        "INPUT_SYNC_MODULE": inputs["sync_module"],
        "INPUT_SITE": inputs["site"],
        "INPUT_INSTALL_PREFIX": inputs["install_prefix"],
        "INPUT_MODULE_NAME": inputs["module_name"],
        "INPUT_REF_NAME": inputs["ref_name"],
        "INPUT_PREFIX_COMPILER_SPECIFIC": inputs["prefix_compiler_specific"],
        "INPUT_IS_PRERELEASE": inputs["is_prerelease"],
        "INPUT_TAG_MODULE": inputs["tag_module"],
        "INPUT_MODULE_TAG_NAME": inputs["module_tag_name"],
        "GITHUB_ACTION_PATH": str(HPC_ACTION_DIR),
    }


def generate_template_env(
    inputs: dict[str, str], config_outputs: dict[str, str]
) -> dict[str, str]:
    """Env for hpc/scripts/generate_template.py (action.yml step id: template)."""
    return {
        "INPUT_STAGES": inputs["stages"],
        "INPUT_CMAKE_OPTIONS": inputs["cmake_options"],
        "INPUT_CTEST_OPTIONS": inputs["ctest_options"],
        "INPUT_DEPENDENCIES": inputs["dependencies"],
        "INPUT_DEPENDENCY_CMAKE_OPTIONS": inputs["dependency_cmake_options"],
        "INPUT_PYTHON_DEPENDENCIES": inputs["python_dependencies"],
        "INPUT_MODULES": inputs["modules"],
        "INPUT_ENV_VARS": inputs["env_vars"],
        "INPUT_INSTALL_LIB_DIR": inputs["install_lib_dir"],
        "INPUT_BUNDLE_YML": inputs["bundle_yml"],
        "INPUT_INSTALL_COMMAND": inputs["install_command"],
        "INPUT_REF_NAME": inputs["ref_name"],
        "INPUT_SHA": inputs["sha"],
        "INPUT_MODULE_NAME": inputs["module_name"],
        "INPUT_IS_PRERELEASE": inputs["is_prerelease"],
        "INPUT_TAG_MODULE": inputs["tag_module"],
        "INPUT_MODULE_TAG_NAME": config_outputs["module_tag_name"],
        "INPUT_PARALLEL": inputs["parallel"],
        "INPUT_NTASKS": inputs["ntasks"],
        "INPUT_GPUS": inputs["gpus"],
        "INPUT_QUEUE": inputs["queue"],
        "INPUT_SITE": inputs["site"],
        "INPUT_LOCK_PERMISSIONS": inputs["lock_permissions"],
        "INPUT_USE_NINJA": inputs["use_ninja"],
        "INPUT_SELF_TEST": inputs["self_test"],
        "INPUT_FORCE_BUILD": inputs["force_build"],
        "INPUT_ECBUNDLE": inputs["ecbundle"],
        "INPUT_CLEAN_BEFORE_INSTALL": inputs["clean_before_install"],
        "INPUT_PYTHON_VERSION": inputs["python_version"],
        "INPUT_PYTHON_REQUIREMENTS": inputs["python_requirements"],
        "INPUT_PYTHON_TOML_OPT_DEP_SECTIONS": inputs["python_toml_opt_dep_sections"],
        "INPUT_CONDA_DEPS": inputs["conda_deps"],
        "INPUT_POST_SCRIPT": inputs["post_script"],
        "INPUT_MKDIR": inputs["mkdir"],
        "INPUT_PYTEST_CMD": inputs["pytest_cmd"],
        "INPUT_NAME": inputs["name"],
        "INPUT_DRY_RUN": inputs["dry_run"],
        "INPUT_DRY_RUN_INSTALL": inputs["dry_run_install"],
        "INPUT_PREFIX_COMPILER_SPECIFIC": inputs["prefix_compiler_specific"],
        "STEP_CONFIG_COMPILER": config_outputs["compiler"],
        "STEP_CONFIG_COMPILER_MODULES": config_outputs["compiler_modules"],
        "STEP_CONFIG_INSTALL_PREFIX": config_outputs["install_prefix"],
        "STEP_CONFIG_BASE_INSTALL_PREFIX": config_outputs["base_install_prefix"],
        "STEP_CONFIG_DO_SYNC": config_outputs["do_sync"],
        "GITHUB_ACTION_PATH": str(HPC_ACTION_DIR),
    }


def run_script(
    script: Path, env: dict[str, str], repository: str, cwd: Path
) -> dict[str, str]:
    """Run a cd-actions script in a subprocess and return its GITHUB_OUTPUT."""
    output_file = cwd / f"github_output_{script.stem}"
    output_file.write_text("")
    full_env = {
        "PATH": os.environ.get("PATH", ""),
        "GITHUB_REPOSITORY": repository,
        "GITHUB_OUTPUT": str(output_file),
        **env,
    }
    result = subprocess.run(
        [sys.executable, str(script)],
        env=full_env,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{script.name} exited with {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return parse_github_output(output_file.read_text())


def render_hpc_job(
    matrix_item: dict,
    *,
    ref_name: str,
    sha: str,
    dry_run: str,
    is_prerelease: str,
    repository: str,
    workdir: Path,
) -> tuple[str, str]:
    """Chain parse_config -> generate_template; return (template, sbatch)."""
    inputs = action_inputs_from_matrix(
        matrix_item,
        ref_name=ref_name,
        sha=sha,
        dry_run=dry_run,
        is_prerelease=is_prerelease,
    )
    config_outputs = run_script(
        HPC_ACTION_DIR / "scripts" / "parse_config.py",
        parse_config_env(inputs),
        repository,
        workdir,
    )
    template_outputs = run_script(
        HPC_ACTION_DIR / "scripts" / "generate_template.py",
        generate_template_env(inputs, config_outputs),
        repository,
        workdir,
    )
    return template_outputs["template"], template_outputs["sbatch_options"]
